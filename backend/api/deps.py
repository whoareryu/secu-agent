"""프로덕션 조립. 무거운 것을 한 번만 만든다.

임베딩 모델 로드가 수십 초 걸리므로 프로세스당 한 번만 한다.
에이전트는 요청마다 새로 만든다 — 도구가 클로저로 검색기를 닫고 있고,
그래프 조립 자체는 싸다.
"""

import logging
import os
import threading
from collections.abc import Callable
from functools import lru_cache

import psycopg

from adapters.agent.runner import build_agent
from adapters.db.access_log import PgAccessLog
from adapters.db.catalog import PgDocumentCatalog
from adapters.db.chunk_search import PgChunkSearch
from adapters.db.connection import connect
from adapters.db.log_search import PgLogSearch
from adapters.db.principal_store import PgPrincipalStore
from adapters.embedding.e5 import E5Embedder
from adapters.llm.gemini import build_model
from api.demo import build_demo_router
from api.main import build_app


# 이음매. 테스트가 실제 연결·실제 모델 없이 수명주기만 보게 한다.
def _새_연결():
    conn = connect(os.environ.get("SECUAGENT_DSN"))
    # 읽기 전용 경로가 대부분인데 autocommit 이 꺼져 있으면 매 쿼리가
    # idle-in-transaction 을 남긴다. 관리형 Postgres 는 그런 연결을 끊는다.
    conn.autocommit = True
    return conn


def _새_임베더():
    return E5Embedder()


# **lru_cache 를 쓰지 않는다.** 두 가지 이유가 있다.
#
# 하나. lru_cache 는 값을 영구 보관한다. 연결이 한 번 죽으면(DB 재시작·
# 네트워크) 죽은 연결을 계속 돌려주고, 프로세스를 재시작할 때까지 모든
# 요청이 실패한다. /healthz 도 영원히 db:false 다.
#
# 둘. lru_cache 는 함수 **실행 중** 락을 잡지 않는다. 콜드 스타트에 동시
# 요청 N개가 오면 각각 E5Embedder() 를 만들고(~500MB · ~30초) 캐시에는
# 하나만 남아 나머지가 샌다.
_잠금 = threading.Lock()
_상태: dict[str, object] = {"conn": None, "embedder": None}

# 재연결은 조용히 지나가면 안 된다. DB 가 재시작했다는 사실을 아는 유일한
# 자리이고, 이것이 잦아지면 그 자체가 신호다.
logger = logging.getLogger("secu_agent.deps")


def _자원():
    """(연결, 임베더). 연결이 닫혀 있으면 다시 붙는다.

    임베더는 재연결과 무관하게 유지한다 — 연결이 죽었다고 모델을 다시
    올리면 30초가 날아간다.
    """
    with _잠금:
        if _상태["embedder"] is None:
            _상태["embedder"] = _새_임베더()
        conn = _상태["conn"]
        if conn is None or conn.closed:
            _상태["conn"] = _새_연결()
        return _상태["conn"], _상태["embedder"]


def _연결을_버린다(죽은) -> None:
    """다음 _자원() 이 새로 붙게 한다. 이미 교체됐으면 건드리지 않는다."""
    with _잠금:
        if _상태["conn"] is 죽은:
            _상태["conn"] = None
            logger.warning("DB 연결이 죽어 버린다 — 다음 요청이 새로 붙는다")


def 한_번만[T](작업: Callable[[psycopg.Connection], T]) -> T:
    """연결을 얻어 한 번만 부른다. 실패해도 다시 부르지 않는다.

    **쓰기 경로가 이것을 쓴다.** autocommit 이라 executemany 가 중간에
    끊기면 앞선 행은 이미 커밋돼 있다. 재시도하면 그 행들이 두 번 들어가고,
    열람 기록이 부풀면 감사 자료가 아니게 된다.
    """
    conn, _ = _자원()
    try:
        return 작업(conn)
    except psycopg.OperationalError:
        # 다음 요청이 새 연결을 받게 한다. 이 요청은 실패한다.
        _연결을_버린다(conn)
        raise


def 재시도[T](작업: Callable[[psycopg.Connection], T]) -> T:
    """읽기 경로. 연결이 죽어 있으면 다시 붙어 **한 번만** 다시 부른다.

    `conn.closed` 만으로는 부족하다 — 서버가 연결을 끊어도 다음 쿼리가
    실패하기 전까지 0 이다. 그래서 실패를 보고 판단한다.

    두 번은 하지 않는다. DB 가 내려가 있는 동안 무한히 다시 붙으면 요청이
    끝나지 않고, 그 사이 스레드풀이 찬다.
    """
    conn, _ = _자원()
    try:
        return 작업(conn)
    except psycopg.OperationalError:
        _연결을_버린다(conn)
    conn, _ = _자원()
    logger.warning("DB 에 다시 붙어 재시도한다")
    return 작업(conn)


def 모델_준비됨() -> bool:
    return _상태["embedder"] is not None


def create_app():
    # _자원() 을 여기서 부르지 않는다 — DB 가 기동 시점에 죽어 있으면 import 가
    # 실패해 uvicorn 이 아예 뜨지 못하고, /healthz 조차 응답할 수 없게 된다.
    # 각 클로저가 처음 쓰일 때 자원을 resolve 한다.
    # 모델 객체는 상태가 없고 매 요청 같은 것을 만든다. 그런데 생성 안에
    # ADC 자격증명 해석이 들어 있어, 요청마다 그 일을 다시 했다.
    _모델 = lru_cache(maxsize=1)(build_model)

    def 에이전트_공장():
        conn, embedder = _자원()
        return build_agent(embedder, PgChunkSearch(conn), _모델(), PgLogSearch(conn))

    # 읽기는 재시도(), 쓰기는 한_번만() 을 지난다. 스토어를 호출마다 새로
    # 만드는 것은 원래 모양 그대로다 — 스토어는 연결을 쥔 얇은 껍데기라
    # 만드는 비용이 없고, 그래서 연결이 바뀌어도 낡은 스토어가 남지 않는다.
    class _지연주체저장소:
        def find(self, name):
            return 재시도(lambda c: PgPrincipalStore(c).find(name))

    class _지연열람기록:
        def record(self, rows):
            # 쓰기다. 재시도하면 중복 기록이 된다(한_번만 의 독스트링 참고).
            return 한_번만(lambda c: PgAccessLog(c).record(rows))

        def recent(self, limit):
            return 재시도(lambda c: PgAccessLog(c).recent(limit))

        def violations(self, limit):
            return 재시도(lambda c: PgAccessLog(c).violations(limit))

    class _지연카탈로그:
        def documents(self):
            return 재시도(lambda c: PgDocumentCatalog(c).documents())

        def principals(self):
            return 재시도(lambda c: PgDocumentCatalog(c).principals())

    class _지연로그검색:
        def query(self, principal, event_type, since, limit):
            return 재시도(lambda c: PgLogSearch(c).query(principal, event_type, since, limit))

    주체저장소 = _지연주체저장소()
    # build_demo_router 는 여기서 _자원() 을 부르지 않는다 — 라우터를
    # 조립할 뿐이고, conn·embedder 는 요청이 들어올 때 resolve된다.
    데모_라우터 = build_demo_router(_자원, 주체저장소)

    return build_app(
        에이전트_공장,
        주체저장소,
        모델_준비됨,
        열람기록=_지연열람기록(),
        카탈로그=_지연카탈로그(),
        데모_라우터=데모_라우터,
        로그검색=_지연로그검색(),
    )


app = create_app()

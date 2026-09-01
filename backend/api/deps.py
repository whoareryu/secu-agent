"""프로덕션 조립. 무거운 것을 한 번만 만든다.

임베딩 모델 로드가 수십 초 걸리므로 프로세스당 한 번만 한다.
에이전트는 요청마다 새로 만든다 — 도구가 클로저로 검색기를 닫고 있고,
그래프 조립 자체는 싸다.
"""

import os
from functools import lru_cache

from adapters.agent.runner import build_agent
from adapters.db.access_log import PgAccessLog
from adapters.db.catalog import PgDocumentCatalog
from adapters.db.chunk_search import PgChunkSearch
from adapters.db.connection import connect
from adapters.db.log_search import PgLogSearch
from adapters.db.principal_store import PgPrincipalStore
from adapters.embedding.e5 import E5Embedder
from adapters.llm.gemini import build_model
from api.main import build_app


@lru_cache(maxsize=1)
def _자원():
    conn = connect(os.environ.get("SECUAGENT_DSN"))
    # 읽기 전용 경로가 대부분인데 autocommit 이 꺼져 있으면 매 쿼리가
    # idle-in-transaction 을 남긴다. 관리형 Postgres 는 그런 연결을 끊고,
    # 여기에는 재연결 로직이 없다.
    conn.autocommit = True
    embedder = E5Embedder()
    return conn, embedder


def create_app():
    # _자원() 을 여기서 부르지 않는다 — DB 가 기동 시점에 죽어 있으면 import 가
    # 실패해 uvicorn 이 아예 뜨지 못하고, /healthz 조차 응답할 수 없게 된다.
    # 각 클로저가 처음 쓰일 때 자원을 resolve 한다.
    def 저장소():
        conn, _ = _자원()
        return PgPrincipalStore(conn)

    def 에이전트_공장():
        conn, embedder = _자원()
        return build_agent(embedder, PgChunkSearch(conn), build_model(), PgLogSearch(conn))

    class _지연주체저장소:
        def find(self, name):
            return 저장소().find(name)

    class _지연열람기록:
        def record(self, rows):
            conn, _ = _자원()
            return PgAccessLog(conn).record(rows)

        def recent(self, limit):
            conn, _ = _자원()
            return PgAccessLog(conn).recent(limit)

        def violations(self, limit):
            conn, _ = _자원()
            return PgAccessLog(conn).violations(limit)

    class _지연카탈로그:
        def documents(self):
            conn, _ = _자원()
            return PgDocumentCatalog(conn).documents()

        def principals(self):
            conn, _ = _자원()
            return PgDocumentCatalog(conn).principals()

    def 모델_준비됨() -> bool:
        return _자원.cache_info().currsize > 0

    return build_app(
        에이전트_공장,
        _지연주체저장소(),
        모델_준비됨,
        열람기록=_지연열람기록(),
        카탈로그=_지연카탈로그(),
    )


app = create_app()

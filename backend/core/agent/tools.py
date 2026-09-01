"""에이전트 도구의 실제 로직.

LangChain 도 LLM 도 모른다. 포트만 안다.

adapters/agent/runner.py 와 분리한 것은 스타일이 아니다. LangChain 의
컨텍스트 주입은 컴파일된 그래프를 거쳐야만 동작한다 — 실측: 도구를
직접 invoke 하면 ValidationError, 맨 ToolNode 로도 ValueError 다.
로직이 @tool 래퍼 안에 있으면 단위 테스트할 방법이 없어진다.
"""

from datetime import datetime

from core.agent.policy import MAX_K, MAX_LOG_LIMIT, enforce, enforce_events
from core.ports import ChunkSearch, Embedder, LogSearch
from core.retrieve.hybrid import search
from core.types import LogEvent, PolicyHit, Principal

DEFAULT_K = 10
DEFAULT_LOG_LIMIT = 20


def search_policy(
    query: str,
    principal: Principal,
    embedder: Embedder,
    searcher: ChunkSearch,
    k: int = DEFAULT_K,
) -> list[PolicyHit]:
    """권한이 반영된 규정 청크를 관련도 순으로 돌려준다.

    principal 이 필수 인자다 — 권한 없는 검색을 호출할 방법이 없다(spec 5.3).

    돌려주기 전에 enforce 로 한 번 더 검사한다. 정상 경로에서는 절대
    발동하지 않는다. 발동했다면 사전 필터링이 깨졌다는 뜻이고, 그 사실이
    조용히 묻히면 안 된다(spec 5.4).

    embedder 와 searcher 를 인자로 받는 이유: core 는 어댑터를 만들 수
    없다. 어댑터 쪽이 이 둘을 묶어 LLM 에게는 (query, k) 만 보이는 도구로
    감싼다.

    k 는 MAX_K 로 깎는다 — 호출자가 LLM 일 수 있어 그 값을 믿지 않는다.
    """
    # 모델이 준 값을 믿지 않는다. 호출 횟수 상한과 짝을 이루는 작업량 상한이다.
    k = max(1, min(k, MAX_K))
    ids = search(query, principal, embedder, searcher, k=k)
    hits = searcher.load_hits(ids, principal)
    return enforce(hits, principal)


def query_logs(
    principal: Principal,
    searcher: LogSearch,
    event_type: str | None = None,
    since: datetime | None = None,
    limit: int = DEFAULT_LOG_LIMIT,
) -> list[LogEvent]:
    """권한이 반영된 운영 로그를 최근 순으로 돌려준다.

    search_policy 와 같은 형태다 — principal 이 필수이고, 돌려주기 전에
    enforce_events 로 한 번 더 검사한다. 정상 경로에서는 발동하지 않는다.

    **개수가 주체에 따라 다른 것은 정상이다.** 문서는 상위 k개라 개수가
    고정이지만 로그는 개수가 답이다. 그 때문에 생기는 위험(부분 집계를
    전체로 오해하는 것)은 API 응답의 범위 고지가 막는다 — 모델에게
    맡기지 않는다(보충 spec 2.4).
    """
    limit = max(1, min(limit, MAX_LOG_LIMIT))
    events = searcher.query(principal, event_type, since, limit)
    return enforce_events(events, principal)

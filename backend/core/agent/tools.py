"""에이전트 도구의 실제 로직.

LangChain 도 LLM 도 모른다. 포트만 안다.

adapters/agent/runner.py 와 분리한 것은 스타일이 아니다. LangChain 의
컨텍스트 주입은 컴파일된 그래프를 거쳐야만 동작한다 — 실측: 도구를
직접 invoke 하면 ValidationError, 맨 ToolNode 로도 ValueError 다.
로직이 @tool 래퍼 안에 있으면 단위 테스트할 방법이 없어진다.
"""

from core.agent.policy import MAX_K, enforce
from core.ports import ChunkSearch, Embedder
from core.retrieve.hybrid import search
from core.types import PolicyHit, Principal

DEFAULT_K = 10


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

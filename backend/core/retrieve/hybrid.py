"""하이브리드 검색 — 벡터와 키워드를 RRF 로 융합한다.

포트만 안다. DB 도 임베딩 모델도 모른다.

두 검색기 모두에 principal 을 넘긴다. 한쪽만 권한 필터를 적용하면
그쪽으로 누출된다(spec 6.1).
"""

from core.ports import ChunkSearch, Embedder
from core.retrieve.fusion import rrf
from core.types import Principal

# 융합 전에 각 검색기에서 가져올 후보 수.
# k 보다 넉넉히 가져와야 융합이 의미를 갖는다 — k 개씩만 가져오면
# 두 리스트가 거의 겹치지 않을 때 융합할 것이 없다.
CANDIDATE_MULTIPLIER = 5


def search(
    query: str,
    principal: Principal,
    embedder: Embedder,
    searcher: ChunkSearch,
    k: int = 10,
) -> list[int]:
    """질의로 chunk id 를 최대 k 개, 관련도 순으로 돌려준다."""
    candidates = k * CANDIDATE_MULTIPLIER

    # 질의는 query 접두어다. 문서(passage)와 섞으면 품질이 조용히 나빠진다.
    qvec = embedder.encode([query], kind="query")[0]

    벡터 = searcher.by_vector(qvec, principal, candidates)
    키워드 = searcher.by_keyword(query, principal, candidates)

    return rrf([벡터, 키워드])[:k]

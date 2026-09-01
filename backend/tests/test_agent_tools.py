"""도구 로직 — LangChain 도 LLM 도 DB 도 없이 검사한다.

이 파일이 존재할 수 있는 이유가 곧 설계 근거다. LangChain 의 컨텍스트
주입은 컴파일된 그래프를 거쳐야만 동작하므로(실측), 로직이 @tool 래퍼
안에 있으면 단위 테스트할 방법이 없다. 그래서 로직은 core 에 있다.
"""

import pytest

from core.agent.policy import AccessViolation
from core.agent.tools import search_policy
from core.types import EMBEDDING_DIM, PolicyHit, Principal

사원 = Principal(department="개발팀", clearance=1)


class 고정임베더:
    def encode(self, texts, kind):
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class 스텁검색기:
    """받은 principal 을 기록하고, 미리 정해둔 hit 을 돌려준다."""

    def __init__(self, hits: list[PolicyHit]) -> None:
        self.hits = hits
        self.받은_주체: list[Principal] = []
        self.받은_k: list[int] = []

    def by_vector(self, vec, principal, k):
        self.받은_주체.append(principal)
        self.받은_k.append(k)
        return [h.chunk_id for h in self.hits]

    def by_keyword(self, query, principal, k):
        self.받은_주체.append(principal)
        return [h.chunk_id for h in self.hits]

    def load_hits(self, ids, principal):
        self.받은_주체.append(principal)
        by_id = {h.chunk_id: h for h in self.hits}
        return [by_id[i] for i in ids if i in by_id]


def _hit(chunk_id=1, clearance=1, depts=(), code="2.6.1"):
    return PolicyHit(
        chunk_id=chunk_id,
        text=f"본문 {chunk_id}",
        doc_title="ISMS-P 인증기준 안내서",
        clause_code=code,
        required_clearance=clearance,
        allowed_departments=depts,
    )


def test_권한_안의_결과를_그대로_돌려준다():
    검색기 = 스텁검색기([_hit(1), _hit(2)])
    결과 = search_policy("네트워크 접근", 사원, 고정임베더(), 검색기)
    assert [h.chunk_id for h in 결과] == [1, 2]


def test_모든_검색_경로에_같은_주체를_넘긴다():
    """한 경로라도 다른 주체를 쓰면 그쪽으로 누출된다(spec 6.1)."""
    검색기 = 스텁검색기([_hit(1)])
    search_policy("질의", 사원, 고정임베더(), 검색기)
    assert 검색기.받은_주체, "검색기가 한 번도 안 불렸다"
    assert all(p == 사원 for p in 검색기.받은_주체)


def test_권한_밖_항목이_섞이면_예외가_난다():
    """검색기가 고장나 권한 밖 항목을 돌려주면 도구가 터진다.

    조용히 걸러내면 사후 필터링이 되고, 버그가 결과 개수 뒤에 숨는다.
    이 도구가 core.agent.policy.enforce 의 첫 프로덕션 호출자다.
    """
    검색기 = 스텁검색기([_hit(1), _hit(2, clearance=3)])
    with pytest.raises(AccessViolation):
        search_policy("질의", 사원, 고정임베더(), 검색기)


def test_k_를_검색에_전달한다():
    검색기 = 스텁검색기([_hit(1)])
    search_policy("질의", 사원, 고정임베더(), 검색기, k=3)
    # hybrid.search 가 후보를 k 의 배수로 가져가므로 k 자체가 아니라
    # 그것에 비례한 값이 온다. 0 이나 고정값이 아닌 것만 확인한다.
    assert 검색기.받은_k and all(n >= 3 for n in 검색기.받은_k)


def test_결과가_없으면_빈_리스트다():
    """볼 수 있는 것이 없는 것과 규칙이 깨진 것은 다르다."""
    검색기 = 스텁검색기([])
    assert search_policy("질의", 사원, 고정임베더(), 검색기) == []

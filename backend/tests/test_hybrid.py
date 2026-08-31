from core.retrieve.hybrid import search
from core.types import EMBEDDING_DIM, Principal


class 스텁임베더:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def encode(self, texts, kind):
        self.calls.append(kind)
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class 스텁검색기:
    def __init__(self, vec_hits, kw_hits):
        self.vec_hits, self.kw_hits = vec_hits, kw_hits
        self.받은_주체: list[Principal] = []

    def by_vector(self, vec, principal, k):
        self.받은_주체.append(principal)
        return self.vec_hits[:k]

    def by_keyword(self, query, principal, k):
        self.받은_주체.append(principal)
        return self.kw_hits[:k]


사원 = Principal(department="개발팀", clearance=1)


def test_두_검색_결과를_융합한다():
    s = 스텁검색기(vec_hits=[1, 2, 3], kw_hits=[3, 4, 5])
    # 3 이 양쪽에 있으므로 1위여야 한다
    assert search("질의", 사원, 스텁임베더(), s, k=5)[0] == 3


def test_질의는_query_접두어로_임베딩한다():
    # 문서는 passage, 질의는 query 다. 섞으면 검색 품질이 조용히 나빠진다.
    e = 스텁임베더()
    search("질의", 사원, e, 스텁검색기([1], [2]), k=5)
    assert e.calls == ["query"]


def test_주체를_두_검색기_모두에_넘긴다():
    # 한쪽만 권한 필터를 적용하면 그쪽으로 누출된다(spec 6.1).
    s = 스텁검색기([1], [2])
    search("질의", 사원, 스텁임베더(), s, k=5)
    assert s.받은_주체 == [사원, 사원]


def test_k_개까지만_돌려준다():
    s = 스텁검색기(vec_hits=[1, 2, 3, 4, 5, 6], kw_hits=[7, 8, 9])
    assert len(search("질의", 사원, 스텁임베더(), s, k=3)) == 3


def test_결과가_없으면_빈_리스트다():
    assert search("질의", 사원, 스텁임베더(), 스텁검색기([], []), k=5) == []

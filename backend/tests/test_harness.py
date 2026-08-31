"""eval.harness.evaluate() 의 첫 테스트.

evaluate 의 계약은 "GoldenQuery 마다 다른 principal 로 검색한다"이다. DB 도
임베딩 모델도 없이, principal 을 기록하는 스텁으로 그 계약만 잡는다 —
q.principal 을 고정 주체 하나로 바꿔치기해도 스위트가 초록으로 남는
사태를 막는다.
"""

from core.types import EMBEDDING_DIM, PolicyHit, Principal
from eval.golden import GoldenQuery
from eval.harness import EvalResult, QueryResult, evaluate


class 스텁임베더:
    def encode(self, texts, kind):
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class 스텁검색기:
    """test_hybrid.py 의 스텁검색기와 같은 모양 — load_hits 만 principal 을
    추가로 기록한다."""

    def __init__(self, vec_hits, kw_hits, hits_by_id):
        self.vec_hits, self.kw_hits = vec_hits, kw_hits
        self.hits_by_id = hits_by_id
        self.받은_주체: list[Principal] = []

    def by_vector(self, vec, principal, k):
        self.받은_주체.append(principal)
        return self.vec_hits[:k]

    def by_keyword(self, query, principal, k):
        self.받은_주체.append(principal)
        return self.kw_hits[:k]

    def load_hits(self, ids, principal):
        self.받은_주체.append(principal)
        return [self.hits_by_id[i] for i in ids if i in self.hits_by_id]


사원 = Principal(department="개발팀", clearance=1)
임원 = Principal(department="보안팀", clearance=3)


def _히트(chunk_id: int, clause_code: str | None) -> PolicyHit:
    return PolicyHit(
        chunk_id=chunk_id,
        text="본문",
        doc_title="문서",
        clause_code=clause_code,
        required_clearance=1,
        allowed_departments=(),
    )


def test_질의마다_자기_principal_로_검색한다():
    """GoldenQuery 마다 자기 principal 이 순서대로 searcher 에 전달돼야 한다.

    evaluate 가 q.principal 대신 고정 주체 하나로 바꿔치기하면, 두 번째
    질의에서 임원 대신 사원이 기록되어 이 단언이 깨진다.
    """
    hits_by_id = {1: _히트(1, "A-1"), 2: _히트(2, "B-1")}
    s = 스텁검색기(vec_hits=[1], kw_hits=[1], hits_by_id=hits_by_id)
    q1 = GoldenQuery(query="질의1", principal=사원, relevant=frozenset({"A-1"}))
    q2 = GoldenQuery(query="질의2", principal=임원, relevant=frozenset({"B-1"}))

    evaluate([q1, q2], 스텁임베더(), s, k=5)

    # 질의당 by_vector · by_keyword · load_hits 세 번씩, 질의 순서대로.
    assert s.받은_주체 == [사원, 사원, 사원, 임원, 임원, 임원]


def test_clause_code_가_없는_청크는_채점에서_빠진다():
    """조항 밖 청크(표지 · 목차)는 정답이 될 수 없으므로 점수 계산 전에 빠진다."""
    hits_by_id = {1: _히트(1, None), 2: _히트(2, "A-1")}
    s = 스텁검색기(vec_hits=[1, 2], kw_hits=[], hits_by_id=hits_by_id)
    q = GoldenQuery(query="질의", principal=사원, relevant=frozenset({"A-1"}))

    r = evaluate([q], 스텁임베더(), s, k=5)

    assert r.per_query[0].retrieved == ("A-1",)


def test_EvalResult_집계값을_손으로_확인한다():
    pq = (
        QueryResult(query="q1", recall=1.0, mrr=1.0, ndcg=1.0, latency_ms=10.0, retrieved=("A",)),
        QueryResult(query="q2", recall=0.0, mrr=0.0, ndcg=0.0, latency_ms=30.0, retrieved=()),
    )
    r = EvalResult(k=5, per_query=pq)

    assert r.recall == 0.5
    assert r.mrr == 0.5
    assert r.ndcg == 0.5
    assert r.p50 == 20.0
    assert r.p95 == 30.0

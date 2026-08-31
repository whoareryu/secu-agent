"""골든셋을 실제 검색에 물려 지표를 낸다.

권한 축을 반드시 태운다 — GoldenQuery 마다 다른 principal 로 검색한다.
전부 같은 주체로 돌리면 하네스가 principal 을 무시해도 지표가 같게 나온다.
"""

import statistics
import time
from collections.abc import Sequence
from dataclasses import dataclass

from core.ports import ChunkSearch, Embedder
from core.retrieve.hybrid import search
from eval.golden import GoldenQuery
from eval.metrics import mrr_at_k, ndcg_at_k, recall_at_k


@dataclass(frozen=True)
class QueryResult:
    query: str
    recall: float
    mrr: float
    ndcg: float
    latency_ms: float
    retrieved: tuple[str, ...]


@dataclass(frozen=True)
class EvalResult:
    k: int
    per_query: tuple[QueryResult, ...]

    @property
    def recall(self) -> float:
        return statistics.mean(r.recall for r in self.per_query)

    @property
    def mrr(self) -> float:
        return statistics.mean(r.mrr for r in self.per_query)

    @property
    def ndcg(self) -> float:
        return statistics.mean(r.ndcg for r in self.per_query)

    @property
    def p50(self) -> float:
        return statistics.median(r.latency_ms for r in self.per_query)

    @property
    def p95(self) -> float:
        정렬 = sorted(r.latency_ms for r in self.per_query)
        # 30건에서 p95 는 보간 없이 상위 5% 경계 원소를 쓴다 — 건수가 적어
        # 보간을 해도 정밀도가 늘지 않는다.
        return 정렬[min(len(정렬) - 1, int(len(정렬) * 0.95))]


def evaluate(
    queries: Sequence[GoldenQuery],
    embedder: Embedder,
    searcher: ChunkSearch,
    k: int = 10,
) -> EvalResult:
    결과: list[QueryResult] = []
    for q in queries:
        t0 = time.perf_counter()
        ids = search(q.query, q.principal, embedder, searcher, k=k)
        지연 = (time.perf_counter() - t0) * 1000

        hits = searcher.load_hits(ids, q.principal)
        # 조항 밖 청크(표지·목차)는 코드가 없다. 정답이 될 수 없으므로 뺀다.
        코드 = [h.clause_code for h in hits if h.clause_code]

        정답 = set(q.relevant)
        결과.append(
            QueryResult(
                query=q.query,
                recall=recall_at_k(코드, 정답, k),
                mrr=mrr_at_k(코드, 정답, k),
                ndcg=ndcg_at_k(코드, 정답, k),
                latency_ms=지연,
                retrieved=tuple(코드),
            )
        )
    return EvalResult(k=k, per_query=tuple(결과))

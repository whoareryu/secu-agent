"""python -m eval.run — 골든셋을 돌려 마크다운 표를 낸다.

.venv/bin/python -m eval.run
.venv/bin/python -m eval.run --per-query   # 건별 상세
"""

import argparse
import sys
from pathlib import Path

from adapters.db.chunk_search import PgChunkSearch
from adapters.db.connection import connect
from adapters.embedding.e5 import E5Embedder
from eval.golden import DEFAULT_PATH, load
from eval.harness import evaluate


def main() -> int:
    ap = argparse.ArgumentParser(description="검색 품질 평가")
    ap.add_argument("--golden", default=str(DEFAULT_PATH))
    ap.add_argument("-k", type=int, default=10)
    ap.add_argument("--per-query", action="store_true")
    ap.add_argument("--dsn", default=None)
    args = ap.parse_args()

    queries = load(Path(args.golden))
    conn = connect(args.dsn)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM chunks")
        총청크 = cur.fetchone()[0]
    if 총청크 == 0:
        print("코퍼스가 비어 있다. 먼저 적재한다:", file=sys.stderr)
        print(
            "  python -m pipeline.cli ingest ../data/raw/ismsp.pdf "
            '--title "ISMS-P 인증기준 안내서"',
            file=sys.stderr,
        )
        print("  python -m pipeline.cli ingest-dir ../data/policies", file=sys.stderr)
        return 1

    r = evaluate(queries, E5Embedder(), PgChunkSearch(conn), k=args.k)
    conn.close()

    print(f"\n## 검색 품질 (골든셋 {len(queries)}건 · k={r.k} · 코퍼스 {총청크}청크)\n")
    print("| 지표 | 값 |")
    print("|---|---|")
    print(f"| Recall@{r.k} | {r.recall:.3f} |")
    print(f"| MRR@{r.k} | {r.mrr:.3f} |")
    print(f"| nDCG@{r.k} | {r.ndcg:.3f} |")
    print(f"| 지연 p50 | {r.p50:.0f}ms |")
    print(f"| 지연 p95 | {r.p95:.0f}ms |")

    if args.per_query:
        print("\n### 건별\n")
        print("| 질의 | Recall | MRR | nDCG |")
        print("|---|---|---|---|")
        for q in sorted(r.per_query, key=lambda x: x.recall):
            print(f"| {q.query} | {q.recall:.2f} | {q.mrr:.2f} | {q.ndcg:.2f} |")

    return 0


if __name__ == "__main__":
    sys.exit(main())

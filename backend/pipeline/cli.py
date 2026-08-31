"""파이프라인 CLI.

    python -m pipeline.cli ingest ../data/raw/ismsp.pdf \
        --title "ISMS-P 인증기준 안내서" --clearance 1

권한 등급과 허용 부서를 인자로 받는다. 공개 표준 문서에는 등급 정보가
없으므로 적재하는 사람이 부여한다 — 이 사실은 spec 4.1 에 적혀 있다.
"""

import argparse
import sys
from pathlib import Path

from adapters.db.connection import apply_schema, connect
from adapters.db.document_store import PgDocumentStore
from adapters.embedding.e5 import E5Embedder
from adapters.parsing.loader import load
from core.types import Document
from pipeline.ingest import ingest


def main() -> int:
    ap = argparse.ArgumentParser(description="Secu-Agent 데이터 파이프라인")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ing = sub.add_parser("ingest", help="문서를 적재한다")
    ing.add_argument("path", type=Path)
    ing.add_argument("--title", required=True)
    ing.add_argument("--clearance", type=int, default=1, help="1(사원) 2(팀장) 3(임원)")
    ing.add_argument("--departments", nargs="*", default=[], help="비우면 전사 공개")
    ing.add_argument("--dsn", default=None)

    sch = sub.add_parser("search", help="하이브리드 검색")
    sch.add_argument("query")
    sch.add_argument("--clearance", type=int, default=1)
    sch.add_argument("--department", default="개발팀")
    sch.add_argument("-k", type=int, default=5)
    sch.add_argument("--dsn", default=None)

    args = ap.parse_args()

    if args.cmd == "ingest":
        if not args.path.exists():
            print(f"파일이 없다: {args.path}", file=sys.stderr)
            return 1

        conn = connect(args.dsn)
        apply_schema(conn)
        store = PgDocumentStore(conn)

        doc = Document(
            id=0,
            title=args.title,
            source_path=str(args.path),
            doc_type=args.path.suffix.lstrip(".").lower(),
            required_clearance=args.clearance,
            allowed_departments=tuple(args.departments),
        )

        print(f"{args.path} 적재 중… (모델 로드에 시간이 걸린다)")
        report = ingest(args.path, doc, load, E5Embedder(), store)
        print(f"  조항 {report.clauses}개 · 청크 {report.chunks}개")
        print(f"  DB 총 청크: {store.count_all_chunks()}")
        conn.close()

    if args.cmd == "search":
        from adapters.db.chunk_search import PgChunkSearch
        from core.retrieve.hybrid import search as hybrid_search
        from core.types import Principal

        conn = connect(args.dsn)
        searcher = PgChunkSearch(conn)
        principal = Principal(department=args.department, clearance=args.clearance)

        ids = hybrid_search(args.query, principal, E5Embedder(), searcher, k=args.k)
        rows = searcher.load_hits(ids, principal)

        print(f"질의: {args.query}")
        print(f"주체: {principal.department} · 등급 {principal.clearance}")
        print(f"결과: {len(rows)}건\n")
        for i, hit in enumerate(rows, start=1):
            표시 = f"[{hit.clause_code}]" if hit.clause_code else "[조항 밖]"
            print(f"  {i}. {표시} {hit.doc_title}")
            print(f"     {hit.text[:100].strip()}…\n")
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

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
from adapters.parsing.loader import load, load_meta
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

    ind = sub.add_parser("ingest-dir", help="디렉토리의 마크다운 규정을 전부 적재한다")
    ind.add_argument("path", type=Path)
    ind.add_argument("--dsn", default=None)

    sch = sub.add_parser("search", help="하이브리드 검색")
    sch.add_argument("query")
    sch.add_argument("--clearance", type=int, default=1)
    sch.add_argument("--department", default="개발팀")
    sch.add_argument("-k", type=int, default=5)
    sch.add_argument("--dsn", default=None)

    sub.add_parser("seed-principals", help="시연 계정을 넣는다")

    sh = sub.add_parser("seed-hosts", help="data/hosts.json 의 호스트를 등록한다")
    sh.add_argument("--dsn", default=None)

    il = sub.add_parser("ingest-logs", help="syslog 파일을 적재한다")
    il.add_argument("path", type=Path)
    il.add_argument("--year", type=int, required=True,
                    help="syslog 형식에는 연도가 없다. 명시한다.")
    il.add_argument("--dsn", default=None)

    dem = sub.add_parser("demo", help="같은 질의를 세 계정으로 던진다")
    dem.add_argument("query")
    dem.add_argument("-k", type=int, default=5)
    dem.add_argument("--dsn", default=None)

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

    if args.cmd == "ingest-dir":
        경로들 = sorted(args.path.glob("*.md"))
        if not 경로들:
            print(f"마크다운 문서가 없다: {args.path}", file=sys.stderr)
            return 1

        conn = connect(args.dsn)
        apply_schema(conn)
        store = PgDocumentStore(conn)
        embedder = E5Embedder()  # 모델을 한 번만 로드한다

        for p in 경로들:
            meta = load_meta(p)
            doc = Document(
                id=0,
                title=meta["title"],
                source_path=str(p),
                doc_type="md",
                required_clearance=int(meta["clearance"]),
                allowed_departments=tuple(meta.get("departments") or ()),
            )
            report = ingest(p, doc, load, embedder, store)
            부서 = ",".join(doc.allowed_departments) or "전사"
            print(
                f"  {p.name}: 조항 {report.clauses}개 · 청크 {report.chunks}개 "
                f"(등급 {doc.required_clearance} · {부서})"
            )

        print(f"DB 총 청크: {store.count_all_chunks()}")
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

    if args.cmd == "seed-principals":
        import json

        경로 = Path(__file__).resolve().parents[2] / "data" / "principals.json"
        계정들 = json.loads(경로.read_text(encoding="utf-8"))

        conn = connect(None)
        apply_schema(conn)
        with conn.cursor() as cur:
            for p in 계정들:
                cur.execute(
                    """
                    INSERT INTO principals (name, department, clearance)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        department = EXCLUDED.department,
                        clearance = EXCLUDED.clearance
                    """,
                    (p["name"], p["department"], p["clearance"]),
                )
        conn.commit()
        for p in 계정들:
            print(f"  {p['name']} · {p['department']} · 등급 {p['clearance']}")
        conn.close()

    if args.cmd == "seed-hosts":
        import json

        from adapters.db.host_store import PgHostStore
        from core.types import Host

        경로 = Path(__file__).resolve().parents[2] / "data" / "hosts.json"
        호스트들 = json.loads(경로.read_text(encoding="utf-8"))

        conn = connect(args.dsn)
        apply_schema(conn)
        store = PgHostStore(conn)
        for h in 호스트들:
            store.upsert(
                Host(
                    name=h["name"],
                    department=h["department"],
                    required_clearance=h["required_clearance"],
                    # .get 을 쓰지 않는다. 키를 빠뜨리거나 오타를 내면 빈 튜플이
                    # 되고, 빈 튜플은 전사 공개다 — 오타가 조용히 여는 방향으로
                    # 작동한다. 형제 키들과 같이 직접 인덱싱해 KeyError 로 터진다.
                    allowed_departments=tuple(h["allowed_departments"]),
                )
            )
            print(f"  {h['name']} · {h['department']} · 등급 {h['required_clearance']}")
        conn.close()

    if args.cmd == "ingest-logs":
        if not args.path.exists():
            print(f"파일이 없다: {args.path}", file=sys.stderr)
            return 1

        from pipeline.ingest_logs import MissingHost, ingest_logs

        conn = connect(args.dsn)
        apply_schema(conn)
        try:
            결과 = ingest_logs(args.path, year=args.year, conn=conn)
        except MissingHost as e:
            print(f"거부: {e}", file=sys.stderr)
            conn.close()
            return 1
        print(f"  적재 {결과.적재}건 · 건너뜀 {결과.건너뜀}건")
        conn.close()

    if args.cmd == "demo":
        from adapters.db.chunk_search import PgChunkSearch
        from core.retrieve.hybrid import search as hybrid_search
        from core.types import Principal

        conn = connect(args.dsn)
        searcher = PgChunkSearch(conn)
        embedder = E5Embedder()  # 세 계정이 모델을 공유한다

        with conn.cursor() as cur:
            cur.execute("SELECT name, department, clearance FROM principals ORDER BY clearance")
            계정들 = cur.fetchall()
        if not 계정들:
            print("시연 계정이 없다. 먼저: python -m pipeline.cli seed-principals", file=sys.stderr)
            return 1

        print(f'질의: "{args.query}"\n')
        for 이름, 부서, 등급 in 계정들:
            principal = Principal(department=부서, clearance=등급)
            ids = hybrid_search(args.query, principal, embedder, searcher, k=args.k)
            rows = searcher.load_hits(ids, principal)
            print(f"── {이름} ({부서} · 등급 {등급}) — {len(rows)}건")
            for i, hit in enumerate(rows, start=1):
                표시 = f"[{hit.clause_code}]" if hit.clause_code else "[조항 밖]"
                print(f"   {i}. {표시} {hit.doc_title}")
            print()
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

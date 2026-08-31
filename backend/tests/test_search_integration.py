"""실제 DB 로 하이브리드 검색을 확인한다.

    docker compose up -d
    .venv/bin/python -m pytest -m db -v
"""

import os

import pytest

from adapters.db.chunk_search import _벡터_SQL, PgChunkSearch
from adapters.db.connection import apply_schema, connect
from adapters.db.document_store import PgDocumentStore
from core.ports import ChunkSearch
from core.retrieve.hybrid import search
from core.types import EMBEDDING_DIM, Chunk, Clause, Document, PolicyHit, Principal

pytestmark = pytest.mark.db

DSN = os.environ.get("SECUAGENT_DSN", "postgresql://secuagent:secuagent@localhost:5433/secuagent")
사원 = Principal(department="개발팀", clearance=1)


class 고정임베더:
    """항상 같은 벡터를 준다 — 벡터 검색이 도는지만 본다."""

    def encode(self, texts, kind):
        return [[0.1] * EMBEDDING_DIM for _ in texts]


@pytest.fixture
def db():
    conn = connect(DSN)
    apply_schema(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE documents RESTART IDENTITY CASCADE")
    conn.commit()

    store = PgDocumentStore(conn)
    doc_id = store.upsert_document(Document(
        id=0, title="ISMS-P", source_path="a.pdf", doc_type="pdf",
        required_clearance=1, allowed_departments=(),
    ))
    ids = store.insert_clauses(doc_id, [
        Clause(code="2.6.1", title="네트워크 접근", text="네트워크 접근 통제"),
        Clause(code="2.5.1", title="사용자 계정 관리", text="계정 발급과 관리"),
    ])
    store.insert_chunks(
        doc_id, ids,
        [Chunk(clause_code="2.6.1", ordinal=0, text="네트워크에 대한 비인가 접근을 통제한다"),
         Chunk(clause_code="2.5.1", ordinal=0, text="사용자 계정 발급 절차를 수립한다")],
        [[0.1] * EMBEDDING_DIM, [0.9] * EMBEDDING_DIM],
    )
    yield conn, PgChunkSearch(conn)
    conn.close()


def test_구현이_포트를_만족한다(db):
    _, searcher = db
    assert isinstance(searcher, ChunkSearch)


def test_벡터_검색이_결과를_돌려준다(db):
    _, searcher = db
    assert len(searcher.by_vector([0.1] * EMBEDDING_DIM, 사원, k=10)) == 2


def test_권한_필터가_순위보다_먼저_적용된다(db):
    """실행 계획을 직접 본다. 결과 개수로는 이걸 확인할 수 없다.

    처음에는 "권한 밖 문서를 가까이 심어두고 k 가 채워지는지" 로 쓰려 했다.
    실측해 보니 그 단언은 **흔들린다** — 문서당 500·2000 청크에서는 누출이
    재현되는데 50·200·1000 에서는 재현되지 않았다. HNSW 그래프가 삽입 순서와
    난수에 따라 달라지기 때문이다. `hnsw.ef_search` 를 1 까지 낮춰도 작은
    픽스처에서는 재현되지 않았다.

    흔들리는 보안 테스트는 결국 꺼진다. 그래서 증상 대신 **구조**를 단언한다:
    권한 통과 집합이 CTE 로 먼저 확정되고, 정렬이 그 CTE 위에서 일어나야 한다.
    이건 코퍼스 크기와 무관하게 참이거나 거짓이다.

    `AS MATERIALIZED` 를 지우면 플래너가 CTE 를 인라인해서 이 노드가 사라지고
    테스트가 실패한다.
    """
    conn, _ = db
    with conn.cursor() as cur:
        cur.execute(
            "EXPLAIN " + _벡터_SQL,
            {
                "clearance": 사원.clearance,
                "dept": 사원.department,
                "qvec": str([0.1] * EMBEDDING_DIM),
                "k": 10,
            },
        )
        계획 = "\n".join(row[0] for row in cur.fetchall())

    assert "CTE 허용" in 계획, (
        "권한 통과 집합이 CTE 로 확정되지 않는다. AS MATERIALIZED 가 빠졌거나 "
        f"플래너가 인라인했다. 사후 필터링이 되어 존재가 새어나간다(spec 5.3).\n{계획}"
    )
    assert "CTE Scan" in 계획, (
        f"정렬이 CTE 위에서 일어나지 않는다 — 순위가 권한보다 먼저 매겨진다.\n{계획}"
    )


def test_키워드_검색이_본문에_있는_말을_찾는다(db):
    _, searcher = db
    hits = searcher.by_keyword("네트워크", 사원, k=10)
    assert len(hits) == 1


def test_본문에_없는_말은_키워드_검색에서_0건이다(db):
    _, searcher = db
    assert searcher.by_keyword("존재하지않는단어", 사원, k=10) == []


def test_하이브리드_검색이_두_경로를_모두_쓴다(db):
    _, searcher = db
    hits = search("네트워크 접근", 사원, 고정임베더(), searcher, k=10)
    assert len(hits) == 2      # 벡터가 2건을 주고 키워드가 1건을 더한다


def test_조항_코드까지_불러온다(db):
    _, searcher = db
    hits = search("네트워크", 사원, 고정임베더(), searcher, k=10)
    rows = searcher.load_hits(hits, 사원)
    assert all(isinstance(r, PolicyHit) for r in rows)
    assert {r.clause_code for r in rows} == {"2.6.1", "2.5.1"}


def test_load_hits_는_권한_밖_청크의_본문을_주지_않는다(db):
    """검색을 막아도 여기가 뚫리면 소용없다.

    load_hits 는 청크 **본문**을 돌려준다. 권한 검사를 검색 쪽에만 두면
    id 를 아는 호출자가 이 경로로 본문을 그대로 가져간다. 존재 누출보다
    나쁜 내용 누출이다.

    권한 밖 id 는 조용히 빠져야 한다. 예외를 던지면 "그 id 는 접근 불가"
    라는 응답 자체가 존재 확인이 된다.
    """
    conn, searcher = db
    store = PgDocumentStore(conn)
    기밀 = store.upsert_document(Document(
        id=0, title="3급 기밀", source_path="secret.pdf", doc_type="pdf",
        required_clearance=3, allowed_departments=(),
    ))
    store.insert_chunks(
        기밀, {},
        [Chunk(clause_code=None, ordinal=0, text="대외비: 마스터 키")],
        [[0.5] * EMBEDDING_DIM],
    )
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM chunks")
        전체 = [r[0] for r in cur.fetchall()]

    받은 = searcher.load_hits(전체, 사원)

    assert all("대외비" not in r.text for r in 받은), (
        "등급 1 사원이 3급 기밀 청크의 본문을 받았다. load_hits 에 권한 필터가 없다."
    )
    assert len(받은) < len(전체), "권한 밖 청크가 걸러지지 않았다"


def test_load_hits_가_준_순서를_지킨다(db):
    # SQL 반환 순서에 기대면 융합 결과의 순위가 뒤집힌다.
    _, searcher = db
    ids = searcher.by_vector([0.1] * EMBEDDING_DIM, 사원, k=10)
    rows = searcher.load_hits(list(reversed(ids)), 사원)
    assert [r.chunk_id for r in rows] == list(reversed(ids))

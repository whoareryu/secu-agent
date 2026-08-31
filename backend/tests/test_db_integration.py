"""실제 데이터베이스가 필요한 테스트.

기본 스위트에서 제외된다(pyproject 의 addopts). 돌리려면:
    docker compose up -d
    .venv/bin/python -m pytest -m db -v
"""

import os

import pytest

from adapters.db.connection import apply_schema, connect
from adapters.db.document_store import PgDocumentStore
from core.ports import DocumentStore
from core.types import EMBEDDING_DIM, Chunk, Clause, Document

pytestmark = pytest.mark.db

DSN = os.environ.get("SECUAGENT_DSN", "postgresql://secuagent:secuagent@localhost:5433/secuagent")


@pytest.fixture
def store():
    conn = connect(DSN)
    apply_schema(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE documents RESTART IDENTITY CASCADE")
    conn.commit()
    yield PgDocumentStore(conn)
    conn.close()


def _문서(path="data/raw/a.pdf", clearance=1, depts=()) -> Document:
    return Document(
        id=0,
        title="테스트 문서",
        source_path=path,
        doc_type="pdf",
        required_clearance=clearance,
        allowed_departments=depts,
    )


def _벡터(seed: float = 0.1) -> list[float]:
    return [seed] * EMBEDDING_DIM


def test_구현이_포트를_만족한다(store):
    assert isinstance(store, DocumentStore)


def test_문서를_저장하고_id_를_돌려준다(store):
    doc_id = store.upsert_document(_문서())
    assert doc_id > 0


def test_같은_경로를_두_번_넣어도_행이_늘지_않는다(store):
    first = store.upsert_document(_문서())
    second = store.upsert_document(_문서())
    assert first == second
    with store.conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM documents")
        assert cur.fetchone()[0] == 1


def test_권한_컬럼이_저장된다(store):
    doc_id = store.upsert_document(_문서(clearance=3, depts=("인사팀",)))
    with store.conn.cursor() as cur:
        cur.execute(
            "SELECT required_clearance, allowed_departments FROM documents WHERE id = %s",
            (doc_id,),
        )
        assert cur.fetchone() == (3, ["인사팀"])


def test_허용부서가_비면_NULL_로_저장된다(store):
    # NULL = 전사 공개. 빈 배열과 구분해야 SQL 필터가 단순해진다.
    doc_id = store.upsert_document(_문서(depts=()))
    with store.conn.cursor() as cur:
        cur.execute("SELECT allowed_departments FROM documents WHERE id = %s", (doc_id,))
        assert cur.fetchone()[0] is None


def test_조항을_저장하고_코드_매핑을_돌려준다(store):
    doc_id = store.upsert_document(_문서())
    ids = store.insert_clauses(doc_id, [
        Clause(code="1.1.1", title="가", text="본문 가"),
        Clause(code="2.6.1", title="나", text="본문 나"),
    ])
    assert set(ids) == {"1.1.1", "2.6.1"}


def test_청크와_벡터를_저장한다(store):
    doc_id = store.upsert_document(_문서())
    ids = store.insert_clauses(doc_id, [Clause(code="1.1.1", title="가", text="본문")])
    n = store.insert_chunks(
        doc_id, ids,
        [Chunk(clause_code="1.1.1", ordinal=0, text="청크 본문")],
        [_벡터()],
    )
    assert n == 1
    assert store.count_chunks() == 1


def test_조항_밖_청크도_저장된다(store):
    # 표지·목차는 조항이 없다. clause_id 가 NULL 이어야 한다.
    doc_id = store.upsert_document(_문서())
    store.insert_chunks(doc_id, {}, [Chunk(clause_code=None, ordinal=0, text="목차")], [_벡터()])
    with store.conn.cursor() as cur:
        cur.execute("SELECT clause_id FROM chunks")
        assert cur.fetchone()[0] is None


def test_전문검색_벡터가_채워진다(store):
    # text_tsv 가 비면 키워드 검색이 조용히 0건을 낸다.
    doc_id = store.upsert_document(_문서())
    store.insert_chunks(
        doc_id, {}, [Chunk(clause_code=None, ordinal=0, text="네트워크 접근 통제")], [_벡터()]
    )
    with store.conn.cursor() as cur:
        cur.execute("SELECT text_tsv IS NOT NULL FROM chunks")
        assert cur.fetchone()[0] is True


def test_문서를_지우면_조항과_청크도_지워진다(store):
    doc_id = store.upsert_document(_문서())
    ids = store.insert_clauses(doc_id, [Clause(code="1.1.1", title="가", text="본문")])
    store.insert_chunks(
        doc_id, ids, [Chunk(clause_code="1.1.1", ordinal=0, text="청크")], [_벡터()]
    )
    with store.conn.cursor() as cur:
        cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
    store.conn.commit()
    assert store.count_chunks() == 0

"""실제 데이터베이스가 필요한 테스트.

기본 스위트에서 제외된다(pyproject 의 addopts). 돌리려면:
    docker compose up -d
    .venv/bin/python -m pytest -m db -v
"""

import os

import psycopg
import pytest

from adapters.db.connection import apply_schema, connect
from adapters.db.document_store import PgDocumentStore
from core.ports import DocumentStore
from core.types import EMBEDDING_DIM, Chunk, Clause, Document, Principal

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
    ids = store.insert_clauses(
        doc_id,
        [
            Clause(code="1.1.1", title="가", text="본문 가"),
            Clause(code="2.6.1", title="나", text="본문 나"),
        ],
    )
    assert set(ids) == {"1.1.1", "2.6.1"}


def test_청크와_벡터를_저장한다(store):
    doc_id = store.upsert_document(_문서())
    ids = store.insert_clauses(doc_id, [Clause(code="1.1.1", title="가", text="본문")])
    n = store.insert_chunks(
        doc_id,
        ids,
        [Chunk(clause_code="1.1.1", ordinal=0, text="청크 본문")],
        [_벡터()],
    )
    assert n == 1
    assert store.count_all_chunks() == 1


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
    assert store.count_all_chunks() == 0


def test_삽입_실패_후_커넥션이_다음_작업에_쓸_수_있다(store):
    # insert_chunks 가 차원이 다른 벡터로 실패하면 psycopg.errors.DataException 이 난다.
    # 롤백이 없으면 커넥션이 aborted 상태로 남아 다음 문서의 upsert_document 까지
    # InFailedSqlTransaction 으로 죽는다 — 배치 적재에서 원인이 아닌 문서까지 실패한다.
    doc_id = store.upsert_document(_문서())
    with pytest.raises(psycopg.errors.DataException):
        store.insert_chunks(
            doc_id, {}, [Chunk(clause_code=None, ordinal=0, text="깨진 벡터")], [[0.1, 0.2, 0.3]]
        )

    # 롤백이 됐다면 커넥션은 멀쩡하고, 다음 문서는 정상적으로 저장돼야 한다.
    다음_id = store.upsert_document(_문서(path="data/raw/b.pdf"))
    assert 다음_id > 0


def test_재분류하면_기존_행이_새_등급으로_갱신된다(store):
    # DO UPDATE 가 DO NOTHING 으로 퇴행하면, 기밀로 재분류된 문서가 옛
    # 허용 등급을 그대로 유지하게 된다 — 이 시스템이 막으려는 바로 그 실패다.
    첫_id = store.upsert_document(_문서(clearance=1, depts=()))
    둘째_id = store.upsert_document(_문서(clearance=3, depts=("보안팀",)))
    assert 첫_id == 둘째_id

    with store.conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM documents")
        assert cur.fetchone()[0] == 1

        cur.execute(
            "SELECT required_clearance, allowed_departments FROM documents WHERE id = %s",
            (첫_id,),
        )
        assert cur.fetchone() == (3, ["보안팀"])


def test_청크를_지우면_문서와_조항은_남는다(store):
    doc_id = store.upsert_document(_문서())
    ids = store.insert_clauses(doc_id, [Clause(code="2.6.1", title="가", text="본문")])
    store.insert_chunks(
        doc_id, ids, [Chunk(clause_code="2.6.1", ordinal=0, text="청크")], [_벡터()]
    )

    assert store.delete_chunks(doc_id) == 1
    assert store.count_all_chunks() == 0

    # 문서와 조항은 살아 있어야 한다 — 재적재가 새 조항 id 를 만들면
    # 기존 인용(조항 코드)이 가리키던 행이 사라진다.
    with store.conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM documents WHERE id = %s", (doc_id,))
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM clauses WHERE document_id = %s", (doc_id,))
        assert cur.fetchone()[0] == 1


def test_같은_문서를_두_번_적재해도_청크가_늘지_않는다(store):
    def 적재():
        doc_id = store.upsert_document(_문서())
        store.delete_chunks(doc_id)
        ids = store.insert_clauses(doc_id, [Clause(code="2.6.1", title="가", text="본문")])
        store.insert_chunks(
            doc_id, ids, [Chunk(clause_code="2.6.1", ordinal=0, text="청크")], [_벡터()]
        )

    적재()
    적재()
    assert store.count_all_chunks() == 1


def test_같은_이름의_계정을_두_번_넣으면_갱신된다(store):
    """시연 계정 시드를 여러 번 돌려도 행이 늘면 안 된다.

    principals.name 에 UNIQUE 가 걸려 있어 ON CONFLICT 가 동작해야 한다.
    """
    with store.conn.cursor() as cur:
        for 등급 in (1, 3):
            cur.execute(
                "INSERT INTO principals (name, department, clearance) VALUES (%s, %s, %s) "
                "ON CONFLICT (name) DO UPDATE SET clearance = EXCLUDED.clearance",
                ("김개발", "개발팀", 등급),
            )
        cur.execute("SELECT count(*), max(clearance) FROM principals WHERE name = '김개발'")
        개수, 등급 = cur.fetchone()
    store.conn.commit()
    assert (개수, 등급) == (1, 3)


def test_주체를_이름으로_찾는다(store):
    from adapters.db.principal_store import PgPrincipalStore
    from core.ports import PrincipalStore

    with store.conn.cursor() as cur:
        cur.execute(
            "INSERT INTO principals (name, department, clearance) VALUES (%s, %s, %s) "
            "ON CONFLICT (name) DO UPDATE SET clearance = EXCLUDED.clearance",
            ("박인사", "인사팀", 2),
        )
    store.conn.commit()

    저장소 = PgPrincipalStore(store.conn)
    assert isinstance(저장소, PrincipalStore)
    assert 저장소.find("박인사") == Principal(department="인사팀", clearance=2)
    assert 저장소.find("없는사람") is None

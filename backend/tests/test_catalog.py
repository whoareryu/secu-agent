"""문서·계정 목록 어댑터. 읽기 전용이라 코퍼스를 파괴하지 않는다."""

import psycopg
import pytest

from adapters.db.catalog import PgDocumentCatalog
from core.ports import DocumentCatalog

pytestmark = pytest.mark.corpus


@pytest.fixture
def catalog(작업DB_읽기전용):
    yield PgDocumentCatalog(작업DB_읽기전용)


def test_구현이_포트를_만족한다(catalog):
    assert isinstance(catalog, DocumentCatalog)


def test_문서_목록이_등급과_부서를_담는다(catalog):
    docs = catalog.documents()
    assert docs, "코퍼스가 비어 있다 — 적재 후 다시 돌린다"
    개발팀문서 = [d for d in docs if "개발팀" in d.allowed_departments]
    assert 개발팀문서, "부서 제한 문서가 없다"
    assert all(isinstance(d.required_clearance, int) for d in docs)


def test_전사_공개는_빈_튜플이다(catalog):
    """NULL 을 빈 튜플로 정규화한다 — core 의 규칙이 빈 튜플을 전사 공개로 읽는다."""
    docs = catalog.documents()
    전사 = [d for d in docs if d.allowed_departments == ()]
    assert 전사, "전사 공개 문서가 없다"


def test_청크_수가_함께_온다(catalog):
    assert all(d.chunk_count >= 0 for d in catalog.documents())
    assert sum(d.chunk_count for d in catalog.documents()) > 0


def test_계정_목록을_읽는다(catalog):
    names = {p.name for p in catalog.principals()}
    assert {"김개발", "박인사", "최임원"} <= names


def test_목록에_본문이_없다(catalog):
    """목록 응답에 본문이 섞이면 이 엔드포인트가 우회 경로가 된다."""
    import dataclasses

    from core.types import DocumentRow

    필드 = {f.name for f in dataclasses.fields(DocumentRow)}
    for 금지 in ("text", "body", "content", "chunks"):
        assert 금지 not in 필드


def test_작업DB_연결로는_쓸_수_없다(작업DB_읽기전용):
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        with 작업DB_읽기전용.cursor() as cur:
            cur.execute("CREATE TEMP TABLE 쓰기시도 (x int)")
    작업DB_읽기전용.rollback()


@pytest.mark.corpus
def test_계정_목록이_역할을_싣는다(catalog):
    """프론트가 역할을 서버에서만 얻도록 하려면 이 응답에 있어야 한다."""
    이름별 = {p.name: p for p in catalog.principals()}
    assert 이름별["남감사"].role == "auditor"
    assert 이름별["정개발"].role == "developer"
    assert 이름별["김개발"].role == "member"

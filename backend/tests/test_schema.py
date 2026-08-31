import re
from pathlib import Path

from core.types import EMBEDDING_DIM

SCHEMA = Path("db/schema.sql").read_text(encoding="utf-8")


def _컬럼_목록(테이블: str) -> str:
    m = re.search(
        rf"CREATE TABLE (?:IF NOT EXISTS )?{테이블}\s*\((.*?)\n\);",
        SCHEMA,
        re.DOTALL | re.IGNORECASE,
    )
    assert m, f"{테이블} 테이블 정의를 찾을 수 없다"
    return m.group(1)


def test_다섯_개_테이블이_정의돼_있다():
    for t in ("documents", "clauses", "chunks", "log_events", "principals"):
        assert _컬럼_목록(t)


def test_벡터_차원이_EMBEDDING_DIM_과_일치한다():
    # 한쪽만 바꾸면 적재는 되는데 pgvector 가 차원 불일치로 실패한다.
    선언 = re.findall(r"vector\((\d+)\)", SCHEMA)
    assert 선언, "vector(N) 선언을 찾을 수 없다"
    assert all(int(n) == EMBEDDING_DIM for n in 선언), (
        f"schema 의 차원 {선언} 이 EMBEDDING_DIM({EMBEDDING_DIM}) 과 다르다"
    )


def test_권한_컬럼이_documents_에_있다():
    # 이 두 컬럼이 사전 필터링의 WHERE 절이 된다(spec 5.1).
    본문 = _컬럼_목록("documents")
    assert "required_clearance" in 본문
    assert "allowed_departments" in 본문


def test_HNSW_와_GIN_인덱스가_있다():
    assert "using hnsw" in SCHEMA.lower()
    assert "using gin" in SCHEMA.lower()


def test_권한_필터_컬럼에_인덱스가_있다():
    # 사전 필터링은 WHERE 가 먼저 적용되므로 이 인덱스가 없으면 느려지고,
    # 느려지는 정도가 권한에 따라 달라지면 타이밍 누출이 된다(spec 5.2).
    assert re.search(r"CREATE INDEX.*documents.*required_clearance", SCHEMA, re.IGNORECASE)


def test_같은_문서를_두_번_넣지_못하게_막는_제약이_있다():
    본문 = _컬럼_목록("documents")
    assert "UNIQUE (source_path)" in 본문 or "UNIQUE(source_path)" in 본문

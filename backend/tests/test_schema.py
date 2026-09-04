import re
from pathlib import Path

import psycopg
import pytest

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
    # by_vector 는 이 컬럼으로 거른 집합을 AS MATERIALIZED CTE 로 먼저
    # 확정한 뒤 그 위에서 정렬한다 — 스캔 비용이 등급과 무관하게 상수라
    # 타이밍 누출은 이미 구조로 막혀 있다. 이 인덱스는 그 상수 비용
    # 자체를 낮추는 성능 목적이다.
    assert re.search(r"CREATE INDEX.*documents.*required_clearance", SCHEMA, re.IGNORECASE)


def test_같은_문서를_두_번_넣지_못하게_막는_제약이_있다():
    본문 = _컬럼_목록("documents")
    assert "UNIQUE (source_path)" in 본문 or "UNIQUE(source_path)" in 본문


@pytest.mark.db
def test_hosts_테이블이_있다(db연결):
    with db연결.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'hosts'
        """)
        컬럼 = {r[0] for r in cur.fetchall()}
    assert {"name", "department", "required_clearance", "allowed_departments"} <= 컬럼


@pytest.mark.db
def test_log_events_의_host_가_hosts_를_참조한다(db연결):
    """외래키가 있으면 미등록 호스트의 이벤트가 애초에 들어가지 않는다.

    조회 시점의 INNER JOIN 은 그 다음 방어선이다 — 둘 다 있어야 한다.
    """
    with db연결.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = 'log_events'
              AND tc.constraint_type = 'FOREIGN KEY'
              AND kcu.column_name = 'host'
        """)
        assert cur.fetchone()[0] == 1


@pytest.mark.db
def test_principals_에_role_컬럼이_있다(db연결):
    """역할을 서버가 정한다는 불변식이 이 컬럼에 걸려 있다.

    프론트에 이름→역할 맵을 두면 권한 판정의 네 번째 사본이 된다(스펙 §2.1).
    """
    with db연결.cursor() as cur:
        cur.execute(
            "SELECT data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'principals' AND column_name = 'role'"
        )
        row = cur.fetchone()
    assert row is not None, "principals.role 이 없다"
    assert row == ("text", "NO")


@pytest.mark.db
def test_role_은_정해진_셋만_받는다(db연결):
    """오타 하나가 조용히 새 역할을 만들면 guard 가 그 값을 모른 채 통과시킨다."""
    with db연결.cursor() as cur:
        cur.execute("TRUNCATE principals RESTART IDENTITY CASCADE")
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO principals (name, department, clearance, role) "
                "VALUES ('x', '개발팀', 1, 'superuser')"
            )
    db연결.rollback()


@pytest.mark.db
def test_access_records_에_session_id_가_있다(db연결):
    """내 브라우저의 질의와 남의 것을 가르는 유일한 값이다(스펙 §2.4).

    NULL 을 허용한다 — 이 컬럼이 생기기 전의 행이 이미 있다.
    """
    with db연결.cursor() as cur:
        cur.execute(
            "SELECT data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'access_records' AND column_name = 'session_id'"
        )
        row = cur.fetchone()
    assert row == ("text", "YES")

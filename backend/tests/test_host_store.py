"""PgHostStore — 어떤 테스트도 이 파일을 import 하지 않았다.

`-m db` 를 포함해 전부다. 로그 권한이 걸리는 축이 호스트인데(`log_search`
의 `권한_WHERE("h")`), 그 호스트를 넣는 코드가 무검증이었다.

특히 `list(host.allowed_departments) or None` 한 줄이 검증되지 않았다.
빈 튜플을 NULL 로 정규화하는 규칙인데, 이게 어긋나면 "전사 공개" 가
"아무도 못 봄" 으로 뒤집힌다 — 에러가 아니라 조용한 누락이라 발견이 늦다.
`core/access/visibility.py` 가 NULL 을 전사 공개로 읽기 때문이다.
"""

import pytest

from adapters.db.host_store import PgHostStore
from core.types import Host

pytestmark = pytest.mark.db


@pytest.fixture
def 저장소(db연결):
    with db연결.cursor() as cur:
        cur.execute("TRUNCATE log_events RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE hosts RESTART IDENTITY CASCADE")
    db연결.commit()
    return PgHostStore(db연결)


def _행(conn, 이름):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT department, required_clearance, allowed_departments FROM hosts WHERE name = %s",
            (이름,),
        )
        return cur.fetchone()


def test_넣고_이름으로_돌려받는다(저장소, db연결):
    저장소.upsert(
        Host(name="dev-web-01", department="개발팀", required_clearance=1, allowed_departments=())
    )

    assert 저장소.names() == {"dev-web-01"}


def test_허용_부서가_비면_NULL_로_들어간다(저장소, db연결):
    """**이 한 줄이 이 파일의 요점이다.**

    빈 배열로 들어가면 `'개발팀' = ANY('{}')` 가 언제나 거짓이라, 전사
    공개여야 할 호스트를 아무도 못 보게 된다. NULL 이어야 권한 SQL 의
    "부서 제한 없음" 분기를 탄다.
    """
    저장소.upsert(
        Host(
            name="vpn-gw-01", department="정보보안팀", required_clearance=1, allowed_departments=()
        )
    )

    부서, 등급, 허용 = _행(db연결, "vpn-gw-01")
    assert 허용 is None, "빈 튜플은 NULL 로 정규화돼야 한다 — 빈 배열이면 아무도 못 본다"
    assert (부서, 등급) == ("정보보안팀", 1)


def test_허용_부서가_있으면_그대로_들어간다(저장소, db연결):
    저장소.upsert(
        Host(
            name="hr-db-01",
            department="인사팀",
            required_clearance=2,
            allowed_departments=("인사팀",),
        )
    )

    _, _, 허용 = _행(db연결, "hr-db-01")
    assert 허용 == ["인사팀"]


def test_같은_이름은_덮어쓴다(저장소, db연결):
    """seed-hosts 를 두 번 돌려도 행이 늘지 않아야 한다."""
    저장소.upsert(
        Host(name="dev-web-01", department="개발팀", required_clearance=1, allowed_departments=())
    )
    저장소.upsert(
        Host(
            name="dev-web-01",
            department="정보보안팀",
            required_clearance=3,
            allowed_departments=("정보보안팀",),
        )
    )

    assert 저장소.names() == {"dev-web-01"}
    assert _행(db연결, "dev-web-01") == ("정보보안팀", 3, ["정보보안팀"])


def test_비어_있으면_빈_집합이다(저장소):
    """ingest_logs 가 미등록 호스트를 판정할 때 이 값을 쓴다 — None 이면 터진다."""
    assert 저장소.names() == set()

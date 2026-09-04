"""열람 기록 어댑터.

docker compose up -d
.venv/bin/python -m pytest -m db tests/test_access_log.py -v
"""

import pytest

from adapters.db.access_log import PgAccessLog
from core.ports import AccessLog
from core.types import AccessRecord

pytestmark = pytest.mark.db


@pytest.fixture
def log(db연결):
    conn = db연결
    with conn.cursor() as cur:
        cur.execute("TRUNCATE access_records RESTART IDENTITY")
    conn.commit()
    yield PgAccessLog(conn)


def _rec(resource_id=1, allowed=True, code="2.6.1", persona="김개발", kind="chunk"):
    return AccessRecord(
        persona=persona,
        department="개발팀",
        clearance=1,
        query="네트워크 접근 통제",
        clause_code=code,
        resource_kind=kind,
        resource_id=resource_id,
        allowed=allowed,
    )


def test_구현이_포트를_만족한다(log):
    assert isinstance(log, AccessLog)


def test_기록하고_다시_읽는다(log):
    assert log.record([_rec(1), _rec(2)]) == 2
    읽은 = log.recent(10)
    assert {r.resource_id for r in 읽은} == {1, 2}


def test_빈_목록은_아무것도_하지_않는다(log):
    assert log.record([]) == 0
    assert log.recent(10) == []


def test_최근_것이_먼저_온다(log):
    log.record([_rec(1)])
    log.record([_rec(2)])
    assert log.recent(10)[0].resource_id == 2


def test_위반만_따로_읽는다(log):
    log.record([_rec(1, allowed=True), _rec(2, allowed=False)])
    위반 = log.violations(10)
    assert [r.resource_id for r in 위반] == [2]
    assert all(r.allowed is False for r in 위반)


def test_같은_id_의_청크_기록과_로그_기록이_구별된다(log):
    """resource_kind 가 컬럼으로 살아 있는지 어댑터 왕복으로 확인한다.

    청크 id 와 로그 이벤트 id 는 겹친다(청크 1..338, 로그 이벤트 1..33).
    종류가 저장되지 않으면 두 행이 같은 것으로 읽히고, 관리자 화면이 로그
    이벤트 id 를 청크로 푼다.
    """
    log.record([_rec(7, kind="chunk"), _rec(7, kind="log_event", allowed=False)])
    읽은 = log.recent(10)
    assert {(r.resource_kind, r.resource_id) for r in 읽은} == {
        ("chunk", 7),
        ("log_event", 7),
    }
    assert [r.resource_kind for r in log.violations(10)] == ["log_event"]


def test_기록에_본문_컬럼이_없다(log):
    """스키마에 본문·제목 컬럼이 있으면 언젠가 채워진다.

    기록이 문서 본문이나 제목을 담으면 그 테이블이 곧 권한 우회 경로가 된다 —
    제목만으로도 존재가 드러난다.
    """
    with log.conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'access_records'"
        )
        컬럼 = {r[0] for r in cur.fetchall()}
    for 금지 in ("text", "doc_title", "title", "body", "content"):
        assert 금지 not in 컬럼, f"기록 스키마에 {금지} 컬럼이 있다"


@pytest.mark.db
def test_세션_id_가_저장되고_되돌아온다(db연결):
    """어느 브라우저가 남긴 기록인지가 마스킹의 유일한 근거다."""
    로그 = PgAccessLog(db연결)
    with db연결.cursor() as cur:
        cur.execute("TRUNCATE access_records RESTART IDENTITY")
    db연결.commit()

    로그.record(
        [
            AccessRecord(
                persona="김개발",
                department="개발팀",
                clearance=1,
                query="질의",
                clause_code="2.6.1",
                resource_kind="chunk",
                resource_id=1,
                allowed=True,
                session_id="sess-a",
            )
        ]
    )

    행 = 로그.recent(10)
    assert len(행) == 1
    assert 행[0].session_id == "sess-a"


@pytest.mark.db
def test_세션_없이_기록해도_터지지_않는다(db연결):
    """이 컬럼이 생기기 전의 경로가 남아 있을 수 있다. NULL 로 들어간다."""
    로그 = PgAccessLog(db연결)
    with db연결.cursor() as cur:
        cur.execute("TRUNCATE access_records RESTART IDENTITY")
    db연결.commit()

    로그.record(
        [
            AccessRecord(
                persona="김개발",
                department="개발팀",
                clearance=1,
                query="질의",
                clause_code=None,
                resource_kind="chunk",
                resource_id=1,
                allowed=True,
            )
        ]
    )

    assert 로그.recent(10)[0].session_id is None

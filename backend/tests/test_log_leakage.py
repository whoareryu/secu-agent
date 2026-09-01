"""로그 누출 테스트 — 사후 필터링이면 반드시 실패한다.

문서 쪽 test_leakage.py 의 로그판이다. 다만 잡아내는 것이 다르다.

문서: 결과 개수가 등급에 따라 달라지면 존재가 누출된다.
로그: 개수가 달라지는 것은 **정상이다**(개수 자체가 답이므로).
      잡아야 하는 것은 **권한 있는 이벤트가 잘려나가는 것**이다.

픽스처의 핵심: **권한 밖 호스트의 이벤트를 가장 최근 것으로 심는다.**
사후 필터링으로 짜면 — 최근 N건을 뽑고 나서 거르면 — 낮은 등급 주체는
2건만 받고 나머지가 조용히 사라진다.
"""

from datetime import datetime, timedelta

import pytest

from adapters.db.log_search import PgLogSearch
from core.types import Principal

pytestmark = pytest.mark.db

개발자 = Principal(department="개발팀", clearance=1)
임원 = Principal(department="경영지원팀", clearance=3)

# 권한 밖 이벤트 수. limit 보다 커야 사후 필터링이 결과를 0 에 가깝게 만든다.
_제한_이벤트 = 20
_허용_이벤트 = 20
_기준시각 = datetime(2026, 9, 1, 0, 0, 0)


@pytest.fixture
def 로그코퍼스(db연결):
    """허용 호스트의 오래된 이벤트 20건 + 권한 밖 호스트의 **최근** 이벤트 20건.

    최근 20건이 전부 권한 밖이라는 것이 이 픽스처의 전부다. 사후
    필터링이면 limit=10 요청이 0건을 돌려준다.
    """
    with db연결.cursor() as cur:
        cur.execute("TRUNCATE log_events RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE hosts RESTART IDENTITY CASCADE")
        cur.executemany(
            "INSERT INTO hosts (name, department, required_clearance, allowed_departments)"
            " VALUES (%s,%s,%s,%s)",
            [
                ("open-01", "개발팀", 1, None),  # 전사 공개
                ("exec-01", "경영지원팀", 3, None),  # 등급 3 필요
            ],
        )
        행 = []
        for i in range(_허용_이벤트):  # 오래된 것
            행.append(
                (
                    _기준시각 - timedelta(hours=100 - i),
                    "open-01",
                    "sshd",
                    "auth_failure",
                    "devuser",
                    f"open {i}",
                    None,
                )
            )
        for i in range(_제한_이벤트):  # 최근 것
            행.append(
                (
                    _기준시각 - timedelta(minutes=_제한_이벤트 - i),
                    "exec-01",
                    "sshd",
                    "auth_failure",
                    "execuser",
                    f"exec {i}",
                    None,
                )
            )
        cur.executemany(
            "INSERT INTO log_events (ts, host, process, event_type, principal_name, raw, severity)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s)",
            행,
        )
    db연결.commit()
    return db연결


# ───────────────────── 누출 경로 ① 허용 데이터의 절단 ─────────────────────


def test_권한_밖_이벤트가_최근이어도_허용_이벤트가_잘리지_않는다(로그코퍼스):
    """**이 테스트가 사후 필터링을 잡는다.**

    최근 20건이 전부 권한 밖이다. 사후 필터링이면 상위 10건을 뽑고 거른
    뒤 0건이 남는다. 사전 필터링이면 허용 이벤트에서 10건이 온다.
    """
    검색 = PgLogSearch(로그코퍼스)
    결과 = 검색.query(개발자, event_type=None, since=None, limit=10)
    assert len(결과) == 10, (
        f"허용 이벤트가 20건 있는데 {len(결과)}건만 왔다. "
        "권한 필터가 ORDER BY 뒤에 있다 — 사후 필터링이다."
    )
    assert all(e.host == "open-01" for e in 결과)


def test_부서_제한이_없는_픽스처에서_등급_3_은_최근_이벤트를_받는다(로그코퍼스):
    """대조군. 위 테스트가 '항상 open-01' 이라서 통과하는 것이 아님을 보인다.

    이름에 픽스처 조건을 적는다. 두 호스트 모두 allowed_departments 가 NULL
    (전사 공개)이라 여기서는 등급만 갈린다. 권한은 등급 ∧ 부서의 격자이지
    사다리가 아니므로(스펙 2.1), "등급이 높으면 더 받는다" 는 일반 주장은
    이 픽스처가 보이는 것보다 넓다 — 부서가 다르면 등급 3 도 못 본다.
    """
    검색 = PgLogSearch(로그코퍼스)
    결과 = 검색.query(임원, event_type=None, since=None, limit=10)
    assert len(결과) == 10
    assert all(e.host == "exec-01" for e in 결과), "임원에게는 최근 것이 exec-01 이다"


# ───────────────────── 누출 경로 ② 권한 밖 내용 ─────────────────────


def test_권한_밖_호스트의_이벤트가_한_건도_섞이지_않는다(로그코퍼스):
    검색 = PgLogSearch(로그코퍼스)
    결과 = 검색.query(개발자, event_type=None, since=None, limit=200)
    assert len(결과) == _허용_이벤트
    assert not any(e.host == "exec-01" for e in 결과)
    assert not any("exec" in e.raw for e in 결과), "raw 로도 새면 안 된다"


def test_등록되지_않은_호스트의_이벤트는_아무에게도_보이지_않는다(로그코퍼스):
    """외래키를 우회해 직접 써넣어도 조회에서 닫힌다.

    INNER JOIN 이라 권한 행이 없으면 이벤트 행도 없다 — 검사가 아니라
    구조로 보장된다(보충 spec 결정 14).
    """
    with 로그코퍼스.cursor() as cur:
        cur.execute("ALTER TABLE log_events DROP CONSTRAINT IF EXISTS log_events_host_fkey")
        cur.execute(
            "INSERT INTO log_events (ts, host, event_type, raw)"
            " VALUES (%s,'ghost-99','auth_failure','유령')",
            (_기준시각,),
        )
    로그코퍼스.commit()
    try:
        검색 = PgLogSearch(로그코퍼스)
        for p in (개발자, 임원):
            결과 = 검색.query(p, event_type=None, since=None, limit=200)
            assert not any(e.host == "ghost-99" for e in 결과)
    finally:
        with 로그코퍼스.cursor() as cur:
            cur.execute("DELETE FROM log_events WHERE host = 'ghost-99'")
            cur.execute(
                "ALTER TABLE log_events ADD CONSTRAINT log_events_host_fkey"
                " FOREIGN KEY (host) REFERENCES hosts(name)"
            )
        로그코퍼스.commit()


# ───────────────────── 필터가 권한을 우회하지 않는다 ─────────────────────


def test_event_type_필터가_권한을_우회하지_않는다(로그코퍼스):
    검색 = PgLogSearch(로그코퍼스)
    결과 = 검색.query(개발자, event_type="auth_failure", since=None, limit=200)
    assert not any(e.host == "exec-01" for e in 결과)


def test_since_필터가_권한을_우회하지_않는다(로그코퍼스):
    """권한 밖 이벤트만 있는 시간 구간을 물어도 빈 결과여야 한다 —
    '그 구간에 뭔가 있다'가 새면 안 된다.
    """
    검색 = PgLogSearch(로그코퍼스)
    결과 = 검색.query(개발자, event_type=None, since=_기준시각 - timedelta(minutes=30), limit=200)
    assert 결과 == []


def test_limit_상한이_있어도_권한이_먼저다(로그코퍼스):
    검색 = PgLogSearch(로그코퍼스)
    결과 = 검색.query(개발자, event_type=None, since=None, limit=1)
    assert len(결과) == 1
    assert 결과[0].host == "open-01"


def test_돌려주는_이벤트가_호스트_권한을_들고_온다(로그코퍼스):
    """재검증이 DB 를 다시 부르지 않게 하기 위해서다."""
    검색 = PgLogSearch(로그코퍼스)
    결과 = 검색.query(임원, event_type=None, since=None, limit=1)
    assert 결과[0].required_clearance == 3

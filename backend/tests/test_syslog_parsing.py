"""syslog 파서.

형식은 진짜다 — 합성 코퍼스를 쓰더라도 파서는 실물 sshd/sudo 로그를
파싱해야 한다. 그래야 "형식은 진짜, 내용은 합성" 이라는 문서 코퍼스와
같은 구조가 된다(상위 spec §10).
"""

from datetime import datetime

import pytest

from adapters.parsing.syslog import parse_line

인증실패 = (
    "Sep  1 03:14:22 dev-web-01 sshd[4412]: Failed password for invalid user "
    "admin from 10.0.3.19 port 51422 ssh2"
)
세션열림 = (
    "Sep  1 03:20:01 hr-app-01 sshd[4510]: Accepted publickey for parkhr "
    "from 10.0.1.7 port 40122 ssh2"
)
권한상승 = (
    "Sep  1 09:02:11 sec-log-01 sudo:  choiexec : TTY=pts/0 ; PWD=/var/log "
    "; USER=root ; COMMAND=/bin/cat audit.log"
)


def test_인증_실패를_읽는다():
    e = parse_line(인증실패, year=2026)
    assert e is not None
    assert e.ts == datetime(2026, 9, 1, 3, 14, 22)
    assert e.host == "dev-web-01"
    assert e.process == "sshd"
    assert e.event_type == "auth_failure"
    assert e.principal_name == "admin"
    assert e.raw == 인증실패, "원본을 그대로 보존해야 한다"


def test_세션_열림을_읽는다():
    e = parse_line(세션열림, year=2026)
    assert e.event_type == "session_open"
    assert e.principal_name == "parkhr"
    assert e.host == "hr-app-01"


def test_권한_상승을_읽는다():
    e = parse_line(권한상승, year=2026)
    assert e.event_type == "privilege_use"
    assert e.principal_name == "choiexec"
    assert e.process == "sudo"


def test_연도를_추측하지_않는다():
    """syslog 에는 연도가 없다. 인자로 받는다 — 지어내지 않는다."""
    a = parse_line(인증실패, year=2025)
    b = parse_line(인증실패, year=2026)
    assert a.ts.year == 2025
    assert b.ts.year == 2026


def test_알아보지_못하는_줄은_None_을_돌려준다():
    assert parse_line("무의미한 줄", year=2026) is None
    assert parse_line("", year=2026) is None


def test_형식은_맞지만_유형을_모르면_other_로_읽는다():
    """모르는 것을 버리지 않는다 — raw 는 남고 event_type 만 other 다.

    버리면 그 줄이 있었다는 사실 자체가 사라진다.
    """
    줄 = "Sep  1 04:00:00 dev-web-01 cron[900]: (root) CMD (run-parts /etc/cron.hourly)"
    e = parse_line(줄, year=2026)
    assert e is not None
    assert e.event_type == "other"
    assert e.raw == 줄


def test_사용자를_못_찾으면_None_이지_빈_문자열이_아니다():
    줄 = "Sep  1 04:00:00 dev-web-01 kernel: [12345.6] eth0: link up"
    e = parse_line(줄, year=2026)
    assert e.principal_name is None


@pytest.mark.parametrize(
    "줄",
    [
        "Feb 30 03:14:22 dev-web-01 sshd[4412]: Failed password for root",
        "Jan 99 03:14:22 dev-web-01 sshd[4412]: Failed password for root",
        "Sep  1 25:00:00 dev-web-01 sshd[4412]: Failed password for root",
        "Sep  1 12:60:00 dev-web-01 sshd[4412]: Failed password for root",
    ],
)
def test_자릿수는_맞지만_존재하지_않는_시각은_None(줄: str):
    """정규식은 자릿수만 본다 — 값의 범위는 datetime 이 안다.

    던지게 두면 pipeline/ingest_logs.py 가 줄들을 한 번에 평가하므로
    손상된 줄 하나가 파일 전체의 적재를 원인 불명의 ValueError 로 죽인다.
    독스트링의 약속("형식이 아니면 None")대로 그 줄만 건너뛴다.
    """
    assert parse_line(줄, 2026) is None

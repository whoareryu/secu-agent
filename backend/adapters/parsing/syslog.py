"""syslog 한 줄 → 구조화된 이벤트.

**event_type 은 줄이 문자 그대로 말하는 것만 읽는다.** "Failed password"
가 있으면 auth_failure 다. 이것은 판단이 아니라 파싱이다.

어떤 event_type 이 어느 조항 위반인가는 여기서 정하지 않는다 — 그것은
보안 담당자의 판단이고, 추측을 표에 굳혀 정답처럼 내놓지 않는다는 것이
보충 spec 결정 15 다. 에이전트가 search_policy 로 찾고 verify_clauses 가
인용의 실재를 검증한다.
"""

import re
from dataclasses import dataclass
from datetime import datetime

# "Sep  1 03:14:22 dev-web-01 sshd[4412]: 나머지"
# 날짜의 일(day)은 한 자리일 때 공백으로 채워진다 — %e 가 아니라 정규식으로 받는다.
_줄 = re.compile(
    r"^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+"
    r"(?P<proc>[A-Za-z0-9_\-]+)(?:\[(?P<pid>\d+)\])?:\s*"
    r"(?P<msg>.*)$"
)

_월 = {
    m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), start=1)
}

# 메시지 본문에서 유형과 사용자명을 읽는다. 순서가 의미를 갖는다 —
# 먼저 맞는 것이 이긴다.
_유형 = [
    ("auth_failure", re.compile(r"Failed password for (?:invalid user )?(?P<who>\S+)")),
    ("auth_failure", re.compile(r"authentication failure.*user=(?P<who>\S+)")),
    ("session_open", re.compile(r"Accepted \S+ for (?P<who>\S+)")),
    ("session_open", re.compile(r"session opened for user (?P<who>\S+)")),
    ("session_close", re.compile(r"session closed for user (?P<who>\S+)")),
    ("privilege_use", re.compile(r"^\s*(?P<who>\S+)\s*:\s*TTY=")),
    ("access_denied", re.compile(r"(?:Permission denied|access denied).*user (?P<who>\S+)")),
]


@dataclass(frozen=True)
class ParsedLine:
    """적재 직전의 이벤트. 호스트 권한은 아직 모른다 — 그건 hosts 가 갖는다."""

    ts: datetime
    host: str
    process: str | None
    event_type: str
    principal_name: str | None
    raw: str
    severity: str | None


def parse_line(line: str, year: int) -> ParsedLine | None:
    """syslog 한 줄을 읽는다. 형식이 아니면 None.

    year 를 인자로 받는 이유: syslog 형식에는 연도가 없다. 지금 연도로
    추측하면 연말에 적재한 작년 12월 로그가 내년 것이 된다.
    """
    m = _줄.match(line.rstrip("\n"))
    if not m:
        return None

    시 = datetime.strptime(m["time"], "%H:%M:%S")
    ts = datetime(year, _월[m["mon"]], int(m["day"]), 시.hour, 시.minute, 시.second)

    msg = m["msg"]
    event_type, who = "other", None
    for 유형, 패턴 in _유형:
        찾음 = 패턴.search(msg)
        if 찾음:
            event_type, who = 유형, 찾음["who"]
            break

    return ParsedLine(
        ts=ts,
        host=m["host"],
        process=m["proc"],
        event_type=event_type,
        principal_name=who,
        raw=line.rstrip("\n"),
        severity=None,  # syslog 우선순위는 이 형식에 없다. 지어내지 않는다.
    )

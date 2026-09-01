"""로그 적재.

**미등록 호스트를 거부한다.** 전원 공개로 취급하면 열리는 방향으로
실패하고, 조용히 건너뛰면 이벤트가 사라진 것을 아무도 모른다. 시끄럽게
막고 사람이 hosts 에 등록하게 한다(보충 spec 3.2).

거부는 **전부 아니면 전무**다. 부분 적재를 허용하면 어디까지 들어갔는지
알 수 없어 재실행이 위험해진다.
"""

from dataclasses import dataclass
from pathlib import Path

import psycopg

from adapters.db.host_store import PgHostStore
from adapters.parsing.syslog import parse_line


class MissingHost(Exception):
    """hosts 에 등록되지 않은 호스트가 로그에 있다."""


@dataclass(frozen=True)
class 적재결과:
    적재: int
    건너뜀: int  # 파싱되지 않은 줄. 조용히 버리지 않고 세어서 보고한다


def ingest_logs(path: Path, year: int, conn: psycopg.Connection) -> 적재결과:
    줄들 = path.read_text(encoding="utf-8").splitlines()
    파싱 = [parse_line(줄, year=year) for 줄 in 줄들]
    이벤트 = [e for e in 파싱 if e is not None]
    건너뜀 = len(파싱) - len(이벤트)

    등록됨 = PgHostStore(conn).names()
    미등록 = sorted({e.host for e in 이벤트} - 등록됨)
    if 미등록:
        raise MissingHost(
            f"hosts 에 없는 호스트: {', '.join(미등록)}. "
            "python -m pipeline.cli seed-hosts 로 먼저 등록한다."
        )

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO log_events (ts, host, process, event_type, principal_name, raw, severity)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
            """,
            [
                (e.ts, e.host, e.process, e.event_type, e.principal_name, e.raw, e.severity)
                for e in 이벤트
            ],
        )
    conn.commit()
    return 적재결과(적재=len(이벤트), 건너뜀=건너뜀)

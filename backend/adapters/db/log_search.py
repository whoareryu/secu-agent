"""LogSearch 의 psycopg 구현.

**INNER JOIN 이 이 파일의 핵심이다.** `WHERE` 절은 빼먹을 수 있지만
JOIN 을 빼먹으면 권한 컬럼이 없어 쿼리가 아예 성립하지 않는다. 권한 행이
없으면 이벤트 행도 없다 — 검사가 아니라 구조로 닫힌다(보충 spec 결정 14).

by_vector 와 달리 `AS MATERIALIZED` 가 필요 없다. 여기에는 근사 인덱스가
없다 — 정확한 필터와 정렬뿐이라, HNSW 처럼 후보가 잘려 사후 필터 결과가
0건이 되는 일이 없다. 형태를 맞추려고 CTE 를 넣지 않는다.
"""

from datetime import datetime

import psycopg

from adapters.db.permission_sql import 권한_WHERE
from core.types import LogEvent, Principal

_열 = """
    e.id, e.ts, e.host, e.process, e.event_type, e.principal_name, e.raw, e.severity,
    h.required_clearance, h.allowed_departments
"""

# 권한 조건이 ORDER BY 보다 먼저다. 이 문장을 모듈 상수로 두는 이유는 문서
# 쪽과 같다 — 테스트가 실제로 실행되는 문장을 검사할 수 있어야 한다.
#
# NULLS LAST 를 붙인 이유: log_events.ts 는 nullable 이고 DESC 의 기본은
# NULLS FIRST 다. 시각을 모르는 행이 모든 결과의 첫 줄에 오면 "최근" 이
# 거짓이 된다.
_조회_SQL = f"""
    SELECT {_열}
    FROM log_events e
    JOIN hosts h ON h.name = e.host
    WHERE {권한_WHERE("h")}
      AND (%(event_type)s::text IS NULL OR e.event_type = %(event_type)s)
      AND (%(since)s::timestamptz IS NULL OR e.ts >= %(since)s)
    ORDER BY e.ts DESC NULLS LAST, e.id DESC
    LIMIT %(limit)s
"""


class PgLogSearch:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def query(
        self,
        principal: Principal,
        event_type: str | None,
        since: datetime | None,
        limit: int,
    ) -> list[LogEvent]:
        with self.conn.cursor() as cur:
            cur.execute(
                _조회_SQL,
                {
                    "clearance": principal.clearance,
                    "dept": principal.department,
                    "event_type": event_type,
                    "since": since,
                    "limit": limit,
                },
            )
            return [
                LogEvent(
                    id=r[0], ts=r[1], host=r[2], process=r[3], event_type=r[4],
                    principal_name=r[5], raw=r[6], severity=r[7],
                    required_clearance=r[8],
                    # NULL(전사 공개)을 빈 튜플로 정규화한다 — core 쪽 규칙이
                    # 빈 튜플을 전사 공개로 읽는다.
                    allowed_departments=tuple(r[9] or ()),
                )
                for r in cur.fetchall()
            ]

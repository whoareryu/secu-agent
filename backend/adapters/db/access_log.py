"""AccessLog 의 psycopg 구현.

기록은 요청 처리의 곁가지다 — 실패해도 요청을 죽이면 안 된다. 예외를
삼키는 것은 호출자(api/main.py)의 몫이고, 여기서는 정직하게 던진다.
"""

from collections.abc import Sequence

import psycopg

from core.types import AccessRecord

_삽입_열 = "persona, department, clearance, query, clause_code, resource_kind, resource_id, allowed"
_조회_열 = _삽입_열 + ", ts"


def _행에서(row) -> AccessRecord:
    return AccessRecord(
        persona=row[0],
        department=row[1],
        clearance=row[2],
        query=row[3],
        clause_code=row[4],
        resource_kind=row[5],
        resource_id=row[6],
        allowed=row[7],
        ts=row[8],
    )


class PgAccessLog:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def record(self, rows: Sequence[AccessRecord]) -> int:
        if not rows:
            return 0
        try:
            with self.conn.cursor() as cur:
                cur.executemany(
                    f"INSERT INTO access_records ({_삽입_열}) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    [
                        (
                            r.persona,
                            r.department,
                            r.clearance,
                            r.query,
                            r.clause_code,
                            r.resource_kind,
                            r.resource_id,
                            r.allowed,
                        )
                        for r in rows
                    ],
                )
            self.conn.commit()
            return len(rows)
        except Exception:
            self.conn.rollback()
            raise

    def recent(self, limit: int) -> list[AccessRecord]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT {_조회_열} FROM access_records ORDER BY ts DESC, id DESC LIMIT %s",
                (limit,),
            )
            return [_행에서(r) for r in cur.fetchall()]

    def violations(self, limit: int) -> list[AccessRecord]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT {_조회_열} FROM access_records WHERE allowed = FALSE "
                "ORDER BY ts DESC, id DESC LIMIT %s",
                (limit,),
            )
            return [_행에서(r) for r in cur.fetchall()]

"""PrincipalStore 의 psycopg 구현.

principals 테이블은 W2 의 seed-principals 가 채운다. 페르소나 목록을
코드에 다시 적지 않는 이유: 두 벌이 되면 어긋난다.
"""

import psycopg

from core.types import Principal


class PgPrincipalStore:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def find(self, name: str) -> Principal | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT department, clearance, role FROM principals WHERE name = %s", (name,)
            )
            row = cur.fetchone()
        if row is None:
            return None
        return Principal(department=row[0], clearance=row[1], role=row[2])

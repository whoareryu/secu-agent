"""HostStore 의 psycopg 구현."""

import psycopg

from core.types import Host


class PgHostStore:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def upsert(self, host: Host) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO hosts (name, department, required_clearance, allowed_departments)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    department = EXCLUDED.department,
                    required_clearance = EXCLUDED.required_clearance,
                    allowed_departments = EXCLUDED.allowed_departments
                """,
                # 빈 튜플을 NULL 로 정규화한다 — documents 쪽과 같은 규칙이다.
                (
                    host.name,
                    host.department,
                    host.required_clearance,
                    list(host.allowed_departments) or None,
                ),
            )
        self.conn.commit()

    def names(self) -> set[str]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT name FROM hosts")
            return {r[0] for r in cur.fetchall()}

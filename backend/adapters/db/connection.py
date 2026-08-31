"""psycopg 연결과 스키마 적용.

DSN 은 환경변수 SECUAGENT_DSN 으로 준다. 기본값은 docker-compose 의 로컬
컨테이너다 — 5432 대신 5433 을 쓰는 이유는 다른 로컬 Postgres 와 부딪히지
않기 위해서다.
"""

import os
from pathlib import Path

import psycopg

DEFAULT_DSN = "postgresql://secuagent:secuagent@localhost:5433/secuagent"
SCHEMA = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


def connect(dsn: str | None = None) -> psycopg.Connection:
    return psycopg.connect(dsn or os.environ.get("SECUAGENT_DSN", DEFAULT_DSN))


def apply_schema(conn: psycopg.Connection) -> None:
    """db/schema.sql 을 적용한다. 전부 IF NOT EXISTS 라 여러 번 돌려도 안전하다."""
    with conn.cursor() as cur:
        cur.execute(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()

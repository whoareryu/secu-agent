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


def connect(dsn: str | None = None, connect_timeout: int = 5) -> psycopg.Connection:
    """DSN 우선순위: 인자 > 환경변수 > 기본값.

    `os.environ.get(k, default)` 를 쓰면 안 된다 — 값이 **빈 문자열**이면
    기본값을 주지 않는다. `.env` 는 `SECUAGENT_DSN=` 로 비워 두는 것을
    "기본값을 쓴다"는 뜻으로 문서화했는데, `set -a; source .env` 나 direnv 를
    쓰면 빈 문자열이 실제로 export 되고 `psycopg.connect("")` 는 libpq
    기본값(유닉스 소켓 · 현재 OS 사용자)으로 붙는다. 그러면 -m corpus 가
    엉뚱한 데이터베이스를 작업 코퍼스로 착각한다.

    `connect_timeout` 이 없으면 DB 가 방화벽 뒤에서 드롭될 때 OS 기본값
    (수십 초~수 분)까지 매달린다.
    """
    return psycopg.connect(
        dsn or os.environ.get("SECUAGENT_DSN") or DEFAULT_DSN,
        connect_timeout=connect_timeout,
    )


def apply_schema(conn: psycopg.Connection) -> None:
    """db/schema.sql 을 적용한다. 전부 IF NOT EXISTS 라 여러 번 돌려도 안전하다."""
    with conn.cursor() as cur:
        cur.execute(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()

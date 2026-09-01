"""db 테스트용 별도 데이터베이스.

db 마커가 붙은 테스트는 전부 TRUNCATE 로 시작한다. 격리를 위해서는 옳지만,
작업 데이터베이스에 대고 하면 적재해둔 코퍼스와 열람 기록이 사라진다.
같은 컨테이너의 **다른 데이터베이스**를 쓴다.

안전장치를 검사가 아니라 픽스처 진입점에 둔 이유: 잊을 수 있는 곳에 두면
잊는다. 이 픽스처를 쓰지 않고 db 테스트를 쓸 수는 있지만, 그건 리뷰에서
보인다 — 조용히 지나가지 않는다.
"""

import os

import psycopg
import pytest

from adapters.db.connection import DEFAULT_DSN, apply_schema

기본_테스트_DSN = "postgresql://secuagent:secuagent@localhost:5433/secuagent_test"


def _데이터베이스_이름(dsn: str) -> str:
    """DSN 에서 데이터베이스 이름만 뽑는다.

    문자열 전체를 비교하면 안 된다 — 사용자나 포트만 달라도 다른 DSN 이
    되지만 가리키는 데이터베이스는 같을 수 있다.
    """
    return dsn.rsplit("/", 1)[-1].split("?")[0]


def 테스트_DSN_검증(test_dsn: str, work_dsn: str) -> None:
    """테스트 DSN 이 작업 DSN 과 같은 데이터베이스를 가리키면 터진다."""
    if _데이터베이스_이름(test_dsn) == _데이터베이스_이름(work_dsn):
        raise RuntimeError(
            f"테스트 DSN 이 작업 데이터베이스({_데이터베이스_이름(work_dsn)})를 "
            "가리킨다. db 테스트는 TRUNCATE 로 시작하므로 코퍼스가 지워진다. "
            "SECUAGENT_TEST_DSN 을 다른 데이터베이스로 지정한다."
        )


def _데이터베이스_보장(test_dsn: str, work_dsn: str) -> None:
    """테스트 데이터베이스가 없으면 만든다.

    CREATE DATABASE 에는 IF NOT EXISTS 가 없다. 예외로 판단한다.
    """
    이름 = _데이터베이스_이름(test_dsn)
    관리 = psycopg.connect(work_dsn)
    관리.autocommit = True  # CREATE DATABASE 는 트랜잭션 안에서 안 된다
    try:
        with 관리.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{이름}"')
    except psycopg.errors.DuplicateDatabase:
        pass
    finally:
        관리.close()


@pytest.fixture(scope="session")
def db연결():
    작업 = os.environ.get("SECUAGENT_DSN", DEFAULT_DSN)
    테스트 = os.environ.get("SECUAGENT_TEST_DSN", 기본_테스트_DSN)
    테스트_DSN_검증(테스트, 작업)
    _데이터베이스_보장(테스트, 작업)
    conn = psycopg.connect(테스트)
    apply_schema(conn)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def 작업DB_읽기전용():
    """작업 데이터베이스에 **쓰기 불가능한** 연결.

    코퍼스 자체를 검사하는 테스트를 위한 것이다 — 실제 9문서·3계정이
    우리가 아는 그것인지 확인하는 일은 빈 테스트 DB 에서 할 수 없다.

    읽기 전용을 규율이 아니라 Postgres 로 강제한다. 이 연결로는 TRUNCATE 가
    문법적으로 통과해도 실행에서 터진다 — 나중에 누가 이 파일에 쓰기를
    더해도 조용히 지나가지 않는다.
    """
    conn = psycopg.connect(os.environ.get("SECUAGENT_DSN", DEFAULT_DSN))
    with conn.cursor() as cur:
        cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
    conn.commit()
    yield conn
    conn.close()

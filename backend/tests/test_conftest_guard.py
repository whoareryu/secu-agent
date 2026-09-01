"""테스트 DB 안전장치.

이 장치가 없으면 pytest -m db 한 번이 작업 코퍼스를 지운다. 실제로
그런 일이 있었고 jekyll/verification.markdown 항목 ⑤ 가 그것이다.
"""

import pytest

from tests.conftest import 테스트_DSN_검증


def test_같은_데이터베이스를_가리키면_거부한다():
    같은 = "postgresql://secuagent:secuagent@localhost:5433/secuagent"
    with pytest.raises(RuntimeError, match="작업 데이터베이스"):
        테스트_DSN_검증(같은, 같은)


def test_호스트가_달라도_데이터베이스_이름이_같으면_거부한다():
    """DSN 문자열 비교로는 안 된다 — 포트나 사용자만 다르면 통과해버린다."""
    with pytest.raises(RuntimeError, match="작업 데이터베이스"):
        테스트_DSN_검증(
            "postgresql://a:b@localhost:5433/secuagent",
            "postgresql://secuagent:secuagent@localhost:5433/secuagent",
        )


def test_이름이_다르면_통과한다():
    테스트_DSN_검증(
        "postgresql://secuagent:secuagent@localhost:5433/secuagent_test",
        "postgresql://secuagent:secuagent@localhost:5433/secuagent",
    )


def test_쿼리_문자열이_붙어도_이름을_바르게_읽는다():
    with pytest.raises(RuntimeError, match="작업 데이터베이스"):
        테스트_DSN_검증(
            "postgresql://a@h/secuagent?sslmode=require",
            "postgresql://a@h/secuagent",
        )


def test_키워드_형식_DSN_도_같은_데이터베이스로_읽는다():
    """libpq 는 URI 와 키워드 두 형식을 다 받는다.

    문자열을 자르는 방식은 키워드 형식을 통째로 놓쳐, 같은 데이터베이스를
    가리키는 두 DSN 이 달라 보이고 가드가 조용히 무력해진다.
    """
    with pytest.raises(RuntimeError, match="작업 데이터베이스"):
        테스트_DSN_검증(
            "dbname=secuagent host=localhost port=5433",
            "postgresql://secuagent:secuagent@localhost:5433/secuagent",
        )


def test_이름을_읽을_수_없으면_터진다():
    """모르면 막는다. libpq 의 '없으면 사용자 이름' 규칙을 흉내내면
    틀릴 때 열리는 방향으로 틀린다.
    """
    with pytest.raises(RuntimeError, match="읽을 수 없다"):
        테스트_DSN_검증(
            "postgresql://secuagent@localhost:5433/",
            "postgresql://secuagent:secuagent@localhost:5433/secuagent",
        )

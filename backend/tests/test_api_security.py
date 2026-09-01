"""공유 시크릿 검사.

백엔드는 Vercel 의 Route Handler 하고만 대화한다. 시크릿이 없으면
백엔드가 공개 엔드포인트가 되고, 그 뒤에는 LLM 이 있다 — 아무나
요금을 태울 수 있다.
"""

import pytest
from fastapi import HTTPException

from api.security import 시크릿_검사


def test_맞는_시크릿은_통과한다(monkeypatch):
    monkeypatch.setenv("BACKEND_SHARED_SECRET", "s3cret")
    시크릿_검사("s3cret")  # 예외가 없으면 통과


def test_틀린_시크릿은_401_이다(monkeypatch):
    monkeypatch.setenv("BACKEND_SHARED_SECRET", "s3cret")
    with pytest.raises(HTTPException) as e:
        시크릿_검사("wrong")
    assert e.value.status_code == 401


def test_시크릿이_없으면_401_이다(monkeypatch):
    monkeypatch.setenv("BACKEND_SHARED_SECRET", "s3cret")
    with pytest.raises(HTTPException) as e:
        시크릿_검사(None)
    assert e.value.status_code == 401


def test_서버에_시크릿이_설정되지_않았으면_500_이고_통과시키지_않는다(monkeypatch):
    """설정 누락이 '아무나 통과' 로 이어지면 안 된다 — 닫히는 쪽으로 실패한다."""
    monkeypatch.delenv("BACKEND_SHARED_SECRET", raising=False)
    with pytest.raises(HTTPException) as e:
        시크릿_검사("무엇이든")
    assert e.value.status_code == 500


def test_401_응답이_이유를_설명하지_않는다(monkeypatch):
    """'시크릿이 틀렸다' 와 '시크릿이 없다' 를 구분해 알려줄 이유가 없다."""
    monkeypatch.setenv("BACKEND_SHARED_SECRET", "s3cret")
    메시지 = []
    for 값 in ("wrong", None):
        with pytest.raises(HTTPException) as e:
            시크릿_검사(값)
        메시지.append(e.value.detail)
    assert 메시지[0] == 메시지[1]


def test_비ASCII_시크릿은_500_이고_통과시키지_않는다(monkeypatch):
    """한글 시크릿은 어느 층에서도 못 쓴다.

    클라이언트는 HTTP 헤더 값으로 보내지 못하고(UnicodeEncodeError),
    hmac.compare_digest 는 양쪽이 같은 값이어도 TypeError 로 죽는다.
    둘 다 원인을 말해주지 않으므로 서버가 설정 오류라고 밝힌다.
    """
    monkeypatch.setenv("BACKEND_SHARED_SECRET", "한글시크릿")
    with pytest.raises(HTTPException) as e:
        시크릿_검사("한글시크릿")
    assert e.value.status_code == 500


def test_상수_시간_비교를_쓴다():
    """== 로 비교하면 타이밍으로 시크릿을 한 글자씩 알아낼 수 있다."""
    import inspect

    from api import security

    소스 = inspect.getsource(security)
    assert "compare_digest" in 소스, "hmac.compare_digest 를 쓰지 않는다"

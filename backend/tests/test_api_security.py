"""공유 시크릿 검사.

백엔드는 Vercel 의 Route Handler 하고만 대화한다. 시크릿이 없으면
백엔드가 공개 엔드포인트가 되고, 그 뒤에는 LLM 이 있다 — 아무나
요금을 태울 수 있다.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.main import build_app
from api.security import 시크릿_검사
from core.types import Principal


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


def test_상수_시간_비교를_실제로_호출한다(monkeypatch):
    """== 로 비교하면 타이밍으로 시크릿을 한 글자씩 알아낼 수 있다.

    소스에 "compare_digest" 라는 글자가 있는지를 보면 안 된다 — 모듈
    독스트링이 그 단어를 담고 있어서 비교를 `==` 로 바꿔도 통과한다.
    호출을 관찰한다: hmac.compare_digest 를 감싸 실제로 불렸는지와
    무엇을 받았는지를 본다.

    벽시계 타이밍 측정은 쓰지 않는다 — 이 프로젝트는 그 측정이 두 구현을
    구별하지 못한다는 것을 이미 실측으로 보였다(jekyll/verification 장치 ①).
    """
    import hmac

    진짜 = hmac.compare_digest
    호출: list[tuple] = []

    def 감시(a, b):
        호출.append((a, b))
        return 진짜(a, b)

    monkeypatch.setattr(hmac, "compare_digest", 감시)
    monkeypatch.setenv("BACKEND_SHARED_SECRET", "s3cret")

    시크릿_검사("s3cret")
    assert 호출 == [("s3cret", "s3cret")], "맞는 시크릿을 상수 시간 비교로 확인하지 않았다"

    # 틀린 값도 같은 비교를 거쳐야 한다. 길이나 접두어로 미리 가지를 치면
    # 그 분기 자체가 타이밍 경로가 된다.
    호출.clear()
    with pytest.raises(HTTPException):
        시크릿_검사("wrong")
    assert 호출 == [("wrong", "s3cret")], "틀린 시크릿이 상수 시간 비교를 거치지 않았다"


class _주체저장소:
    def find(self, name):
        return Principal(department="개발팀", clearance=1) if name == "김개발" else None


def test_스키마_문서가_노출되지_않는다(monkeypatch):
    """/openapi.json 은 시크릿을 **어느 헤더에 달아야 하는지**까지 알려준다.

    데이터 엔드포인트가 전부 401 이어도 이것 하나가 열려 있으면 공격면의
    전체 지도가 인증 없이 공개된다. 이 백엔드는 터널로 외부에 노출돼 있고,
    컨테이너 로그에 실제로 이 세 경로를 읽고 /ask 를 시도한 흔적이 있다.
    """
    monkeypatch.setenv("BACKEND_SHARED_SECRET", "s3cret")
    client = TestClient(build_app(lambda: None, _주체저장소()))

    for 경로 in ("/openapi.json", "/docs", "/redoc"):
        assert client.get(경로).status_code == 404, f"{경로} 가 열려 있다"

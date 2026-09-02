"""GET /log-events — 주체의 눈으로 본 로그.

**권한 없는 조회 경로를 만들지 않는다.** LogSearch.query 가 Principal 을
필수로 받는 이유(core/ports.py: "권한 없는 조회를 호출할 방법이 없다")가
HTTP 계층에서도 유지되는지를 이 파일이 지킨다.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import build_app
from core.types import Principal

시크릿 = "test-secret-abc123"
헤더 = {"X-Backend-Secret": 시크릿}


class 스텁로그검색:
    def __init__(self):
        self.받은_주체 = []

    def query(self, principal, event_type, since, limit):
        self.받은_주체.append(principal)
        return []


class 스텁주체저장소:
    def find(self, name):
        return Principal(department="개발팀", clearance=1) if name == "김개발" else None


@pytest.fixture
def 검색():
    return 스텁로그검색()


@pytest.fixture
def client(검색, monkeypatch):
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)
    app = build_app(lambda: None, 스텁주체저장소(), 로그검색=검색)
    return TestClient(app)


def test_시크릿_없이는_401(client):
    assert client.get("/log-events?persona=김개발").status_code == 401


def test_알_수_없는_페르소나는_400(client):
    r = client.get("/log-events?persona=없는사람", headers=헤더)
    assert r.status_code == 400


def test_주체가_검색기까지_전달된다(client, 검색):
    """**이 테스트가 이 엔드포인트의 핵심이다.**

    주체 없이 조회하는 경로가 생기면 그것이 곧 우회 경로다. 검색기가
    받은 주체가 principals 테이블에서 번역된 것인지를 본다.
    """
    client.get("/log-events?persona=김개발", headers=헤더)
    assert 검색.받은_주체 == [Principal(department="개발팀", clearance=1)]

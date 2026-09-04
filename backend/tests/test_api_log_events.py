"""GET /log-events — 주체의 눈으로 본 로그.

**권한 없는 조회 경로를 만들지 않는다.** LogSearch.query 가 Principal 을
필수로 받는 이유(core/ports.py: "권한 없는 조회를 호출할 방법이 없다")가
HTTP 계층에서도 유지되는지를 이 파일이 지킨다.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import build_app
from core.types import LogEvent, Principal

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


def test_권한_밖_이벤트가_섞이면_502_이고_raw_가_새지_않는다(client, 검색):
    """**SQL 이 회귀했을 때의 2차 방어선.**

    이 경로는 raw(로그 전문)를 그대로 돌려준다. 권한 필터가 깨지면
    /ask 는 AccessViolation 으로 502 를 내며 시끄럽게 죽지만, 여기에
    재검증이 없으면 200 OK 로 권한 밖 호스트의 원문이 조용히 나간다.
    도구 경로(core/agent/tools.py)와 같은 규율을 HTTP 계층에도 건다.
    """
    샌_것 = LogEvent(
        id=99,
        ts=None,
        host="hr-db-01",
        process="sshd",
        event_type="session_open",
        principal_name="parkhr",
        raw="Sep 1 09:00:00 hr-db-01 sshd[1]: Accepted publickey for parkhr",
        severity=None,
        required_clearance=3,  # 김개발(등급 1)이 볼 수 없다
        allowed_departments=("인사팀",),
    )
    검색.query = lambda principal, event_type, since, limit: [샌_것]

    r = client.get("/log-events?persona=김개발", headers=헤더)

    assert r.status_code == 502
    assert "parkhr" not in r.text
    assert "hr-db-01" not in r.text

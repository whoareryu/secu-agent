"""읽기 엔드포인트 — 문서 · 계정 · 열람 이력. DB 도 LLM 도 없이 스텁으로 검사한다."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from api.main import build_app
from core.types import AccessRecord, DocumentRow, PrincipalRow

시크릿 = "test-secret-abc123"
헤더 = {"X-Backend-Secret": 시크릿}


class 스텁주체저장소:
    def find(self, name):
        return None


class 스텁카탈로그:
    def documents(self):
        return [
            DocumentRow(
                id=1,
                title="ISMS-P 인증기준 안내서",
                doc_type="pdf",
                required_clearance=1,
                allowed_departments=(),
                source_path="data/raw/ismsp.pdf",
                chunk_count=42,
            ),
            DocumentRow(
                id=2,
                title="개발팀 서버접근 절차",
                doc_type="md",
                required_clearance=1,
                allowed_departments=("개발팀",),
                source_path="data/raw/03-개발팀-서버접근-절차.md",
                chunk_count=7,
            ),
        ]

    def principals(self):
        return [
            PrincipalRow(name="김개발", department="개발팀", clearance=1),
            PrincipalRow(name="박인사", department="인사팀", clearance=2),
            PrincipalRow(name="최임원", department="임원실", clearance=3),
        ]


def _기록(persona="박인사", allowed=True, chunk_id=1, ts=None):
    return AccessRecord(
        persona=persona,
        department="인사팀",
        clearance=2,
        query="네트워크 접근",
        clause_code="2.6.1",
        chunk_id=chunk_id,
        allowed=allowed,
        ts=ts,
    )


class 스텁열람기록:
    def __init__(self, 기록들):
        self.기록들 = 기록들

    def record(self, rows):
        return len(rows)

    def recent(self, limit):
        return self.기록들[:limit]

    def violations(self, limit):
        return [r for r in self.기록들 if not r.allowed][:limit]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)

    def 에이전트_공장():
        raise AssertionError("이 테스트들은 /ask 를 부르지 않는다")

    기록들 = [_기록(allowed=True, chunk_id=1), _기록(allowed=False, chunk_id=2)]
    return TestClient(
        build_app(
            에이전트_공장,
            스텁주체저장소(),
            lambda: True,
            열람기록=스텁열람기록(기록들),
            카탈로그=스텁카탈로그(),
        )
    )


def test_시크릿_없이_documents는_401_이다(client):
    assert client.get("/documents").status_code == 401


def test_시크릿_없이_principals는_401_이다(client):
    assert client.get("/principals").status_code == 401


def test_시크릿_없이_access_log는_401_이다(client):
    assert client.get("/access-log").status_code == 401


def test_시크릿_없이_access_log_violations는_401_이다(client):
    assert client.get("/access-log/violations").status_code == 401


def test_documents가_등급과_부서를_담아_돌려준다(client):
    r = client.get("/documents", headers=헤더)
    assert r.status_code == 200
    본문 = r.json()
    assert len(본문) == 2
    개발팀문서 = next(d for d in 본문 if d["title"] == "개발팀 서버접근 절차")
    assert 개발팀문서["required_clearance"] == 1
    assert 개발팀문서["allowed_departments"] == ["개발팀"]
    전사문서 = next(d for d in 본문 if d["title"] == "ISMS-P 인증기준 안내서")
    assert 전사문서["allowed_departments"] == []


def test_principals가_세_계정을_돌려준다(client):
    r = client.get("/principals", headers=헤더)
    assert r.status_code == 200
    이름들 = {p["name"] for p in r.json()}
    assert 이름들 == {"김개발", "박인사", "최임원"}


def test_access_log_limit_상한_초과는_422_다(client):
    r = client.get("/access-log?limit=500", headers=헤더)
    assert r.status_code == 422


def test_access_log_violations가_allowed_false만_돌려준다(client):
    r = client.get("/access-log/violations", headers=헤더)
    assert r.status_code == 200
    본문 = r.json()
    assert 본문, "위반 기록이 비어 있다"
    assert all(record["allowed"] is False for record in 본문)


def test_documents_응답에_본문_키가_없다(client):
    """도메인 타입 검사와 별개로 실제 HTTP 응답 JSON 을 직접 확인한다."""
    r = client.get("/documents", headers=헤더)
    본문 = r.json()
    for 문서 in 본문:
        assert "text" not in 문서
        assert "doc_title" not in 문서


def test_access_log_응답에_본문_키가_없다(client):
    r = client.get("/access-log", headers=헤더)
    본문 = r.json()
    for 기록 in 본문:
        assert "text" not in 기록
        assert "doc_title" not in 기록


def test_access_log가_ts를_돌려준다(monkeypatch):
    """읽기 경로가 시간을 실제로 실어 나르는지 확인한다.

    DB 어댑터가 ts 를 SELECT 에서 빠뜨리거나, main.py 의 _기록으로 가
    r.ts 를 View 에 옮기지 않으면 이 값이 조용히 사라진다.
    """
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)

    def 에이전트_공장():
        raise AssertionError("이 테스트는 /ask 를 부르지 않는다")

    시각 = datetime(2026, 9, 1, 3, 0, 0, tzinfo=UTC)
    기록들 = [_기록(chunk_id=1, ts=시각)]
    client = TestClient(
        build_app(
            에이전트_공장,
            스텁주체저장소(),
            lambda: True,
            열람기록=스텁열람기록(기록들),
            카탈로그=스텁카탈로그(),
        )
    )

    r = client.get("/access-log", headers=헤더)
    assert r.status_code == 200
    본문 = r.json()
    assert datetime.fromisoformat(본문[0]["ts"].replace("Z", "+00:00")) == 시각

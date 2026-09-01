"""API — DB 도 LLM 도 없이 검사한다."""

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from adapters.agent.runner import build_agent
from api.main import build_app
from core.types import EMBEDDING_DIM, PolicyHit, Principal
from tests.fake_chat import 대본모델

시크릿 = "test-secret-abc123"
헤더 = {"X-Backend-Secret": 시크릿}


class 고정임베더:
    def encode(self, texts, kind):
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class 스텁검색기:
    def __init__(self, hits):
        self.hits = hits

    def by_vector(self, vec, principal, k):
        return [h.chunk_id for h in self.hits]

    def by_keyword(self, query, principal, k):
        return [h.chunk_id for h in self.hits]

    def load_hits(self, ids, principal):
        by_id = {h.chunk_id: h for h in self.hits}
        return [by_id[i] for i in ids if i in by_id]


class 스텁주체저장소:
    def __init__(self, 목록):
        self.목록 = 목록

    def find(self, name):
        return self.목록.get(name)


def _hit(chunk_id=1, code="2.6.1"):
    return PolicyHit(
        chunk_id=chunk_id,
        text="네트워크에 대한 비인가 접근을 통제한다",
        doc_title="ISMS-P 인증기준 안내서",
        clause_code=code,
        required_clearance=1,
        allowed_departments=(),
    )


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)
    검색기 = 스텁검색기([_hit()])
    저장소 = 스텁주체저장소({"박인사": Principal("인사팀", 2)})

    def 에이전트_공장():
        모델 = 대본모델(
            대본=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "search_policy",
                            "args": {"query": "네트워크"},
                            "id": "c1",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="규정 2.6.1 을 참고한다."),
            ]
        )
        return build_agent(고정임베더(), 검색기, 모델)

    return TestClient(build_app(에이전트_공장, 저장소))


def test_시크릿_없이는_401_이다(client):
    r = client.post("/ask", json={"query": "질문", "persona": "박인사"})
    assert r.status_code == 401


def test_답변과_인용을_돌려준다(client):
    r = client.post("/ask", json={"query": "네트워크 접근", "persona": "박인사"}, headers=헤더)
    assert r.status_code == 200
    본문 = r.json()
    assert 본문["answer"] == "규정 2.6.1 을 참고한다."
    assert [h["clause_code"] for h in 본문["hits"]] == ["2.6.1"]
    assert 본문["persona"] == {"name": "박인사", "department": "인사팀", "clearance": 2}
    assert 본문["tool_calls"] == 1


def test_모르는_페르소나는_400_이다(client):
    r = client.post("/ask", json={"query": "질문", "persona": "없는사람"}, headers=헤더)
    assert r.status_code == 400


def test_400_응답이_존재하는_이름을_알려주지_않는다(client):
    r = client.post("/ask", json={"query": "질문", "persona": "없는사람"}, headers=헤더)
    본문 = str(r.json())
    for 이름 in ("김개발", "박인사", "최임원"):
        assert 이름 not in 본문


def test_clearance_를_직접_보내도_무시된다(client):
    """클라이언트가 등급을 지정할 수 있으면 그 값이 곧 사칭 경로다."""
    r = client.post(
        "/ask",
        json={"query": "질문", "persona": "박인사", "clearance": 3, "department": "임원실"},
        headers=헤더,
    )
    assert r.status_code == 200
    assert r.json()["persona"]["clearance"] == 2


def test_healthz_는_시크릿_없이도_열린다(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert set(r.json()) >= {"status", "db", "model"}


def test_리스트_모양_content_도_답변으로_직렬화된다(monkeypatch):
    """Gemini 는 agentic 호출에서 thinking/text 파트가 담긴 리스트를 낸다.

    .content 를 그대로 쓰면 str 로 선언된 필드에서 검증이 실패해 500 이 된다.
    """
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)
    검색기 = 스텁검색기([_hit()])
    저장소 = 스텁주체저장소({"박인사": Principal("인사팀", 2)})

    def 에이전트_공장():
        모델 = 대본모델(
            대본=[
                AIMessage(
                    content=[
                        {"type": "thinking", "thinking": "규정을 찾아보자"},
                        {"type": "text", "text": "규정 2.6.1 을 참고한다."},
                    ]
                )
            ]
        )
        return build_agent(고정임베더(), 검색기, 모델)

    c = TestClient(build_app(에이전트_공장, 저장소))
    r = c.post("/ask", json={"query": "질문", "persona": "박인사"}, headers=헤더)
    assert r.status_code == 200
    assert r.json()["answer"] == "규정 2.6.1 을 참고한다."


def test_healthz_는_DB_가_죽으면_degraded_다(monkeypatch):
    """bool(store) 로 검사하면 DB 가 죽어도 ok 가 나온다 — 그러면 헬스체크가
    cold start 와 깨진 배포를 구분하지 못해 존재 이유가 사라진다."""

    class 죽은저장소:
        def find(self, name):
            raise RuntimeError("연결 실패")

    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)

    def 에이전트_공장():
        raise AssertionError("healthz 는 에이전트를 만들지 않는다")

    c = TestClient(build_app(에이전트_공장, 죽은저장소(), lambda: True))
    본문 = c.get("/healthz").json()
    assert 본문["db"] is False
    assert 본문["status"] == "degraded"


def test_healthz_모델_준비_여부는_콜백을_따른다(monkeypatch):
    """SECUAGENT_MODEL_READY 는 import 시점에 고정되는 상수였다 — 실제로는
    임베더가 아직 로드되지 않았어도 매 응답이 ready 를 말했다. 이제는
    호출자가 넘긴 콜백을 그대로 따른다 — 자원이 생기기 전엔 loading,
    생긴 뒤엔 ready 로 바뀐다."""
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)
    저장소 = 스텁주체저장소({"박인사": Principal("인사팀", 2)})

    def 에이전트_공장():
        raise AssertionError("healthz 는 에이전트를 만들지 않는다")

    준비됨 = False
    c = TestClient(build_app(에이전트_공장, 저장소, lambda: 준비됨))

    assert c.get("/healthz").json()["model"] == "loading"
    준비됨 = True
    assert c.get("/healthz").json()["model"] == "ready"

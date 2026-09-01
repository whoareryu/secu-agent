"""API — DB 도 LLM 도 없이 검사한다."""

import os

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from adapters.agent.runner import build_agent
from api.main import build_app
from core.agent.policy import 로그_범위_고지
from core.types import EMBEDDING_DIM, PolicyHit, Principal
from tests.fake_chat import 대본모델

시크릿 = "test-secret-abc123"
헤더 = {"X-Backend-Secret": 시크릿}
_시크릿 = 헤더


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

class 빈로그검색기:
    """로그를 쓰지 않는 테스트용. build_agent 가 log_searcher 를 필수로
    받으므로 빠뜨릴 수 없다 — 빠뜨림이 생성 시점에 드러나는 편이 낫다."""

    def query(self, principal, event_type, since, limit):
        return []



class 스텁주체저장소:
    def __init__(self, 목록):
        self.목록 = 목록

    def find(self, name):
        return self.목록.get(name)


class 스텁열람기록:
    def __init__(self):
        self.기록 = []

    def record(self, rows):
        self.기록.extend(rows)
        return len(rows)

    def recent(self, limit):
        return list(reversed(self.기록))[:limit]

    def violations(self, limit):
        return [r for r in reversed(self.기록) if not r.allowed][:limit]


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
        return build_agent(고정임베더(), 검색기, 모델, 빈로그검색기())

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
        return build_agent(고정임베더(), 검색기, 모델, 빈로그검색기())

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


def test_질의가_열람_기록을_남긴다(monkeypatch):
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)
    기록 = 스텁열람기록()
    검색기 = 스텁검색기([_hit(1, "2.6.1")])
    저장소 = 스텁주체저장소({"박인사": Principal("인사팀", 2)})

    def 공장():
        모델 = 대본모델(
            대본=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "search_policy",
                            "args": {"query": "질의"},
                            "id": "c1",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="답변"),
            ]
        )
        return build_agent(고정임베더(), 검색기, 모델, 빈로그검색기())

    c = TestClient(build_app(공장, 저장소, lambda: True, 기록))
    c.post("/ask", json={"query": "네트워크 접근", "persona": "박인사"}, headers=헤더)

    assert 기록.기록, "기록이 남지 않았다"
    r = 기록.기록[0]
    assert r.persona == "박인사" and r.clearance == 2
    assert r.clause_code == "2.6.1" and r.allowed is True


def test_기록에_본문이_담기지_않는다():
    """AccessRecord 에 본문 필드가 있으면 언젠가 채워진다."""
    import dataclasses

    from core.types import AccessRecord

    필드 = {f.name for f in dataclasses.fields(AccessRecord)}
    for 금지 in ("text", "doc_title", "title", "body"):
        assert 금지 not in 필드, f"AccessRecord 에 {금지} 가 있다"


def test_기록이_실패해도_응답은_정상이다(monkeypatch):
    """기록은 곁가지다. 그것 때문에 질의가 실패하면 안 된다."""
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)

    class 터지는기록:
        def record(self, rows):
            raise RuntimeError("DB 연결 끊김")

        def recent(self, limit):
            return []

        def violations(self, limit):
            return []

    검색기 = 스텁검색기([_hit(1)])
    저장소 = 스텁주체저장소({"박인사": Principal("인사팀", 2)})

    def 공장():
        모델 = 대본모델(대본=[AIMessage(content="답변")])
        return build_agent(고정임베더(), 검색기, 모델, 빈로그검색기())

    c = TestClient(build_app(공장, 저장소, lambda: True, 터지는기록()))
    r = c.post("/ask", json={"query": "질의", "persona": "박인사"}, headers=헤더)
    assert r.status_code == 200


def test_권한_위반은_502_이고_차단_기록을_남긴다(monkeypatch):
    """관리자 화면의 "권한 밖 열람 알림" 을 채우는 유일한 생산자다.

    이 경로는 문서화되지 않은 LangChain 동작에 기대고 있다 — ToolNode 가
    도구 예외를 삼키도록 뒤집히면 아무것도 기록되지 않고 알림 테이블은
    조용히 영원히 빈다. 성공 기록 경로만 덮으면 그것을 못 잡는다.

    예외를 손으로 짓지 않고 enforce 가 실제로 내는 것을 쓴다. main 이 예외의
    kind·ids 로 기록을 만드므로, enforce 가 그것을 싣지 않게 되면 여기서
    걸려야 한다.
    """
    from core.agent.policy import enforce

    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)
    기록 = 스텁열람기록()
    저장소 = 스텁주체저장소({"박인사": Principal("인사팀", 2)})

    권한밖 = PolicyHit(
        chunk_id=77,
        text="임원 전용 본문",
        doc_title="임원 보상 규정",
        clause_code="9.9.9",
        required_clearance=3,
        allowed_departments=("임원실",),
    )

    class 위반에이전트:
        def invoke(self, state, context=None):
            enforce([권한밖], context.principal)
            raise AssertionError("enforce 가 위반을 잡지 못했다")

    c = TestClient(build_app(lambda: 위반에이전트(), 저장소, lambda: True, 기록))
    r = c.post("/ask", json={"query": "임원 보상", "persona": "박인사"}, headers=헤더)

    assert r.status_code == 502

    # 응답은 무엇이 막혔는지 말하지 않는다. 막으려고 만든 장치가 통로가
    # 되면 안 된다 — chunk id 도 조항 코드도 문서 제목도 나가지 않는다.
    본문 = str(r.json())
    for 금지 in ("77", "9.9.9", "임원 보상 규정", "임원 전용 본문"):
        assert 금지 not in 본문, f"502 응답이 {금지} 를 흘렸다"

    # 기록은 남는다. 그리고 그 행이 담은 식별자는 id 뿐이다.
    assert len(기록.기록) == 1, f"차단 기록이 정확히 한 줄이 아니다: {기록.기록}"
    행 = 기록.기록[0]
    assert 행.allowed is False
    assert (행.resource_kind, 행.resource_id) == ("chunk", 77)
    assert 행.clause_code is None
    assert (행.persona, 행.department, 행.clearance) == ("박인사", "인사팀", 2)
    assert 행.query == "임원 보상"


def _로그이벤트(id: int, raw: str):
    from datetime import datetime

    from core.types import LogEvent

    return LogEvent(
        id=id,
        ts=datetime(2026, 9, 1, 2, 0, 0),
        host="exec-fs-01",
        process="sshd",
        event_type="auth_failure",
        principal_name="execuser",
        raw=raw,
        severity=None,
        required_clearance=3,
        allowed_departments=(),
    )


def test_로그_권한_위반은_502_이고_로그_이벤트로_기록된다(monkeypatch):
    """문서 위반 테스트의 로그판. **이 형제가 없어서 결함이 살아남았다.**

    로그 위반이 청크 기록으로 남으면 W4b 관리자 화면이 그 id 를 청크로 풀어
    무관한 문서를 띄운다 — 두 id 공간은 실제로 겹친다(청크 1..338, 로그
    이벤트 1..33). 그래서 같은 숫자(77)를 청크 위반과 로그 위반 양쪽에 쓰고
    두 행이 다르게 읽히는지 본다. 종류를 메시지에서 추측하는 구현은 두 행을
    같게 만들어 여기서 걸린다.
    """
    from core.agent.policy import enforce, enforce_events

    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)
    기록 = 스텁열람기록()
    저장소 = 스텁주체저장소({"박인사": Principal("인사팀", 2)})

    class 로그위반에이전트:
        def invoke(self, state, context=None):
            enforce_events([_로그이벤트(77, raw="exec-fs-01 sshd: Failed password for root")],
                           context.principal)
            raise AssertionError("enforce_events 가 위반을 잡지 못했다")

    c = TestClient(build_app(lambda: 로그위반에이전트(), 저장소, lambda: True, 기록))
    r = c.post("/ask", json={"query": "어젯밤 인증 실패", "persona": "박인사"}, headers=헤더)

    assert r.status_code == 502

    # 응답은 무엇이 막혔는지 말하지 않는다 — id 도 호스트도 raw 본문도 아니다.
    본문 = str(r.json())
    for 금지 in ("77", "exec-fs-01", "Failed password", "root"):
        assert 금지 not in 본문, f"502 응답이 {금지} 를 흘렸다"

    assert len(기록.기록) == 1, f"차단 기록이 정확히 한 줄이 아니다: {기록.기록}"
    행 = 기록.기록[0]
    assert 행.allowed is False
    assert 행.resource_kind == "log_event", "로그 위반이 청크로 기록됐다"
    assert 행.resource_id == 77
    assert (행.persona, 행.department, 행.clearance) == ("박인사", "인사팀", 2)

    # 같은 숫자의 청크 위반과 나란히 둔다. 종류가 없으면 두 행이 구별되지 않는다.
    권한밖청크 = PolicyHit(
        chunk_id=77,
        text="임원 전용 본문",
        doc_title="임원 보상 규정",
        clause_code="9.9.9",
        required_clearance=3,
        allowed_departments=("임원실",),
    )

    class 청크위반에이전트:
        def invoke(self, state, context=None):
            enforce([권한밖청크], context.principal)
            raise AssertionError("enforce 가 위반을 잡지 못했다")

    c2 = TestClient(build_app(lambda: 청크위반에이전트(), 저장소, lambda: True, 기록))
    c2.post("/ask", json={"query": "임원 보상", "persona": "박인사"}, headers=헤더)

    assert len(기록.기록) == 2
    종류들 = {(행.resource_kind, 행.resource_id) for 행 in 기록.기록}
    assert 종류들 == {("log_event", 77), ("chunk", 77)}, (
        f"같은 id 의 로그 위반과 청크 위반이 구별되지 않는다: {종류들}"
    )


def _클라이언트(에이전트):
    os.environ["BACKEND_SHARED_SECRET"] = 시크릿
    저장소 = 스텁주체저장소(
        {
            "김개발": Principal("개발팀", 1),
            "박인사": Principal("인사팀", 2),
            "최임원": Principal("임원실", 3),
        }
    )
    return TestClient(build_app(lambda: 에이전트, 저장소))


class _규정만_에이전트:
    """query_logs 를 부르지 않는다 — ctx.queried_logs 가 False 로 남는다."""

    def invoke(self, state, context=None):
        return {"messages": [AIMessage(content="비밀번호는 12자 이상이어야 한다.")]}


def _규정만_부르는_에이전트():
    return _규정만_에이전트()


class _로그_에이전트:
    """query_logs 를 부른 것처럼 ctx.queried_logs 를 세운다."""

    def invoke(self, state, context=None):
        context.queried_logs = True
        context.tool_calls += 1
        return {"messages": [AIMessage(content="어젯밤 인증 실패가 있었다.")]}


def _로그를_부르는_에이전트():
    return _로그_에이전트()


class _로그_침묵_에이전트:
    """query_logs 는 불렀지만 모델이 아무 문장도 내지 않는다."""

    def invoke(self, state, context=None):
        context.queried_logs = True
        context.tool_calls += 1
        return {"messages": [AIMessage(content="")]}


def _로그를_부르지만_침묵하는_에이전트():
    return _로그_침묵_에이전트()


def test_로그를_조회하지_않으면_고지가_없다():
    """규정만 물은 답에 로그 고지가 붙으면 그것도 지어낸 값이다."""
    client = _클라이언트(에이전트=_규정만_부르는_에이전트())
    r = client.post("/ask", json={"query": "비밀번호 규정", "persona": "김개발"},
                    headers=_시크릿)
    assert r.json()["log_scope"] is None


def test_로그를_조회하면_고지가_붙는다():
    client = _클라이언트(에이전트=_로그를_부르는_에이전트())
    r = client.post("/ask", json={"query": "어젯밤 인증 실패", "persona": "김개발"},
                    headers=_시크릿)
    assert r.json()["log_scope"] == 로그_범위_고지


def test_고지_문구가_등급과_무관하게_동일하다():
    """**이 테스트가 고지를 통로로 만드는 변경을 잡는다.**

    문구가 등급에 따라 갈리는 순간 그 차이가 관측 가능한 신호가 된다.
    조건 없이 같은 문자열이어야 안전하다(보충 spec 2.3).
    """
    client = _클라이언트(에이전트=_로그를_부르는_에이전트())
    문구 = set()
    for 페르소나 in ("김개발", "박인사", "최임원"):
        r = client.post("/ask", json={"query": "어젯밤 인증 실패", "persona": 페르소나},
                        headers=_시크릿)
        문구.add(r.json()["log_scope"])
    # len(문구) == 1 로 쓰면 셋 다 None 이어도 통과한다 — 고지가 아예
    # 사라진 것과 같은 문구인 것을 구별하지 못한다.
    assert 문구 == {로그_범위_고지}, f"등급에 따라 고지가 갈린다: {문구}"


def test_고지가_모델_출력에서_오지_않는다():
    """모델이 아무 말도 안 해도 고지는 붙는다 — 모델은 잊는다."""
    client = _클라이언트(에이전트=_로그를_부르지만_침묵하는_에이전트())
    r = client.post("/ask", json={"query": "로그", "persona": "김개발"}, headers=_시크릿)
    assert r.json()["log_scope"] == 로그_범위_고지

"""에이전트 런너 — LLM 없이 검사한다.

가장 중요한 것은 test_principal_이_도구_스키마에_없다 다. principal 이
스키마에 새어 들어오면 LLM 이 등급을 지정할 수 있게 되는데, 그 사고는
조용하다 — 에이전트는 여전히 답을 내고 나머지 테스트도 전부 통과한다.
"""

import pytest
from langchain_core.messages import AIMessage

from adapters.agent.context import AgentContext
from adapters.agent.runner import build_agent, build_tools
from core.types import EMBEDDING_DIM, PolicyHit, Principal
from tests.fake_chat import 대본모델

사원 = Principal(department="개발팀", clearance=1)
팀장 = Principal(department="인사팀", clearance=2)


class 고정임베더:
    def encode(self, texts, kind):
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class 스텁검색기:
    def __init__(self, hits):
        self.hits = hits
        self.받은_주체 = []

    def by_vector(self, vec, principal, k):
        self.받은_주체.append(principal)
        self.실행수 = getattr(self, "실행수", 0) + 1
        return [h.chunk_id for h in self.hits]

    def by_keyword(self, query, principal, k):
        self.받은_주체.append(principal)
        return [h.chunk_id for h in self.hits]

    def load_hits(self, ids, principal):
        self.받은_주체.append(principal)
        by_id = {h.chunk_id: h for h in self.hits}
        return [by_id[i] for i in ids if i in by_id]


def _hit(chunk_id=1, code="2.6.1"):
    return PolicyHit(
        chunk_id=chunk_id,
        text="네트워크에 대한 비인가 접근을 통제한다",
        doc_title="ISMS-P 인증기준 안내서",
        clause_code=code,
        required_clearance=1,
        allowed_departments=(),
    )


def _도구_호출(query="네트워크 접근"):
    return AIMessage(
        content="",
        tool_calls=[
            {"name": "search_policy", "args": {"query": query}, "id": "c1", "type": "tool_call"}
        ],
    )


# ────────────────────── 보안: 스키마 은닉 ──────────────────────


def test_principal_이_도구_스키마에_없다():
    """**이 파일에서 가장 중요한 테스트다.**

    모델에게 전달되는 스키마는 tool_call_schema 다. 여기에 principal 이
    보이면 LLM 이 clearance 를 직접 지정할 수 있다 — 필수 인자로 두는
    것은 누락을 막을 뿐 사칭을 막지 못한다.

    args_schema 를 검사하면 안 된다. 거기에는 runtime 이 남아 있고,
    args_schema.model_json_schema() 는 PydanticInvalidForJsonSchema 를
    던진다 — ToolRuntime 이 callable 필드를 갖기 때문이다(실측).
    """
    도구들 = build_tools(고정임베더(), 스텁검색기([_hit()]))
    assert len(도구들) == 1

    스키마 = 도구들[0].tool_call_schema.model_json_schema()
    필드 = set(스키마["properties"])

    assert "principal" not in 필드
    assert "runtime" not in 필드
    assert "clearance" not in 필드
    assert "department" not in 필드
    assert 필드 == {"query", "k"}, f"모델이 보는 필드가 예상과 다르다: {필드}"


def test_스키마에_query_는_있다():
    """은닉이 지나쳐 도구가 아무것도 못 받게 되면 안 된다."""
    도구들 = build_tools(고정임베더(), 스텁검색기([_hit()]))
    스키마 = 도구들[0].tool_call_schema.model_json_schema()
    assert "query" in 스키마["properties"]
    assert "query" in 스키마["required"]


# ────────────────────── 컨텍스트 주입 ──────────────────────


def test_요청의_주체가_검색까지_전달된다():
    검색기 = 스텁검색기([_hit()])
    모델 = 대본모델(대본=[_도구_호출(), AIMessage(content="답변")])
    agent = build_agent(고정임베더(), 검색기, 모델)

    agent.invoke(
        {"messages": [{"role": "user", "content": "네트워크 접근 통제"}]},
        context=AgentContext(principal=팀장),
    )
    assert 검색기.받은_주체, "검색기가 불리지 않았다"
    assert all(p == 팀장 for p in 검색기.받은_주체)


def test_인용_근거가_컨텍스트에_모인다():
    """API 가 인용을 꺼내는 경로다. 컨텍스트 객체가 그대로 전달된다(실측)."""
    검색기 = 스텁검색기([_hit(1, "2.6.1"), _hit(2, "2.5.1")])
    모델 = 대본모델(대본=[_도구_호출(), AIMessage(content="답변")])
    ctx = AgentContext(principal=사원)

    build_agent(고정임베더(), 검색기, 모델).invoke(
        {"messages": [{"role": "user", "content": "질문"}]}, context=ctx
    )
    assert [h.clause_code for h in ctx.collected] == ["2.6.1", "2.5.1"]


def test_도구를_안_부르면_근거가_비어_있다():
    검색기 = 스텁검색기([_hit()])
    모델 = 대본모델(대본=[AIMessage(content="도구 없이 바로 답한다")])
    ctx = AgentContext(principal=사원)

    res = build_agent(고정임베더(), 검색기, 모델).invoke(
        {"messages": [{"role": "user", "content": "안녕"}]}, context=ctx
    )
    assert ctx.collected == []
    assert res["messages"][-1].content == "도구 없이 바로 답한다"


# ────────────────────── 결과 없음 ──────────────────────


def test_결과가_없어도_권한을_이유로_말하지_않는다():
    """ "권한이 없어 못 보여준다" 는 문장 자체가 존재 확인이 된다.

    볼 수 있는 것이 없는 것과 문서가 숨겨진 것을 구분해 말하면,
    그 구분이 곧 누출 채널이다.
    """
    검색기 = 스텁검색기([])
    모델 = 대본모델(대본=[_도구_호출(), AIMessage(content="답변")])
    ctx = AgentContext(principal=사원)

    res = build_agent(고정임베더(), 검색기, 모델).invoke(
        {"messages": [{"role": "user", "content": "질문"}]}, context=ctx
    )
    도구_메시지 = [m for m in res["messages"] if m.__class__.__name__ == "ToolMessage"]
    assert 도구_메시지, "도구 메시지가 없다"
    본문 = 도구_메시지[0].content
    for 금지 in ("권한", "등급", "clearance", "접근 불가"):
        assert 금지 not in 본문, f"결과 없음 메시지가 '{금지}' 를 말한다: {본문}"


# ────────────────────── 상한 ──────────────────────


def test_도구가_상한보다_많이_실행되지_않는다():
    """모델이 상한보다 많이 시도해도 도구 로직은 상한까지만 닿는다.

    차단된 호출도 ToolMessage 를 만들기 때문에 그것을 세면 안 된다 —
    검색기가 실제로 불린 횟수가 상한이 지키는 값이다.
    """
    from core.agent.policy import MAX_TOOL_CALLS

    검색기 = 스텁검색기([_hit()])
    # 리스트를 * 로 곱하면 같은 AIMessage 객체를 반복 참조하게 되고, langgraph
    # 의 메시지 병합이 id 로 이뤄지므로 동일 객체는 한 턴으로 뭉개진다(실측).
    # 매번 새 인스턴스를 만들어야 실제 반복 횟수를 시험할 수 있다.
    모델 = 대본모델(
        대본=[_도구_호출() for _ in range(MAX_TOOL_CALLS + 2)] + [AIMessage(content="답변")]
    )
    build_agent(고정임베더(), 검색기, 모델).invoke(
        {"messages": [{"role": "user", "content": "질문"}]},
        context=AgentContext(principal=사원),
    )
    assert getattr(검색기, "실행수", 0) == MAX_TOOL_CALLS


def test_도구를_끝없이_시도해도_종료된다():
    """회귀 테스트.

    ToolCallLimitMiddleware 의 "continue" 는 초과한 도구를 차단할 뿐
    그래프를 끝내지 않는다. 도구만 반복 요청하는 모델에서는 모델 호출이
    무한정 늘어나고, 재귀 상한(9999)에 걸려 GraphRecursionError 로 죽는다 —
    실측으로 확인했다. ModelCallLimitMiddleware 가 그것을 막는다.
    """
    검색기 = 스텁검색기([_hit()])
    # 서로 다른 인스턴스여야 한다. 같은 객체를 반복하면 add_messages 리듀서가
    # .id 로 병합해 한 턴으로 접히고, 폭주를 재현하지 못한다.
    모델 = 대본모델(대본=[_도구_호출() for _ in range(50)])

    # 예외 없이 끝나는 것 자체가 이 테스트의 암묵적 단언이다.
    build_agent(고정임베더(), 검색기, 모델).invoke(
        {"messages": [{"role": "user", "content": "질문"}]},
        context=AgentContext(principal=사원),
    )

    from core.agent.policy import MAX_MODEL_CALLS

    assert 모델.호출수 == MAX_MODEL_CALLS, f"모델을 {모델.호출수}회 불렀다 — 상한이 지켜지지 않았다"


@pytest.mark.llm
def test_실제_모델이_도구를_부르고_한국어로_답한다():
    """실제 Gemini 호출. GOOGLE_APPLICATION_CREDENTIALS 와 GOOGLE_CLOUD_PROJECT 가 필요하다.

        .venv/bin/python -m pytest -m llm -v

    대본 모델로는 확인할 수 없는 것을 본다 — 진짜 모델이 이 도구 설명과
    시스템 프롬프트를 보고 실제로 도구를 부르는가.
    Vertex(Agent Platform) 경로다. 서비스 계정 자격증명이 필요하다.
    """
    import os

    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        pytest.skip("GOOGLE_APPLICATION_CREDENTIALS 가 없다")
    if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        pytest.skip("GOOGLE_CLOUD_PROJECT 가 없다")

    from adapters.llm.gemini import build_model

    검색기 = 스텁검색기([_hit(1, "2.5.4")])
    ctx = AgentContext(principal=사원)
    res = build_agent(고정임베더(), 검색기, build_model()).invoke(
        {"messages": [{"role": "user", "content": "비밀번호는 얼마나 자주 바꿔야 하나"}]},
        context=ctx,
    )
    assert ctx.collected, (
        "실제 모델이 도구를 부르지 않았다 — 도구 설명이나 시스템 프롬프트를 손봐야 한다"
    )
    assert res["messages"][-1].content.strip(), "답변이 비었다"

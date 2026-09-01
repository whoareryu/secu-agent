"""LangGraph 런너 — core 의 도구 로직을 감싸기만 한다.

프레임워크는 이 파일에만 산다. core/ 는 langchain 을 모르고 경계 테스트가
그것을 강제한다(상위 spec 2.3).

**principal 은 도구 스키마에 없다.** 도구 함수가 ToolRuntime 을 받으면
그 인자는 모델이 보는 tool_call_schema 에서 빠진다. 필수 인자로 두면
누락은 막지만 사칭은 막지 못한다 — LLM 이 clearance: 3 을 써넣을 수 있다.

create_react_agent 를 쓰지 않는다. langgraph.prebuilt 의 그것은
deprecated 이고 langchain.agents.create_agent 가 현재 API 다.
"""

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain.tools import ToolRuntime, tool
from langchain_core.language_models import BaseChatModel

from adapters.agent.context import AgentContext
from core.agent import tools as core_tools
from core.agent.policy import MAX_MODEL_CALLS, MAX_TOOL_CALLS
from core.ports import ChunkSearch, Embedder

SYSTEM_PROMPT = """너는 사내 보안 규정을 안내하는 도우미다.

규정에 관한 질문에는 반드시 search_policy 도구로 근거를 찾은 뒤 답한다.
도구가 돌려준 조항만 인용한다. 조항 번호를 지어내지 않는다.
도구가 아무것도 돌려주지 않으면 찾지 못했다고 답한다 — 권한이나 등급을
이유로 들지 않는다.
답은 한국어로, 인용한 조항 번호를 본문에 함께 적는다."""

# 도구가 결과 없음을 알릴 때 쓰는 문장. 권한을 이유로 말하지 않는다 —
# "권한이 없어 못 보여준다" 는 문장 자체가 문서의 존재를 확인해준다.
결과_없음 = "관련된 조항을 찾지 못했다."


def build_tools(embedder: Embedder, searcher: ChunkSearch) -> list:
    """모델에게 넘길 도구 목록을 만든다.

    embedder 와 searcher 를 클로저로 닫는다 — 이것들도 LLM 이 볼 이유가 없다.
    """

    @tool
    def search_policy(query: str, runtime: ToolRuntime[AgentContext], k: int = 10) -> str:
        """사내 보안 규정에서 질의와 관련된 조항을 찾는다.

        Args:
            query: 찾고 싶은 내용을 한국어 자연어로 쓴다.
            k: 가져올 조항 수. 기본 10.
        """
        ctx = runtime.context
        ctx.tool_calls += 1
        hits = core_tools.search_policy(query, ctx.principal, embedder, searcher, k=k)
        ctx.collected.extend(hits)

        if not hits:
            return 결과_없음

        줄 = []
        for h in hits:
            표시 = f"[{h.clause_code}]" if h.clause_code else "[조항 밖]"
            줄.append(f"{표시} {h.doc_title}\n{h.text}")
        return "\n\n".join(줄)

    return [search_policy]


def build_agent(embedder: Embedder, searcher: ChunkSearch, model: BaseChatModel):
    """컴파일된 에이전트를 만든다.

    exit_behavior 가 "continue" 인 이유: 세 값 중 상위 spec 7.2 의 "넘으면
    중단하고 그때까지의 결과로 답한다"에 맞는 것이 이것뿐이다. "error" 는
    예외를 던지고, "end" 는 결과가 아니라 왜 멈췄는지를 답한다.

    "continue" 는 초과한 도구 호출만 차단할 뿐 그래프를 끝내지 않는다 —
    모델이 스스로 멈추기를 기다린다(실측: 계속 도구를 시도하는 모델에서는
    재귀 상한까지 모델 호출만 반복된다). ModelCallLimitMiddleware 가 그
    종료를 보장한다.
    """
    return create_agent(
        model=model,
        tools=build_tools(embedder, searcher),
        system_prompt=SYSTEM_PROMPT,
        context_schema=AgentContext,
        middleware=[
            ToolCallLimitMiddleware(run_limit=MAX_TOOL_CALLS, exit_behavior="continue"),
            # 종료 보장. ToolCallLimitMiddleware 의 "continue" 는 초과한 도구를
            # 차단할 뿐 그래프를 끝내지 않아, 도구를 계속 시도하는 모델에서는
            # 재귀 상한(9999)에 걸릴 때까지 모델만 반복 호출된다 — 실측.
            ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS, exit_behavior="end"),
        ],
    )

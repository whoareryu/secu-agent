"""LangGraph 런너 — core 의 도구 로직을 감싸기만 한다.

프레임워크는 이 파일에만 산다. core/ 는 langchain 을 모르고 경계 테스트가
그것을 강제한다(상위 spec 2.3).

**principal 은 도구 스키마에 없다.** 도구 함수가 ToolRuntime 을 받으면
그 인자는 모델이 보는 tool_call_schema 에서 빠진다. 필수 인자로 두면
누락은 막지만 사칭은 막지 못한다 — LLM 이 clearance: 3 을 써넣을 수 있다.

create_react_agent 를 쓰지 않는다. langgraph.prebuilt 의 그것은
deprecated 이고 langchain.agents.create_agent 가 현재 API 다.
"""

from datetime import datetime

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain.tools import ToolRuntime, tool
from langchain_core.language_models import BaseChatModel

from adapters.agent.context import AgentContext
from core.agent import tools as core_tools
from core.agent.policy import MAX_MODEL_CALLS, MAX_TOOL_CALLS
from core.ports import ChunkSearch, Embedder, LogSearch

SYSTEM_PROMPT = """너는 사내 보안 규정을 안내하는 도우미다.

규정에 관한 질문에는 반드시 search_policy 도구로 근거를 찾은 뒤 답한다.
도구가 돌려준 조항만 인용한다. 조항 번호를 지어내지 않는다.
도구가 아무것도 돌려주지 않으면 찾지 못했다고 답한다 — 권한이나 등급을
이유로 들지 않는다.
답은 한국어로, 인용한 조항 번호를 본문에 함께 적는다.

로그에 관한 질문에는 query_logs 로 실제 기록을 확인한 뒤 답한다.
로그와 규정을 함께 물으면 두 도구를 모두 쓴다 — 이벤트를 찾은 뒤
그 내용으로 search_policy 를 불러 근거 조항을 찾는다.
개수를 셀 때 "전부" 라고 단정하지 않는다."""

# 도구가 결과 없음을 알릴 때 쓰는 문장. 권한을 이유로 말하지 않는다 —
# "권한이 없어 못 보여준다" 는 문장 자체가 문서의 존재를 확인해준다.
결과_없음 = "관련된 조항을 찾지 못했다."

# query_logs 가 결과 없음을 알릴 때 쓰는 문장. 권한을 이유로 들지 않는 것은
# 결과_없음 과 같다.
로그_결과_없음 = "해당하는 기록을 찾지 못했다."


def build_tools(embedder: Embedder, searcher: ChunkSearch, log_searcher: LogSearch) -> list:
    """모델에게 넘길 도구 목록을 만든다.

    embedder, searcher, log_searcher 를 클로저로 닫는다 — 이것들도 LLM 이
    볼 이유가 없다.

    **log_searcher 에 기본값을 두지 않는다.** 기본값 None 을 주면 이 인자를
    빠뜨린 생성이 조용히 통과하고, query_logs 가 None 을 들고 등록된 뒤
    모델이 그것을 부르는 실행 시점에야 터진다. PolicyHit 과 LogEvent 의
    권한 필드에 기본값이 없는 것과 같은 이유다 — 빠뜨림은 생성 시점에
    드러나야 한다.
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

    @tool
    def query_logs(
        runtime: ToolRuntime[AgentContext],
        event_type: str | None = None,
        since: str | None = None,
        limit: int = 20,
    ) -> str:
        """서버 운영 로그에서 이벤트를 찾는다.

        Args:
            event_type: auth_failure · session_open · session_close ·
                privilege_use · other 중 하나. 비우면 전부.
            since: ISO 8601 시각. 이 시각 이후만. 비우면 전부.
            limit: 가져올 이벤트 수. 기본 20.
        """
        ctx = runtime.context
        ctx.tool_calls += 1
        ctx.queried_logs = True

        시각 = None
        if since:
            try:
                시각 = datetime.fromisoformat(since)
            except ValueError:
                # 모델이 형식을 틀리는 일은 흔하다. 요청을 죽이지 말고
                # 필터 없이 진행한다 — 그 사실을 응답에 적는다.
                return "since 를 ISO 8601 시각으로 다시 준다. 예: 2026-09-01T00:00:00"

        events = core_tools.query_logs(
            ctx.principal, log_searcher, event_type=event_type, since=시각, limit=limit
        )
        if not events:
            return 로그_결과_없음

        return "\n".join(
            f"{e.ts:%Y-%m-%d %H:%M:%S} [{e.host}] {e.event_type} {e.raw}" for e in events
        )

    return [search_policy, query_logs]


def build_agent(
    embedder: Embedder,
    searcher: ChunkSearch,
    model: BaseChatModel,
    log_searcher: LogSearch,
):
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
        tools=build_tools(embedder, searcher, log_searcher),
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

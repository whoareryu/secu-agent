"""FastAPI 앱 — 얇은 HTTP 계층.

도메인 판단을 하지 않는다. 페르소나 이름을 Principal 로 바꾸고,
에이전트를 부르고, 결과를 직렬화한다.
"""

from collections.abc import Callable

from fastapi import Depends, FastAPI, HTTPException

from adapters.agent.context import AgentContext
from api.schemas import AskRequest, AskResponse, PersonaView, PolicyHitView
from api.security import 시크릿_검사
from core.ports import PrincipalStore


def build_app(
    에이전트_공장: Callable[[], object],
    주체저장소: PrincipalStore,
    모델_준비됨: Callable[[], bool] = lambda: True,
) -> FastAPI:
    """앱을 조립한다. 의존성을 인자로 받아 테스트가 스텁을 넣을 수 있다."""
    app = FastAPI(title="secu-agent")

    @app.get("/healthz")
    def healthz() -> dict:
        # db 와 model 을 따로 보고한다 — cold start 중인지 배포가 깨졌는지
        # 구분하려면 둘이 나뉘어야 한다.
        #
        # 실제로 DB 를 왕복한다. bool(주체저장소) 는 객체가 언제나 참이라
        # 아무것도 확인하지 않는다. 없는 이름을 찾으면 정상적으로 None 이
        # 돌아오고, 그 과정에서 연결이 실제로 쓰인다.
        try:
            주체저장소.find("__healthz__")
            db_ok = True
        except Exception:
            db_ok = False
        return {
            "status": "ok" if db_ok else "degraded",
            "db": db_ok,
            "model": "ready" if 모델_준비됨() else "loading",
        }

    @app.post("/ask", response_model=AskResponse, dependencies=[Depends(시크릿_검사)])
    def ask(req: AskRequest) -> AskResponse:
        principal = 주체저장소.find(req.persona)
        if principal is None:
            # 어떤 이름이 존재하는지 알려주지 않는다.
            raise HTTPException(status_code=400, detail="알 수 없는 페르소나")

        ctx = AgentContext(principal=principal)
        결과 = 에이전트_공장().invoke(
            {"messages": [{"role": "user", "content": req.query}]}, context=ctx
        )
        return AskResponse(
            # .content 가 아니라 .text 다. Gemini 는 agentic 호출에서 리스트 모양
            # content(thinking + text 파트)를 내고, 그것이 str 로 선언된 필드에
            # 들어가면 검증이 실패해 500 이 된다. .text 는 텍스트 파트만 뽑고
            # 문자열 content 는 그대로 통과시킨다.
            answer=결과["messages"][-1].text,
            hits=[
                PolicyHitView(
                    chunk_id=h.chunk_id,
                    clause_code=h.clause_code,
                    doc_title=h.doc_title,
                    text=h.text,
                )
                for h in ctx.collected
            ],
            persona=PersonaView(
                name=req.persona,
                department=principal.department,
                clearance=principal.clearance,
            ),
            # ToolMessage 개수를 세면 상한에 막힌 호출도 잡혀 실제보다 많이
            # 보고된다. ctx.tool_calls 는 도구 본문이 실제로 실행됐을 때만 는다.
            tool_calls=ctx.tool_calls,
        )

    return app

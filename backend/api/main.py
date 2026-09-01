"""FastAPI 앱 — 얇은 HTTP 계층.

도메인 판단을 하지 않는다. 페르소나 이름을 Principal 로 바꾸고,
에이전트를 부르고, 결과를 직렬화한다.
"""

import os
from collections.abc import Callable

from fastapi import Depends, FastAPI, HTTPException

from adapters.agent.context import AgentContext
from api.schemas import AskRequest, AskResponse, PersonaView, PolicyHitView
from api.security import 시크릿_검사
from core.ports import PrincipalStore


def build_app(에이전트_공장: Callable[[], object], 주체저장소: PrincipalStore) -> FastAPI:
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
            "model": os.environ.get("SECUAGENT_MODEL_READY", "unknown"),
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
        도구_호출수 = sum(1 for m in 결과["messages"] if m.__class__.__name__ == "ToolMessage")
        return AskResponse(
            answer=결과["messages"][-1].content,
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
            tool_calls=도구_호출수,
        )

    return app

"""FastAPI 앱 — 얇은 HTTP 계층.

도메인 판단을 하지 않는다. 페르소나 이름을 Principal 로 바꾸고,
에이전트를 부르고, 결과를 직렬화한다.
"""

from collections.abc import Callable

from fastapi import Depends, FastAPI, HTTPException, Query

from adapters.agent.context import AgentContext
from api.schemas import (
    AccessRecordView,
    AskRequest,
    AskResponse,
    DocumentView,
    PersonaView,
    PolicyHitView,
    PrincipalView,
)
from api.security import 시크릿_검사
from core.ports import AccessLog, DocumentCatalog, PrincipalStore
from core.types import AccessRecord


def build_app(
    에이전트_공장: Callable[[], object],
    주체저장소: PrincipalStore,
    모델_준비됨: Callable[[], bool] = lambda: True,
    열람기록: AccessLog | None = None,
    카탈로그: DocumentCatalog | None = None,
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

        from core.agent.policy import AccessViolation

        try:
            결과 = 에이전트_공장().invoke(
                {"messages": [{"role": "user", "content": req.query}]}, context=ctx
            )
        except AccessViolation as e:
            # 사전 필터링이 깨졌다는 뜻이다. 기록하고 502 를 낸다 —
            # 사용자에게는 이유를 말하지 않는다.
            if 열람기록 is not None:
                try:
                    열람기록.record(
                        [
                            AccessRecord(
                                persona=req.persona,
                                department=principal.department,
                                clearance=principal.clearance,
                                query=req.query,
                                clause_code=None,
                                chunk_id=cid,
                                allowed=False,
                            )
                            for cid in _위반_chunk_id(e)
                        ]
                    )
                except Exception:
                    pass
            raise HTTPException(status_code=502, detail="요청을 처리하지 못했다") from None

        if 열람기록 is not None:
            # 기록 실패가 요청을 죽이면 안 된다. 곁가지다.
            try:
                열람기록.record(
                    [
                        AccessRecord(
                            persona=req.persona,
                            department=principal.department,
                            clearance=principal.clearance,
                            query=req.query,
                            clause_code=h.clause_code,
                            chunk_id=h.chunk_id,
                            allowed=True,
                        )
                        for h in ctx.collected
                    ]
                )
            except Exception:
                pass

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

    @app.get("/documents", dependencies=[Depends(시크릿_검사)])
    def documents() -> list[DocumentView]:
        """전체 문서 목록. 권한 필터를 적용하지 않는다 —

        문서 화면은 "이 페르소나에게 무엇이 보이는가"를 클라이언트가 계산해
        보여주는 화면이고, 그 계산의 입력이 필요하다. 검색 경로가 아니므로
        여기서 필터링하지 않는 것이 맞다. 대신 이 엔드포인트는 공유 시크릿
        뒤에 있고 본문을 돌려주지 않는다.
        """
        if 카탈로그 is None:
            raise HTTPException(status_code=503, detail="카탈로그 준비되지 않음")
        return [
            DocumentView(
                id=d.id,
                title=d.title,
                doc_type=d.doc_type,
                required_clearance=d.required_clearance,
                allowed_departments=d.allowed_departments,
                source_path=d.source_path,
                chunk_count=d.chunk_count,
            )
            for d in 카탈로그.documents()
        ]

    @app.get("/principals", dependencies=[Depends(시크릿_검사)])
    def principals() -> list[PrincipalView]:
        if 카탈로그 is None:
            raise HTTPException(status_code=503, detail="카탈로그 준비되지 않음")
        return [
            PrincipalView(name=p.name, department=p.department, clearance=p.clearance)
            for p in 카탈로그.principals()
        ]

    @app.get("/access-log", dependencies=[Depends(시크릿_검사)])
    def access_log(limit: int = Query(default=50, ge=1, le=200)) -> list[AccessRecordView]:
        if 열람기록 is None:
            raise HTTPException(status_code=503, detail="열람 기록 준비되지 않음")
        return [_기록으로(r) for r in 열람기록.recent(limit)]

    @app.get("/access-log/violations", dependencies=[Depends(시크릿_검사)])
    def access_violations(limit: int = Query(default=20, ge=1, le=200)) -> list[AccessRecordView]:
        if 열람기록 is None:
            raise HTTPException(status_code=503, detail="열람 기록 준비되지 않음")
        return [_기록으로(r) for r in 열람기록.violations(limit)]

    return app


def _기록으로(r: AccessRecord) -> AccessRecordView:
    return AccessRecordView(
        persona=r.persona,
        department=r.department,
        clearance=r.clearance,
        query=r.query,
        clause_code=r.clause_code,
        chunk_id=r.chunk_id,
        allowed=r.allowed,
    )


def _위반_chunk_id(e: Exception) -> list[int]:
    """AccessViolation 메시지에서 chunk_id 만 뽑는다.

    메시지는 f"권한 밖 청크가 도구 출력에 섞였다: [1, 2] …" 형태다.
    파싱이 실패해도 기록은 남겨야 하므로 빈 리스트로 물러선다.
    """
    import re

    m = re.search(r"\[([\d,\s]*)\]", str(e))
    if not m or not m.group(1).strip():
        return []
    return [int(x) for x in m.group(1).split(",") if x.strip()]

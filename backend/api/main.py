"""FastAPI 앱 — 얇은 HTTP 계층.

도메인 판단을 하지 않는다. 페르소나 이름을 Principal 로 바꾸고,
에이전트를 부르고, 결과를 직렬화한다.
"""

import logging
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query

from adapters.agent.context import AgentContext
from api.schemas import (
    AccessRecordView,
    AskRequest,
    AskResponse,
    DocumentView,
    LogEventView,
    PersonaView,
    PolicyHitView,
    PrincipalView,
)
from api.security import 시크릿_검사
from core.agent.policy import 로그_범위_고지
from core.ports import AccessLog, DocumentCatalog, LogSearch, PrincipalStore
from core.types import AccessRecord

# 애플리케이션 로그가 하나도 없었다 — 실패하면 uvicorn 의 액세스 로그 한 줄
# ("POST /ask 502") 만 남고 무엇이 왜 터졌는지는 stdout 에 아무것도 없었다.
logger = logging.getLogger("secu_agent.api")


def build_app(
    에이전트_공장: Callable[[], object],
    주체저장소: PrincipalStore,
    모델_준비됨: Callable[[], bool] = lambda: True,
    열람기록: AccessLog | None = None,
    카탈로그: DocumentCatalog | None = None,
    데모_라우터: APIRouter | None = None,
    로그검색: LogSearch | None = None,
) -> FastAPI:
    """앱을 조립한다. 의존성을 인자로 받아 테스트가 스텁을 넣을 수 있다."""
    # 스키마 문서를 끈다. 데이터 엔드포인트는 전부 공유 시크릿 뒤에 있지만,
    # /openapi.json 은 그 시크릿을 **어느 헤더에 달아야 하는지**까지 포함해
    # 전체 API 를 인증 없이 알려준다. 이 백엔드는 Cloudflare 터널로 공개돼
    # 있고, 컨테이너 로그에 실제로 /openapi.json · /docs · /redoc 을 읽고
    # /ask 를 시도한 흔적이 남아 있다.
    app = FastAPI(title="secu-agent", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/healthz")
    def healthz() -> dict:
        # **model 을 먼저 본다.** 순서가 의미를 만든다.
        #
        # 예전에는 DB 왕복이 먼저였고, 그 호출이 자원을 resolve 하면서
        # 임베더까지 만들었다. 그래서 db=True 면 model 은 언제나 "ready",
        # db=False 면 언제나 "loading" 이었다 — 두 필드가 같은 사실을 두 번
        # 말할 뿐이라, 주석이 말하던 "cold start 인지 배포가 깨졌는지 구분"
        # 은 실현되지 않았다.
        #
        # 아무것도 만들지 않고 상태만 읽으면 그 구분이 생긴다: 모델이 아직
        # 없는데 DB 는 살아 있는 상태(콜드 스타트 중)가 관측된다.
        model_ok = 모델_준비됨()

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
            "model": "ready" if model_ok else "loading",
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
            #
            # stdout 에도 남긴다. access_records 테이블에만 두면 그 기록마저
            # 실패했을 때(아래 except) 사건 자체가 사라진다. 본문·호스트·문서
            # 제목은 담지 않는다 — 예외가 우회 경로가 되면 안 된다.
            logger.error("권한 위반: persona=%s kind=%s ids=%s", req.persona, e.kind, e.ids)
            # 사용자에게는 이유를 말하지 않는다.
            #
            # 종류와 id 는 예외가 구조로 들고 온다. 메시지를 정규식으로 파면
            # 청크 id 와 로그 이벤트 id 가 같은 모양이라 구별되지 않는다.
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
                                resource_kind=e.kind,
                                resource_id=rid,
                                allowed=False,
                            )
                            for rid in e.ids
                        ]
                    )
                except Exception:
                    # 기록 실패가 요청을 죽이면 안 된다. 그래도 조용히
                    # 삼키면 "위반이 없었다"와 구별되지 않는다.
                    logger.warning("권한 위반 기록 실패: persona=%s", req.persona, exc_info=True)
            raise HTTPException(status_code=502, detail="요청을 처리하지 못했다") from None
        except HTTPException:
            raise
        except Exception:
            # AccessViolation 외의 모든 실패 — Gemini 타임아웃·인증 오류, DB
            # 끊김, 그래프가 빈 messages 를 돌려줄 때의 IndexError 등.
            #
            # 지금까지 이것들은 FastAPI 기본 500 으로 나갔다. 그러면 사용자와
            # 운영자 모두 502(권한 사고 — 조사해야 함)와 그 밖 전부(외부 의존이
            # 흔들림 — 다시 시도하면 됨)를 응답만 보고 구별할 수 없다.
            # 503 으로 나누고, 이유는 여전히 말하지 않는다 — 예외 본문에
            # 문서 제목이나 페르소나가 섞여 나갈 수 있다.
            logger.exception("ask 실패: persona=%s", req.persona)
            raise HTTPException(status_code=503, detail="일시적으로 처리할 수 없다") from None

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
                            resource_kind="chunk",
                            resource_id=h.chunk_id,
                            allowed=True,
                        )
                        for h in ctx.collected
                    ]
                )
            except Exception:
                logger.warning("열람 기록 실패: persona=%s", req.persona, exc_info=True)

        log_scope = 로그_범위_고지 if ctx.queried_logs else None

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
            log_scope=log_scope,
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

    @app.get("/log-events", dependencies=[Depends(시크릿_검사)])
    def log_events(
        persona: str,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> list[LogEventView]:
        """**주체 없이 부를 수 없다.** persona 가 필수 쿼리 인자인 이유가
        그것이다 — 기본값을 주면 그 기본값이 곧 권한 우회 경로가 된다.
        """
        if 로그검색 is None:
            raise HTTPException(status_code=503, detail="로그 검색 준비되지 않음")
        principal = 주체저장소.find(persona)
        if principal is None:
            raise HTTPException(status_code=400, detail="알 수 없는 페르소나")

        from core.agent.policy import AccessViolation, enforce_events

        # SQL 이 이미 걸렀다. 그래도 다시 본다 — 도구 경로(core/agent/tools.py)가
        # 같은 이유로 그렇게 한다(상위 spec 5.4). 이 경로는 raw(로그 전문)를
        # 그대로 돌려주므로, SQL 쪽이 회귀하면 /ask 는 502 로 시끄럽게 죽는데
        # 여기만 200 OK 로 권한 밖 호스트의 원문을 조용히 내보낸다.
        try:
            이벤트 = enforce_events(로그검색.query(principal, event_type, since, limit), principal)
        except AccessViolation:
            # /ask 와 같은 판단이다 — 이유를 말하지 않고 502.
            raise HTTPException(status_code=502, detail="요청을 처리하지 못했다") from None

        return [
            LogEventView(
                id=e.id,
                ts=e.ts,
                host=e.host,
                process=e.process,
                event_type=e.event_type,
                raw=e.raw,
            )
            for e in 이벤트
        ]

    if 데모_라우터 is not None:
        # main.py 는 demo 를 모른다 — 라우터는 api/demo.py 가 만들어 주입한다.
        app.include_router(데모_라우터)

    return app


def _기록으로(r: AccessRecord) -> AccessRecordView:
    return AccessRecordView(
        persona=r.persona,
        department=r.department,
        clearance=r.clearance,
        query=r.query,
        clause_code=r.clause_code,
        resource_kind=r.resource_kind,
        resource_id=r.resource_id,
        allowed=r.allowed,
        ts=r.ts,
    )

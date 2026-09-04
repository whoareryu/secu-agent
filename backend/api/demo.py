"""데모 비교 API 라우터.

`demo` 패키지를 직접 import 하는 유일한 파일이다 — tests/test_demo_isolation.py 가
집합 동일성으로 강제한다. 그 목록에는 이 파일과 api/deps.py 둘이 올라 있다:
`from api.demo import compare` 도 순진한 경로에 한 홉이라, 이 파일을 아는
조립 지점까지 같이 세어야 울타리가 실제 도달 거리를 재게 된다.
main.py 는 이 라우터를 모른 채 조립만 하고, api/deps.py 가 실제 conn·embedder
를 쥔 채 여기서 라우터를 만들어 주입한다.

세션·관리자 검사는 BFF(Vercel Route Handler) 쪽에서 한다. 여기서는
다른 엔드포인트와 같은 공유 시크릿만 본다.
"""

from collections.abc import Callable

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from api.schemas import CompareRequest, CompareResponse, DemoPathResult, DemoPersonaView
from api.security import 시크릿_검사
from core.ports import Embedder, PrincipalStore
from demo.compare import compare, 시연_질의

# 응답 순서가 계약이다(test_세_페르소나가_모두_나온다) — 상수로 고정한다.
# department·clearance 는 여기 적지 않는다 — 클라이언트가 권한 값을 실어
# 보낼 수 있으면 그것이 사칭 경로라는 api/schemas.py 의 원칙이 서버 내부의
# 하드코딩에도 같은 이유로 적용된다. 아래에서 주체저장소로 조회한다.
_페르소나_이름 = ("김개발", "박인사", "최임원")


def build_demo_router(
    자원: Callable[[], tuple[psycopg.Connection, Embedder]],
    주체저장소: PrincipalStore,
) -> APIRouter:
    """비교 라우터를 조립한다.

    `자원` 을 라우터 생성 시점이 아니라 요청 시점에 부른다 — api/deps.py 의
    `_자원()` 을 import 시점에 부르지 않는다는 규율을 여기서도 지킨다.
    """
    router = APIRouter(dependencies=[Depends(시크릿_검사)])

    @router.post("/demo/compare", response_model=CompareResponse)
    def demo_compare(req: CompareRequest) -> CompareResponse:
        # 목록 길이를 아는 것은 demo 패키지다. api/schemas.py 에 상한을 적으면
        # 그 파일이 demo 를 import 해야 하고, 그 순간 tests/test_demo_isolation.py
        # 의 "demo 에 닿는 api/ 파일은 정확히 둘" 이 깨진다.
        if req.demo_index >= len(시연_질의):
            raise HTTPException(status_code=422, detail="시연 질의 범위 밖")
        질의 = 시연_질의[req.demo_index]

        principals = []
        for 이름 in _페르소나_이름:
            p = 주체저장소.find(이름)
            if p is None:
                raise HTTPException(status_code=503, detail="데모 페르소나가 준비되지 않음")
            principals.append((이름, p))

        conn, embedder = 자원()
        결과 = compare(conn, embedder, 질의, req.k, principals)

        return CompareResponse(
            query=결과["query"],
            k=결과["k"],
            personas=[
                DemoPersonaView(
                    name=p["name"],
                    department=p["department"],
                    clearance=p["clearance"],
                    prefiltered=DemoPathResult(
                        count=p["prefiltered"].count,
                        clause_codes=p["prefiltered"].clause_codes,
                    ),
                    naive=DemoPathResult(
                        count=p["naive"].count,
                        clause_codes=p["naive"].clause_codes,
                    ),
                )
                for p in 결과["personas"]
            ],
        )

    return router

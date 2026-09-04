"""HTTP 경계의 타입.

AskRequest 에 department·clearance 가 **없다**. 클라이언트가 그것을
보낼 수 있으면 그 값이 곧 사칭 경로다. 페르소나 이름만 받고 서버가
principals 테이블에서 번역한다.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    persona: str = Field(min_length=1, max_length=50)


class PolicyHitView(BaseModel):
    chunk_id: int
    clause_code: str | None
    doc_title: str
    text: str


class PersonaView(BaseModel):
    name: str
    department: str
    clearance: int


class AskResponse(BaseModel):
    answer: str
    hits: list[PolicyHitView]
    persona: PersonaView
    tool_calls: int
    # query_logs 가 불렸을 때만 채운다. 모델의 문장이 아니라 서버가 싣는다 —
    # 모델은 고지를 잊는다(보충 spec 2.4).
    log_scope: str | None = None


class DocumentView(BaseModel):
    id: int
    title: str
    doc_type: str
    required_clearance: int
    allowed_departments: tuple[str, ...]
    source_path: str
    chunk_count: int


class PrincipalView(BaseModel):
    name: str
    department: str
    clearance: int
    role: str


class AccessRecordView(BaseModel):
    persona: str
    department: str
    clearance: int
    query: str
    clause_code: str | None
    # 열람 대상. 종류가 없으면 화면이 로그 이벤트 id 를 청크로 푼다 —
    # 두 id 공간이 겹친다.
    resource_kind: str
    resource_id: int
    allowed: bool
    ts: datetime | None = None


class LogEventView(BaseModel):
    id: int
    ts: datetime | None
    host: str
    process: str | None
    event_type: str
    raw: str


class CompareRequest(BaseModel):
    # **질의 문자열을 받지 않는다.** AskRequest 가 department·clearance 를 받지
    # 않는 것과 같은 종류의 결정이다 — 클라이언트가 정할 수 있는 값이 곧
    # 공격면이 된다. 이 비교는 세 계정의 결과를 한 응답에 담으므로, 질의가
    # 자유 입력이면 등급 밖 조항 코드를 임의 주제로 열거할 수 있는 존재
    # 오라클이 된다(demo/compare.py 의 시연_질의 주석에 실측 재현이 있다).
    #
    # 인덱스만 받고 문자열은 서버가 고른다. 상한은 여기가 아니라 api/demo.py
    # 가 건다 — 목록 길이를 아는 것은 demo 패키지이고, 이 파일이 그것을
    # import 하면 tests/test_demo_isolation.py 의 울타리가 깨진다.
    demo_index: int = Field(ge=0)
    # k 에 le 를 걸지 않는다. 걸면 큰 값이 422 로 막혀버려 "받아서 깎는다"가
    # 아니라 "거부한다"가 되고, 브라우저가 보내는 값을 못 믿는다는 전제와
    # 어긋난다. 상한은 demo/compare.py 의 MAX_DEMO_K clamp 가 건다.
    k: int


class DemoPathResult(BaseModel):
    count: int
    clause_codes: list[str]


class DemoPersonaView(BaseModel):
    name: str
    department: str
    clearance: int
    prefiltered: DemoPathResult
    naive: DemoPathResult


class CompareResponse(BaseModel):
    query: str
    k: int
    personas: list[DemoPersonaView]

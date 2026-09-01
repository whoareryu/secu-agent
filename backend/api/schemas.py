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


class AccessRecordView(BaseModel):
    persona: str
    department: str
    clearance: int
    query: str
    clause_code: str | None
    chunk_id: int
    allowed: bool
    ts: datetime | None = None

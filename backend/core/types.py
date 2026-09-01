"""도메인 엔티티와 값 객체.

표준 라이브러리만 쓴다. DB 도 임베딩 모델도 프레임워크도 모른다 —
그 사실을 tests/test_boundaries.py 가 강제한다.
"""

from dataclasses import dataclass
from datetime import datetime

# 임베딩 벡터 차원. intfloat/multilingual-e5-small 은 384 다.
# 모델을 바꾸면 이 상수와 db/schema.sql 의 vector(N), 그리고 이미 적재된
# 벡터를 전부 함께 바꿔야 한다.
EMBEDDING_DIM: int = 384


@dataclass(frozen=True)
class Principal:
    """검색을 수행하는 주체.

    department: "보안팀" · "인사팀" · "개발팀"
    clearance:  1(사원) · 2(팀장) · 3(임원)

    이 두 값이 단순한 이유가 있다 — 가시성 규칙이 SQL WHERE 로 그대로
    번역되어야 사전 필터링이 된다(spec 3.1). 복잡해지면 애플리케이션
    레이어로 밀려나고, 그 순간 사후 필터링이 되어 존재가 누출된다.
    """

    department: str
    clearance: int


@dataclass(frozen=True)
class Document:
    id: int
    title: str
    source_path: str
    doc_type: str  # "pdf" | "docx" | "md"
    required_clearance: int
    allowed_departments: tuple[str, ...]  # 비어 있으면 전사 공개


@dataclass(frozen=True)
class Clause:
    """규정 조항. ISMS-P 의 "2.6.1 네트워크 접근" 같은 단위."""

    code: str
    title: str
    text: str


@dataclass(frozen=True)
class Chunk:
    """임베딩 단위.

    clause_code 를 들고 다니는 이유: 이것이 없으면 리포트에서
    "규정 2.6.1 위반"이라고 쓸 수 없고 "어딘가에 이런 내용이 있다"까지만
    쓰게 된다. 표지·목차처럼 조항 밖 텍스트는 None 이다.
    """

    clause_code: str | None
    ordinal: int
    text: str


@dataclass(frozen=True)
class PolicyHit:
    """검색 결과 한 건.

    점수를 담지 않는다 — 리스트의 순서가 곧 순위이고, RRF 점수 자체를
    화면에 보여줄 일이 없다.

    권한 메타 두 필드를 담는 이유: core/agent/policy.py 의 enforce 가
    도구 출력을 재검증하려면 판단 근거가 결과 안에 있어야 한다(spec 5.4).
    없으면 enforce 는 DB 를 다시 부르거나 전부 통과시키는 수밖에 없고,
    둘 다 재검증이 아니다.

    기본값을 주지 않는다. 기본값이 있으면 새 호출자가 권한 메타를 빠뜨려도
    조용히 "등급 1 · 전사 공개"로 만들어지고, enforce 는 그것을 통과시킨다.
    """

    chunk_id: int
    text: str
    doc_title: str
    clause_code: str | None
    required_clearance: int
    allowed_departments: tuple[str, ...]


@dataclass(frozen=True)
class DocumentRow:
    """문서 목록 한 줄. 문서 화면이 쓴다.

    본문을 담지 않는다 — 목록은 어떤 문서가 있는지만 보여준다.
    """

    id: int
    title: str
    doc_type: str
    required_clearance: int
    allowed_departments: tuple[str, ...]
    source_path: str
    chunk_count: int


@dataclass(frozen=True)
class PrincipalRow:
    name: str
    department: str
    clearance: int


@dataclass(frozen=True)
class AccessRecord:
    """열람 기록 한 줄. 관리자 대시보드가 읽는다.

    text 도 doc_title 도 없다. 기록이 문서 본문이나 제목을 담으면 그 테이블이
    곧 권한 우회 경로가 된다 — 제목만으로도 존재가 드러난다.

    ts 가 선택인 이유: DB 가 DEFAULT now() 로 채운다. 쓰기 경로는 값을 주지
    않고, 읽기 경로만 채워서 돌려준다.
    """

    persona: str
    department: str
    clearance: int
    query: str
    clause_code: str | None
    chunk_id: int
    allowed: bool
    ts: datetime | None = None

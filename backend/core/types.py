"""도메인 엔티티와 값 객체.

표준 라이브러리만 쓴다. DB 도 임베딩 모델도 프레임워크도 모른다 —
그 사실을 tests/test_boundaries.py 가 강제한다.
"""

from dataclasses import dataclass

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
    doc_type: str                       # "pdf" | "docx" | "md"
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
    화면에 보여줄 일이 없다. 나중에 필요해지면 그때 더한다.
    """

    chunk_id: int
    text: str
    doc_title: str
    clause_code: str | None

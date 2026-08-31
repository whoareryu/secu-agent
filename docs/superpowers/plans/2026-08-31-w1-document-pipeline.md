# W1 구현 계획 — 문서 파이프라인과 하이브리드 검색

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ISMS-P 인증기준 안내서(255쪽)를 조항 단위로 쪼개 pgvector 에 적재하고, 벡터·키워드 하이브리드 검색이 동작하게 한다.

**Architecture:** `core/` 는 표준 라이브러리만 쓰는 순수 도메인이고 경계를 테스트가 강제한다. 문서 포맷은 `adapters/parsing/`, DB 는 `adapters/db/`, 임베딩은 `adapters/embedding/` 이 안다. `pipeline/` 은 `core/ports` 의 포트만 주입받아 조립한다. 권한 필터는 W2 에서 붙이되, **검색 시그니처는 이번 주에 `Principal` 을 이미 받는다** — 나중에 끼워 넣으면 빠뜨린 경로가 생긴다.

**Tech Stack:** Python 3.12, psycopg 3, pgvector, pypdf, sentence-transformers(multilingual-e5-small), pytest

**Spec:** `docs/superpowers/specs/2026-08-31-secu-agent-design.md`

## Global Constraints

- Python 3.12 이상. 가상환경은 `backend/.venv`, 실행은 `.venv/bin/python`, 작업 디렉토리는 `backend/`.
- **`core/` 는 바깥 계층(`adapters`·`api`·`pipeline`·`eval`)을 import 하지 않는다.**
- **`core/` 는 인프라·프레임워크(`psycopg`·`sqlalchemy`·`anthropic`·`fastapi`·`langchain`·`langgraph`·`sentence_transformers`·`torch`·`transformers`·`pypdf`)를 import 하지 않는다.**
- 경계 인터페이스는 `core/ports.py` 가 소유한다. `adapters/` 가 구현한다.
- 임베딩 차원은 `core/types.EMBEDDING_DIM`(384)이 단일 출처다. 모델은 `intfloat/multilingual-e5-small`.
- **e5 계열은 `query:` / `passage:` 접두어를 요구한다.** 접두어를 빼면 검색 품질이 조용히 나빠진다.
- 검색 함수는 처음부터 `Principal` 을 필수 인자로 받는다 (spec 5.3).
- 테스트 함수 이름은 한국어로 쓴다.
- 커밋 메시지는 한국어, 평서형(`~했다`).

---

## File Structure

```
docker-compose.yml            (루트) pgvector 컨테이너
backend/
  core/
    types.py                  Principal · Document · Clause · Chunk · EMBEDDING_DIM
    ports.py                  DocumentStore · ChunkSearch · Embedder
    retrieve/
      fusion.py               RRF — 순위 리스트만 받는 순수 함수
  adapters/
    parsing/
      pdf.py                  PDF → 조항 분할 → 청크
      loader.py               확장자로 파서 선택
    db/
      connection.py           psycopg 연결 · 스키마 적용
      document_store.py       DocumentStore 구현
      chunk_search.py         ChunkSearch 구현 (벡터 · 키워드)
    embedding/
      e5.py                   Embedder 구현 (query/passage 접두어)
  pipeline/
    ingest.py                 파서 → 임베딩 → 저장 오케스트레이션
    cli.py                    python -m pipeline.cli ingest <path>
  db/
    schema.sql
  tests/
    test_boundaries.py        계층 경계 강제
    test_types.py             도메인 타입
    test_fusion.py            RRF
    test_pdf_parsing.py       조항 분할 (픽스처 PDF)
    test_ingest.py            오케스트레이션 (스텁 포트)
    test_db_integration.py    실제 DB (db 마커)
    test_search_integration.py 하이브리드 검색 (db 마커)
```

**책임 분리 근거:** `parsing/` 과 `db/` 를 나눈 것은 변경 이유가 다르기 때문이다 — 문서 포맷은 DOCX·MD 를 더할 때, DB 어댑터는 스키마를 바꿀 때 변한다. `fusion.py` 가 DB 를 모르는 것은 의도적이다 — 순위 병합이 가장 버그가 나기 쉬워 DB 없이 테스트되어야 한다.

---

### Task 1: 스캐폴딩과 계층 경계 테스트

**Files:**
- Modify: `backend/pyproject.toml`, `backend/requirements.txt`, `backend/requirements-dev.txt`
- Create: `backend/core/__init__.py`, `backend/adapters/__init__.py`, `backend/pipeline/__init__.py`, `backend/eval/__init__.py`
- Test: `backend/tests/test_boundaries.py`

**Interfaces:**
- Consumes: 없음
- Produces: 없음 (검사 전용)

경계를 나중에 검사하면 이미 어긴 코드를 고치게 된다. **먼저 그물을 치고 그 안에서 짓는다.**

- [ ] **Step 1: 의존성을 정리한다**

`backend/pyproject.toml` 의 `dependencies` 를 아래로 교체한다. 임베딩이 런타임 필수라 `sentence-transformers` 가 기본 그룹에 들어간다.

```toml
dependencies = [
    "psycopg[binary]>=3.2",
    "pypdf>=5.1",
    "sentence-transformers>=3.3",
]
```

`[dependency-groups]` 의 `finetune` 은 지운다 — 이 프로젝트에 파인튜닝은 없다. `dev` 는 그대로 둔다.

`markers` 에 `db` 를 더한다:

```toml
markers = [
    "llm: 실제 LLM API 를 호출하는 테스트 (기본 제외)",
    "db: 실제 데이터베이스가 필요한 테스트 (기본 제외)",
]
addopts = "-m 'not llm and not db'"
```

**DB 테스트를 기본 제외하는 이유:** 컨테이너가 없는 환경(CI, 남의 체크아웃)에서 스위트 전체가 실패하면 안 된다.

`backend/requirements.txt`:

```
psycopg[binary]>=3.2
pypdf>=5.1
sentence-transformers>=3.3
```

`backend/requirements-finetune.txt` 는 삭제한다.

- [ ] **Step 2: 패키지 디렉토리를 만들고 설치한다**

```bash
cd backend
mkdir -p core/retrieve adapters/{parsing,db,embedding} pipeline db tests
touch core/__init__.py core/retrieve/__init__.py \
      adapters/__init__.py adapters/parsing/__init__.py \
      adapters/db/__init__.py adapters/embedding/__init__.py \
      pipeline/__init__.py eval/__init__.py
rm -f requirements-finetune.txt
uv sync
```

- [ ] **Step 3: 경계 테스트를 쓴다**

`backend/tests/test_boundaries.py`:

```python
"""계층 경계를 CI 가 강제한다.

spec 2.4 의 규칙을 문서가 아니라 테스트로 만든다. 방침만 적어두면 지켜지지 않는다.
"""

import ast
from pathlib import Path

import pytest

# core/ 는 안쪽이다. 이 이름들은 전부 바깥이다.
바깥_계층 = ("adapters", "api", "pipeline", "eval")

# core/ 에 들어오는 순간 경계가 무너지는 것들.
# langchain 이 여기 있는 것이 핵심이다 — 프레임워크가 도메인에 스며들면
# 버전이 바뀔 때 도메인 로직까지 끌려간다(spec 2.3).
인프라_프레임워크 = (
    "psycopg",
    "sqlalchemy",
    "anthropic",
    "fastapi",
    "langchain",
    "langgraph",
    "sentence_transformers",
    "torch",
    "transformers",
    "pypdf",
)


def _최상위_import(py: Path) -> list[str]:
    """파일이 import 하는 모듈들의 최상위 이름."""
    tree = ast.parse(py.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            # `from . import x` 만 건너뛴다 — 이때만 node.module 이 None 이다.
            # level 로 거르면 안 된다: `from ..adapters import X` 는
            # level=2, module='adapters' 라 검사를 통째로 빠져나간다.
            if node.module:
                names.append(node.module)
    return [n.split(".")[0] for n in names]


def _core_파일들() -> list[Path]:
    return sorted(Path("core").rglob("*.py"))


def test_core_에_검사할_파일이_있다():
    # 파일이 0개면 아래 두 테스트가 공허하게 통과한다.
    assert _core_파일들(), "core/ 에 파이썬 파일이 없다"


@pytest.mark.parametrize("py", _core_파일들(), ids=lambda p: str(p))
def test_core_는_바깥_계층을_import_하지_않는다(py):
    for name in _최상위_import(py):
        assert name not in 바깥_계층, f"{py} 가 바깥 계층 {name} 을 import 한다"


@pytest.mark.parametrize("py", _core_파일들(), ids=lambda p: str(p))
def test_core_는_인프라_프레임워크를_import_하지_않는다(py):
    for name in _최상위_import(py):
        assert name not in 인프라_프레임워크, f"{py} 가 {name} 을 import 한다"
```

- [ ] **Step 4: 테스트가 실패하는지 확인한다**

Run: `.venv/bin/python -m pytest tests/test_boundaries.py -v`

Expected: FAIL — `core/ 에 파이썬 파일이 없다`. `core/__init__.py` 는 만들었지만 `rglob` 이 잡으므로 통과할 수도 있다. 그 경우 나머지 두 테스트가 파일 1개에 대해 통과한다.

- [ ] **Step 5: 테스트가 실제로 위반을 잡는지 확인한다**

통과하는 테스트는 그 자체로 아무것도 증명하지 않는다. **일부러 어겨본다.**

```bash
echo "import langchain" >> core/__init__.py
.venv/bin/python -m pytest tests/test_boundaries.py -q
```

Expected: FAIL — `core/__init__.py 가 langchain 을 import 한다`

원복하고 다시 확인한다:

```bash
git checkout core/__init__.py 2>/dev/null || : > core/__init__.py
.venv/bin/python -m pytest tests/test_boundaries.py -q
```

Expected: PASS

- [ ] **Step 6: 커밋한다**

```bash
cd /Users/ryujun/Documents/secu-agent
git add backend/
git commit -m "패키지 골격과 계층 경계 테스트를 추가했다

core/ 가 바깥 계층이나 인프라·프레임워크를 import 하면 CI 가 실패한다.
금지 목록에 langchain·langgraph 를 넣은 것이 핵심이다 — 프레임워크가
도메인에 스며들면 버전이 바뀔 때 도메인 로직까지 끌려간다.

파일별로 parametrize 해서 어느 파일이 어겼는지 실패 메시지에 나온다.
core/ 에 파일이 없으면 나머지 테스트가 공허하게 통과하므로 그것도 검사한다.

일부러 core/__init__.py 에 import langchain 을 넣어 실패를 확인하고 원복했다.

임베딩이 런타임 필수라 sentence-transformers 를 기본 의존성으로 옮기고,
파인튜닝 그룹은 지웠다 — 이 프로젝트에 학습은 없다."
```

---

### Task 2: 도메인 타입과 포트

**Files:**
- Create: `backend/core/types.py`, `backend/core/ports.py`
- Test: `backend/tests/test_types.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `core.types.EMBEDDING_DIM: int` = 384
  - `core.types.Principal` — frozen dataclass(`department: str`, `clearance: int`)
  - `core.types.Document` — frozen dataclass(`id`, `title`, `source_path`, `doc_type`, `required_clearance`, `allowed_departments`)
  - `core.types.Clause` — frozen dataclass(`code: str`, `title: str`, `text: str`)
  - `core.types.Chunk` — frozen dataclass(`clause_code`, `ordinal`, `text`)
  - `core.types.PolicyHit` — frozen dataclass(`chunk_id`, `text`, `doc_title`, `clause_code`)
  - `core.ports.Embedder` — Protocol, `encode(texts, kind) -> list[list[float]]`
  - `core.ports.DocumentStore` — Protocol, `upsert_document`, `insert_clauses`, `insert_chunks`, `count_chunks`
  - `core.ports.ChunkSearch` — Protocol, `by_vector`, `by_keyword`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_types.py`:

```python
import dataclasses

import pytest

from core.ports import ChunkSearch, DocumentStore, Embedder
from core.types import EMBEDDING_DIM, Chunk, Clause, Document, PolicyHit, Principal


def test_임베딩_차원이_384_다():
    # multilingual-e5-small 의 차원. db/schema.sql 의 vector(N) 과 일치해야 한다.
    assert EMBEDDING_DIM == 384


def test_주체는_부서와_등급을_갖고_불변이다():
    p = Principal(department="보안팀", clearance=2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.clearance = 3


def test_문서의_허용부서가_비면_전사_공개다():
    d = Document(
        id=1,
        title="ISMS-P 인증기준 안내서",
        source_path="data/raw/ismsp.pdf",
        doc_type="pdf",
        required_clearance=1,
        allowed_departments=(),
    )
    assert d.allowed_departments == ()


def test_조항은_코드와_제목과_본문을_갖는다():
    c = Clause(code="2.6.1", title="네트워크 접근", text="네트워크에 대한 비인가 접근을...")
    assert c.code == "2.6.1"
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.code = "x"


def test_청크는_조항_코드를_들고_다닌다():
    # 조항 코드가 없으면 리포트에서 "규정 2.6.1 위반"이라고 못 쓴다.
    ch = Chunk(clause_code="2.6.1", ordinal=0, text="본문 일부")
    assert ch.clause_code == "2.6.1"


def test_조항에_속하지_않는_청크도_허용된다():
    # 표지·목차처럼 조항 밖 텍스트가 있다.
    ch = Chunk(clause_code=None, ordinal=0, text="목차")
    assert ch.clause_code is None


def test_검색_결과는_조항_코드를_들고_다닌다():
    # 조항 코드가 없으면 리포트에서 "규정 2.6.1 위반"이라고 못 쓴다.
    h = PolicyHit(chunk_id=1, text="본문", doc_title="ISMS-P", clause_code="2.6.1")
    assert h.clause_code == "2.6.1"
    with pytest.raises(dataclasses.FrozenInstanceError):
        h.text = "x"


def test_조항_밖_결과는_코드가_None_이다():
    h = PolicyHit(chunk_id=1, text="목차", doc_title="ISMS-P", clause_code=None)
    assert h.clause_code is None


def test_포트를_스텁이_만족한다():
    class 임베더:
        def encode(self, texts, kind):
            return [[0.0] * EMBEDDING_DIM for _ in texts]

    class 저장소:
        def upsert_document(self, doc):
            return 1

        def insert_clauses(self, document_id, clauses):
            return {c.code: i for i, c in enumerate(clauses, start=1)}

        def insert_chunks(self, document_id, clause_ids, chunks, vectors):
            return len(chunks)

        def count_chunks(self):
            return 0

    class 검색기:
        def by_vector(self, vec, p, k):
            return []

        def by_keyword(self, q, p, k):
            return []

    assert isinstance(임베더(), Embedder)
    assert isinstance(저장소(), DocumentStore)
    assert isinstance(검색기(), ChunkSearch)


def test_포트를_만족하지_않으면_False_다():
    class 빈것:
        pass

    assert not isinstance(빈것(), Embedder)
    assert not isinstance(빈것(), DocumentStore)
    assert not isinstance(빈것(), ChunkSearch)
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `.venv/bin/python -m pytest tests/test_types.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'core.types'`

- [ ] **Step 3: `core/types.py` 를 쓴다**

```python
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
```

- [ ] **Step 4: `core/ports.py` 를 쓴다**

```python
"""경계 인터페이스.

안쪽 계층이 인터페이스를 소유하고 바깥 계층이 구현한다. 그래야 의존성이
항상 안쪽을 향한다 — adapters/ 는 core 를 알지만 core 는 psycopg 도,
sentence-transformers 도, LangChain 도 모른다.

여기 선언된 Protocol 은 전부 최소 두 구현을 갖는다: 실제 어댑터와 테스트
스텁. 한 번만 쓰는 추상화가 아니다.

@runtime_checkable 은 테스트가 스텁의 포트 만족을 확인하기 위해서다.
isinstance 는 메서드 존재만 보고 시그니처는 보지 않는다 — 시그니처는
실제 호출로 검증한다.
"""

from collections.abc import Sequence
from typing import Literal, Protocol, runtime_checkable

from core.types import Chunk, Clause, Document, Principal

Vector = list[float]


@runtime_checkable
class Embedder(Protocol):
    def encode(self, texts: Sequence[str], kind: Literal["query", "passage"]) -> list[Vector]:
        """e5 계열은 query/passage 접두어를 요구한다 — 그 사실을 포트가 드러낸다.

        접두어를 빼면 검색 품질이 조용히 나빠진다. 시그니처로 강제한다.
        """
        ...


@runtime_checkable
class DocumentStore(Protocol):
    def upsert_document(self, doc: Document) -> int:
        """문서를 저장하고 id 를 돌려준다. 같은 source_path 는 갱신한다."""
        ...

    def insert_clauses(self, document_id: int, clauses: Sequence[Clause]) -> dict[str, int]:
        """조항을 저장하고 code -> id 를 돌려준다."""
        ...

    def insert_chunks(
        self,
        document_id: int,
        clause_ids: dict[str, int],
        chunks: Sequence[Chunk],
        vectors: Sequence[Vector],
    ) -> int:
        """청크와 벡터를 저장하고 저장한 개수를 돌려준다."""
        ...

    def count_chunks(self) -> int: ...


@runtime_checkable
class ChunkSearch(Protocol):
    def by_vector(self, vec: Vector, principal: Principal, k: int) -> list[int]:
        """코사인 유사도 상위 k 개 chunk id.

        principal 이 필수 인자인 것이 중요하다 — 권한 없는 검색을 호출하는
        방법이 없다(spec 5.3). W1 에서는 필터가 아직 통과만 시키지만,
        시그니처는 처음부터 갖춘다. 나중에 끼워 넣으면 빠뜨린 경로가 생긴다.
        """
        ...

    def by_keyword(self, query: str, principal: Principal, k: int) -> list[int]: ...
```

- [ ] **Step 5: 테스트가 통과하는지 확인한다**

Run: `.venv/bin/python -m pytest tests/test_types.py tests/test_boundaries.py -v`

Expected: PASS. 경계 테스트도 함께 돌려 `core/` 가 규칙을 지키는지 본다.

- [ ] **Step 6: 커밋한다**

```bash
git add backend/core/ backend/tests/test_types.py
git commit -m "도메인 타입과 경계 포트를 추가했다

Principal 을 부서·등급 두 값으로 단순하게 유지했다. 가시성 규칙이 SQL
WHERE 로 그대로 번역되어야 사전 필터링이 되기 때문이다 — 복잡해지면
애플리케이션 레이어로 밀려나고 그 순간 사후 필터링이 되어 존재가 누출된다.

Chunk 가 clause_code 를 들고 다닌다. 이것이 없으면 리포트에서
'규정 2.6.1 위반'이라고 쓸 수 없고 '어딘가에 이런 내용이 있다'까지만 쓴다.

ChunkSearch 의 두 메서드가 처음부터 principal 을 필수 인자로 받는다.
W1 에서는 필터가 통과만 시키지만 시그니처를 먼저 갖춘다 — 나중에 끼워
넣으면 빠뜨린 경로가 생긴다.

Embedder.encode 가 kind 를 요구한다. e5 계열은 query/passage 접두어를
요구하고, 빼면 검색 품질이 조용히 나빠진다."
```

---

### Task 3: RRF 융합

**Files:**
- Create: `backend/core/retrieve/fusion.py`
- Test: `backend/tests/test_fusion.py`

**Interfaces:**
- Consumes: 없음 (순수 함수)
- Produces:
  - `core.retrieve.fusion.rrf(rankings: Sequence[Sequence[int]], k: int = 60) -> list[int]`
  - `core.retrieve.fusion.rrf_scores(rankings, k=60) -> dict[int, float]`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_fusion.py`:

```python
from core.retrieve.fusion import rrf, rrf_scores


def test_두_검색기_모두에_등장한_문서가_1위다():
    # 서로 다른 신호가 동의하는 문서를 올리는 것이 RRF 의 존재 이유다.
    assert rrf([[1, 2, 3], [3, 4, 5]])[0] == 3


def test_한_검색기_1위보다_두_검색기_2위가_이긴다():
    # 10 은 1위 한 번, 20 은 2위 두 번.
    fused = rrf([[10, 20], [30, 20]])
    assert fused.index(20) < fused.index(10)


def test_모든_후보가_결과에_포함된다():
    assert set(rrf([[1, 2], [3]])) == {1, 2, 3}


def test_중복이_없다():
    fused = rrf([[1, 1, 2], [1, 2]])
    assert len(fused) == len(set(fused))


def test_빈_입력은_빈_결과다():
    assert rrf([]) == []
    assert rrf([[], []]) == []


def test_검색기가_하나면_순위를_그대로_유지한다():
    assert rrf([[7, 8, 9]]) == [7, 8, 9]


def test_k가_클수록_순위차의_영향이_줄어든다():
    # k 는 상위권 쏠림을 완화하는 상수다.
    작은k = rrf_scores([[1, 2]], k=1)
    큰k = rrf_scores([[1, 2]], k=1000)
    assert 작은k[1] - 작은k[2] > 큰k[1] - 큰k[2]


def test_동점이면_먼저_등장한_순서를_지킨다():
    # 결과가 실행마다 흔들리면 평가 지표를 믿을 수 없다.
    for _ in range(5):
        assert rrf([[1], [2]]) == [1, 2]
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `.venv/bin/python -m pytest tests/test_fusion.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'core.retrieve.fusion'`

- [ ] **Step 3: 구현한다**

`backend/core/retrieve/fusion.py`:

```python
"""Reciprocal Rank Fusion.

가중 합산이 아니라 RRF 를 쓰는 이유는 두 검색기의 점수 스케일이 다르기
때문이다 — 코사인은 0~1, ts_rank 는 임의 스케일이다. 정규화하려면 분포를
조사하고 계수를 튜닝해야 하는데, 3~4주 일정에서 그럴 여유가 없다.
RRF 는 순위만 쓰므로 튜닝할 파라미터가 사실상 없다.

이 모듈은 DB 를 모른다. 순위 병합이 가장 버그가 나기 쉬운 곳이라
DB 없이 테스트되어야 한다.
"""

from collections.abc import Sequence

DEFAULT_K = 60


def rrf_scores(rankings: Sequence[Sequence[int]], k: int = DEFAULT_K) -> dict[int, float]:
    """후보 id → RRF 점수. 점수 = Σ 1/(k + 순위), 순위는 0부터."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        본_것: set[int] = set()
        순위 = 0
        for 후보 in ranking:
            # 같은 검색기가 같은 후보를 두 번 냈으면 첫 번째만 센다.
            if 후보 in 본_것:
                continue
            본_것.add(후보)
            scores[후보] = scores.get(후보, 0.0) + 1.0 / (k + 순위)
            순위 += 1
    return scores


def rrf(rankings: Sequence[Sequence[int]], k: int = DEFAULT_K) -> list[int]:
    """여러 순위 리스트를 하나로 융합한다.

    동점이면 먼저 등장한 순서를 지킨다 — 결과가 실행마다 흔들리면
    평가 지표를 믿을 수 없다.
    """
    scores = rrf_scores(rankings, k=k)

    등장순: dict[int, int] = {}
    for ranking in rankings:
        for 후보 in ranking:
            등장순.setdefault(후보, len(등장순))

    return sorted(scores, key=lambda 후보: (-scores[후보], 등장순[후보]))
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `.venv/bin/python -m pytest tests/test_fusion.py tests/test_boundaries.py -v`

Expected: PASS — 8개 + 경계 테스트

- [ ] **Step 5: 커밋한다**

```bash
git add backend/core/retrieve/ backend/tests/test_fusion.py
git commit -m "RRF 융합을 순수 함수로 추가했다

DB 를 전혀 모르는 함수다. 순위 병합이 가장 버그가 나기 쉬운 곳이라
DB 없이 테스트되어야 한다.

가중 합산이 아닌 이유는 코사인과 ts_rank 의 스케일이 달라서다. 정규화하려면
분포 조사와 계수 튜닝이 필요한데 RRF 는 순위만 쓰므로 파라미터가 없다.

동점 처리를 먼저 등장한 순서로 고정했다 — 결과가 실행마다 흔들리면
평가 지표를 믿을 수 없다."
```

---

### Task 4: PDF 조항 분할과 청킹

**Files:**
- Create: `backend/adapters/parsing/pdf.py`, `backend/adapters/parsing/loader.py`
- Test: `backend/tests/test_pdf_parsing.py`

**Interfaces:**
- Consumes: `core.types.Clause`, `core.types.Chunk`
- Produces:
  - `adapters.parsing.pdf.extract_text(path: Path) -> str`
  - `adapters.parsing.pdf.split_clauses(text: str) -> list[Clause]`
  - `adapters.parsing.pdf.chunk_clauses(clauses, max_chars=900, overlap=150) -> list[Chunk]`
  - `adapters.parsing.loader.load(path: Path) -> tuple[list[Clause], list[Chunk]]`

**실측 근거:** ISMS-P 안내서에서 조항 코드가 `1.3.1 보호대책 구현` 형태로 줄 앞에 나온다. 41~70쪽에서 14건이 정규식으로 정확히 잡혔다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_pdf_parsing.py`:

```python
from core.types import Chunk, Clause
from adapters.parsing.pdf import chunk_clauses, split_clauses

# 실제 ISMS-P 안내서의 구조를 본뜬 텍스트.
# 조항 코드가 줄 앞에 오고, 본문이 뒤따르며, 조항 밖 텍스트(머리말)도 있다.
샘플 = """정보보호 및 개인정보보호 관리체계 인증기준 안내서

1.3.1 보호대책 구현
선정된 보호대책은 이행계획에 따라 효과적으로 구현하고, 이행 결과의
정확성 및 효과성 여부를 확인하여야 한다.

1.3.2 보호대책 공유
보호대책의 실제 운영 또는 시행할 부서 및 담당자를 파악하여 관련 내용을
공유하여야 한다.

2.6.1 네트워크 접근
네트워크에 대한 비인가 접근을 통제하기 위하여 네트워크 접근 통제
정책을 수립하고 이행하여야 한다.
"""


def test_조항_코드로_분할한다():
    clauses = split_clauses(샘플)
    assert [c.code for c in clauses] == ["1.3.1", "1.3.2", "2.6.1"]


def test_조항_제목을_뽑는다():
    by_code = {c.code: c for c in split_clauses(샘플)}
    assert by_code["1.3.1"].title == "보호대책 구현"
    assert by_code["2.6.1"].title == "네트워크 접근"


def test_조항_본문에_다음_조항이_섞이지_않는다():
    # 경계를 잘못 잡으면 인용이 엉뚱한 조항을 가리킨다.
    by_code = {c.code: c for c in split_clauses(샘플)}
    assert "보호대책 공유" not in by_code["1.3.1"].text
    assert "효과적으로 구현" in by_code["1.3.1"].text


def test_조항_앞_머리말은_버린다():
    # 표지·목차는 조항이 아니다.
    clauses = split_clauses(샘플)
    assert all("안내서" not in c.text or c.code.startswith("1.3") for c in clauses)


def test_조항이_없는_텍스트는_빈_리스트다():
    assert split_clauses("조항 코드가 하나도 없는 평범한 문단.") == []


def test_청크가_조항_코드를_들고_다닌다():
    chunks = chunk_clauses(split_clauses(샘플))
    assert all(isinstance(c, Chunk) for c in chunks)
    assert {c.clause_code for c in chunks} == {"1.3.1", "1.3.2", "2.6.1"}


def test_짧은_조항은_청크_하나다():
    chunks = chunk_clauses([Clause(code="9.9.9", title="짧음", text="한 문장.")])
    assert len(chunks) == 1
    assert chunks[0].ordinal == 0


def test_긴_조항은_여러_청크로_쪼개진다():
    긴본문 = "가나다라마바사아자차카타파하 " * 200   # 약 2,800자
    chunks = chunk_clauses([Clause(code="9.9.9", title="김", text=긴본문)], max_chars=900)
    assert len(chunks) > 1
    assert all(len(c.text) <= 900 for c in chunks)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_청크가_겹쳐진다():
    # 문장이 청크 경계에서 잘리면 그 문장은 어느 쪽에서도 검색되지 않는다.
    긴본문 = "".join(f"{i}번째문장. " for i in range(300))
    chunks = chunk_clauses([Clause(code="9.9.9", title="김", text=긴본문)],
                           max_chars=500, overlap=100)
    assert len(chunks) >= 2
    # 앞 청크의 끝부분이 뒤 청크의 앞부분에 나타난다
    assert chunks[0].text[-50:] in chunks[1].text
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `.venv/bin/python -m pytest tests/test_pdf_parsing.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'adapters.parsing.pdf'`

- [ ] **Step 3: 파서를 구현한다**

`backend/adapters/parsing/pdf.py`:

```python
"""PDF → 조항 → 청크.

ISMS-P 안내서는 "2.6.1 네트워크 접근" 형태로 조항 코드가 줄 앞에 온다.
조항 경계를 먼저 잡고 그 안에서 청킹하는 이유: 경계를 무시하고 고정 길이로
자르면 한 청크가 두 조항에 걸치고, 리포트에서 잘못된 조항을 인용하게 된다.

이 모듈은 문서 포맷만 안다 — DB 도 임베딩도 모른다.
"""

import re
from pathlib import Path

from pypdf import PdfReader

from core.types import Chunk, Clause

# "1.3.1 보호대책 구현" — 줄 앞의 조항 코드와 제목.
#
# 각 자리는 반드시 \d+ 다. \d 로 쓰면 2.10·2.11·2.12 가 구조적으로 매치되지
# 않는다 — 실측에서 그 16개(2.10.1~2.12.2)를 통째로 잃었다. 그 안에는
# "2.11.3 이상행위 분석 및 모니터링" 처럼 이 프로젝트의 핵심 조항이 들어 있다.
# 실측: 255쪽 전문에서 고유 조항 102개 — ISMS-P 2022 공식 인증기준 수와 일치한다.
조항_패턴 = re.compile(r"^\s*(\d+\.\d+\.\d+)\s+(\S[^\n]{0,60})$", re.MULTILINE)


def extract_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def split_clauses(text: str) -> list[Clause]:
    """조항 코드로 텍스트를 분할한다.

    조항 앞의 머리말(표지·목차)은 버린다 — 조항이 아니고, 검색되면
    "규정 어디에 있다"고 말할 수 없다.
    """
    matches = list(조항_패턴.finditer(text))
    clauses: list[Clause] = []
    for i, m in enumerate(matches):
        시작 = m.end()
        끝 = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        본문 = text[시작:끝].strip()
        clauses.append(Clause(code=m.group(1), title=m.group(2).strip(), text=본문))
    return clauses


def chunk_clauses(
    clauses: list[Clause], max_chars: int = 900, overlap: int = 150
) -> list[Chunk]:
    """조항 안에서만 청킹한다. 청크는 조항 경계를 넘지 않는다.

    겹침을 두는 이유: 문장이 청크 경계에서 잘리면 그 문장은 어느 쪽에서도
    온전히 검색되지 않는다.
    """
    chunks: list[Chunk] = []
    for c in clauses:
        본문 = c.text
        if len(본문) <= max_chars:
            chunks.append(Chunk(clause_code=c.code, ordinal=0, text=본문))
            continue

        시작 = 0
        ordinal = 0
        step = max_chars - overlap
        while 시작 < len(본문):
            조각 = 본문[시작 : 시작 + max_chars]
            chunks.append(Chunk(clause_code=c.code, ordinal=ordinal, text=조각))
            if 시작 + max_chars >= len(본문):
                break
            시작 += step
            ordinal += 1
    return chunks
```

`backend/adapters/parsing/loader.py`:

```python
"""확장자로 파서를 고른다.

DOCX·MD 는 W1 범위 밖이다. 지원하지 않는 포맷은 조용히 건너뛰지 않고
예외를 던진다 — 조용히 넘기면 적재가 끝난 뒤에야 문서가 없다는 것을 안다.
"""

from pathlib import Path

from adapters.parsing import pdf
from core.types import Chunk, Clause


def load(path: Path) -> tuple[list[Clause], list[Chunk]]:
    suffix = path.suffix.lower()
    if suffix != ".pdf":
        raise ValueError(f"아직 지원하지 않는 포맷이다: {suffix} ({path})")
    clauses = pdf.split_clauses(pdf.extract_text(path))
    return clauses, pdf.chunk_clauses(clauses)
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `.venv/bin/python -m pytest tests/test_pdf_parsing.py -v`

Expected: PASS — 9개

- [ ] **Step 5: 실제 PDF 로 확인한다**

픽스처가 통과해도 실물에서 깨질 수 있다. **실제 255쪽 문서로 돌려본다.**

```bash
cd /Users/ryujun/Documents/secu-agent
mkdir -p data/raw
curl -sL -o "data/raw/ismsp.pdf" \
  "https://www.isac.or.kr/upload/ISMS-P%20%EC%9D%B8%EC%A6%9D%EA%B8%B0%EC%A4%80%20%EC%95%88%EB%82%B4%EC%84%9C(2022.4.22).pdf"
cd backend
.venv/bin/python -c "
from pathlib import Path
from adapters.parsing.loader import load
clauses, chunks = load(Path('../data/raw/ismsp.pdf'))
print(f'조항 {len(clauses)}개 · 청크 {len(chunks)}개')
print()
for c in clauses[:5]:
    print(f'  {c.code}  {c.title[:30]}  본문 {len(c.text)}자')
print()
빈본문 = [c.code for c in clauses if len(c.text) < 20]
print(f'본문이 20자 미만인 조항: {len(빈본문)}개 {빈본문[:8]}')
"
```

Expected: **고유 조항 코드 102개** (실측값 — ISMS-P 2022 공식 인증기준 수와 같다). 부문별로 1.x 16개 · 2.x 64개 · 3.x 22개다.

**102 보다 적게 나오면 최소 본문 길이 필터를 넣지 마라 — 그건 반대 방향이다.** 수가 모자라는 것은 조항을 *덜* 잡았다는 뜻이므로, 먼저 어느 절이 통째로 빠졌는지 확인한다:

```bash
.venv/bin/python -c "
import re, collections
from adapters.parsing.loader import extract_text
전문 = extract_text('../data/raw/ismsp.pdf')
코드 = set(re.findall(r'(?<![\d.])(\d+\.\d+\.\d+)(?![\d.])', 전문))
절 = collections.Counter('.'.join(c.split('.')[:2]) for c in 코드)
print(sorted(절.items(), key=lambda kv: [int(x) for x in kv[0].split('.')]))
"
```

2.10~2.12 가 비어 있으면 패턴의 자릿수 문제다(`\d` vs `\d+`).

각 조항 코드는 목차와 본문에 각각 한 번씩, 전체 172회 등장한다. `split_clauses` 는 **고유 코드 기준**으로 세어야 하며, 목차 항목이 본문을 덮어쓰지 않아야 한다.

관측한 숫자를 기록해 둔다. 다음 태스크의 적재 검증에서 쓴다.

- [ ] **Step 6: `.gitignore` 에 원천 데이터를 넣고 커밋한다**

```bash
cd /Users/ryujun/Documents/secu-agent
grep -q "^data/raw/" .gitignore || printf '\n# 원천 데이터 (대용량, 재다운로드 가능)\ndata/raw/\n' >> .gitignore
git add backend/adapters/parsing/ backend/tests/test_pdf_parsing.py .gitignore
git commit -m "PDF 조항 분할과 청킹을 추가했다

조항 경계를 먼저 잡고 그 안에서 청킹한다. 경계를 무시하고 고정 길이로
자르면 한 청크가 두 조항에 걸치고, 리포트에서 잘못된 조항을 인용하게 된다.

조항 패턴은 실측으로 확인했다 — ISMS-P 안내서 41~70쪽에서 '1.3.1 보호대책
구현' 형태가 14건 정확히 매치됐다.

청크에 겹침을 뒀다. 문장이 경계에서 잘리면 그 문장은 어느 쪽에서도 온전히
검색되지 않는다.

지원하지 않는 포맷은 조용히 건너뛰지 않고 예외를 던진다 — 조용히 넘기면
적재가 끝난 뒤에야 문서가 없다는 것을 알게 된다."
```

---

### Task 5: DB 스키마와 저장소 어댑터

**Files:**
- Create: `docker-compose.yml` (저장소 루트)
- Create: `backend/db/schema.sql`, `backend/adapters/db/connection.py`, `backend/adapters/db/document_store.py`
- Test: `backend/tests/test_schema.py`, `backend/tests/test_db_integration.py`

**Interfaces:**
- Consumes: `core.types.EMBEDDING_DIM`·`Document`·`Clause`·`Chunk`, `core.ports.DocumentStore`
- Produces:
  - `adapters.db.connection.connect(dsn=None) -> psycopg.Connection`
  - `adapters.db.connection.apply_schema(conn) -> None`
  - `adapters.db.document_store.PgDocumentStore` — `DocumentStore` 구현

- [ ] **Step 1: `docker-compose.yml` 을 만든다**

저장소 루트에:

```yaml
# 로컬 개발용 pgvector.
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: secuagent
      POSTGRES_PASSWORD: secuagent
      POSTGRES_DB: secuagent
    ports:
      - "5433:5432"   # 5432 는 다른 로컬 Postgres 와 부딪히기 쉬워 피한다
    volumes:
      - secuagent_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U secuagent"]
      interval: 3s
      timeout: 3s
      retries: 20

volumes:
  secuagent_pgdata:
```

- [ ] **Step 2: 컨테이너를 띄우고 pgvector 를 확인한다**

```bash
cd /Users/ryujun/Documents/secu-agent
docker compose up -d
docker compose exec -T db psql -U secuagent -c \
  "CREATE EXTENSION IF NOT EXISTS vector; SELECT extversion FROM pg_extension WHERE extname='vector';"
```

Expected: `extversion` 이 한 줄 출력된다. 실패하면 `docker compose logs db` 로 확인한다.

- [ ] **Step 3: 스키마 검사 테스트를 쓴다**

DB 를 띄우지 않고 DDL 텍스트를 검사한다. 목적은 스키마와 `core/types.py` 가 어긋나는 것을 CI 에서 잡는 것이다.

`backend/tests/test_schema.py`:

```python
import re
from pathlib import Path

from core.types import EMBEDDING_DIM

SCHEMA = Path("db/schema.sql").read_text(encoding="utf-8")


def _컬럼_목록(테이블: str) -> str:
    m = re.search(
        rf"CREATE TABLE (?:IF NOT EXISTS )?{테이블}\s*\((.*?)\n\);",
        SCHEMA,
        re.DOTALL | re.IGNORECASE,
    )
    assert m, f"{테이블} 테이블 정의를 찾을 수 없다"
    return m.group(1)


def test_다섯_개_테이블이_정의돼_있다():
    for t in ("documents", "clauses", "chunks", "log_events", "principals"):
        assert _컬럼_목록(t)


def test_벡터_차원이_EMBEDDING_DIM_과_일치한다():
    # 한쪽만 바꾸면 적재는 되는데 pgvector 가 차원 불일치로 실패한다.
    선언 = re.findall(r"vector\((\d+)\)", SCHEMA)
    assert 선언, "vector(N) 선언을 찾을 수 없다"
    assert all(int(n) == EMBEDDING_DIM for n in 선언), (
        f"schema 의 차원 {선언} 이 EMBEDDING_DIM({EMBEDDING_DIM}) 과 다르다"
    )


def test_권한_컬럼이_documents_에_있다():
    # 이 두 컬럼이 사전 필터링의 WHERE 절이 된다(spec 5.1).
    본문 = _컬럼_목록("documents")
    assert "required_clearance" in 본문
    assert "allowed_departments" in 본문


def test_HNSW_와_GIN_인덱스가_있다():
    assert "using hnsw" in SCHEMA.lower()
    assert "using gin" in SCHEMA.lower()


def test_권한_필터_컬럼에_인덱스가_있다():
    # 사전 필터링은 WHERE 가 먼저 적용되므로 이 인덱스가 없으면 느려지고,
    # 느려지는 정도가 권한에 따라 달라지면 타이밍 누출이 된다(spec 5.2).
    assert re.search(r"CREATE INDEX.*documents.*required_clearance", SCHEMA, re.IGNORECASE)


def test_같은_문서를_두_번_넣지_못하게_막는_제약이_있다():
    본문 = _컬럼_목록("documents")
    assert "UNIQUE (source_path)" in 본문 or "UNIQUE(source_path)" in 본문
```

- [ ] **Step 4: 테스트가 실패하는지 확인한다**

Run: `.venv/bin/python -m pytest tests/test_schema.py -v`

Expected: FAIL — `FileNotFoundError: db/schema.sql`

- [ ] **Step 5: `backend/db/schema.sql` 을 쓴다**

```sql
-- Secu-Agent 스키마
--
-- 벡터 차원 384 는 임베딩 모델 선택에 종속된다(intfloat/multilingual-e5-small).
-- 모델을 바꾸면 core/types.py 의 EMBEDDING_DIM, 이 스키마, 그리고 이미 적재된
-- 벡터를 전부 함께 바꿔야 한다.
--
-- documents.required_clearance 와 allowed_departments 가 사전 필터링의
-- WHERE 절이 된다. 이 두 컬럼에 인덱스를 두는 이유는 성능만이 아니다 —
-- 필터가 느리면 그 지연이 권한에 따라 달라져 타이밍 누출이 된다.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id                  BIGSERIAL PRIMARY KEY,
    title               TEXT NOT NULL,
    source_path         TEXT NOT NULL,
    doc_type            TEXT NOT NULL CHECK (doc_type IN ('pdf', 'docx', 'md')),
    required_clearance  INT  NOT NULL DEFAULT 1,
    allowed_departments TEXT[],                     -- NULL = 전사 공개
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_path)
);

CREATE INDEX IF NOT EXISTS documents_required_clearance_idx
    ON documents (required_clearance);
CREATE INDEX IF NOT EXISTS documents_allowed_departments_idx
    ON documents USING gin (allowed_departments);

CREATE TABLE IF NOT EXISTS clauses (
    id          BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    code        TEXT   NOT NULL,                    -- "2.6.1"
    title       TEXT   NOT NULL,
    text        TEXT   NOT NULL,
    UNIQUE (document_id, code)
);

CREATE INDEX IF NOT EXISTS clauses_code_idx ON clauses (code);

CREATE TABLE IF NOT EXISTS chunks (
    id          BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    clause_id   BIGINT REFERENCES clauses(id) ON DELETE CASCADE,   -- 조항 밖 텍스트는 NULL
    ordinal     INT    NOT NULL,
    text        TEXT   NOT NULL,
    embedding   vector(384) NOT NULL,
    text_tsv    TSVECTOR    NOT NULL
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (text_tsv);
CREATE INDEX IF NOT EXISTS chunks_document_idx ON chunks (document_id);

-- W4 에서 채운다. 스키마를 지금 두는 이유는 나중에 마이그레이션하지 않기 위해서다.
CREATE TABLE IF NOT EXISTS log_events (
    id             BIGSERIAL PRIMARY KEY,
    ts             TIMESTAMPTZ,
    host           TEXT NOT NULL,
    process        TEXT,
    event_type     TEXT NOT NULL,                   -- auth_failure | session_open | ...
    principal_name TEXT,
    raw            TEXT NOT NULL,                   -- 원본 보존
    severity       TEXT
);

CREATE INDEX IF NOT EXISTS log_events_ts_idx ON log_events (ts);
CREATE INDEX IF NOT EXISTS log_events_type_idx ON log_events (event_type);

CREATE TABLE IF NOT EXISTS principals (
    id         BIGSERIAL PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    department TEXT NOT NULL,
    clearance  INT  NOT NULL
);
```

- [ ] **Step 6: 스키마 테스트가 통과하는지 확인하고, 회귀를 검증한다**

Run: `.venv/bin/python -m pytest tests/test_schema.py -v`

Expected: PASS — 6개

**차원 불일치를 실제로 잡는지 확인한다:**

```bash
sed -i '' 's/vector(384)/vector(768)/' db/schema.sql
.venv/bin/python -m pytest tests/test_schema.py -q
```

Expected: FAIL — `schema 의 차원 ['768', '768'] 이 EMBEDDING_DIM(384) 과 다르다`

```bash
git checkout db/schema.sql 2>/dev/null || sed -i '' 's/vector(768)/vector(384)/' db/schema.sql
.venv/bin/python -m pytest tests/test_schema.py -q
```

Expected: PASS

- [ ] **Step 7: DB 통합 테스트를 쓴다**

`backend/tests/test_db_integration.py`:

```python
"""실제 데이터베이스가 필요한 테스트.

기본 스위트에서 제외된다(pyproject 의 addopts). 돌리려면:
    docker compose up -d
    .venv/bin/python -m pytest -m db -v
"""

import os

import pytest

from adapters.db.connection import apply_schema, connect
from adapters.db.document_store import PgDocumentStore
from core.ports import DocumentStore
from core.types import EMBEDDING_DIM, Chunk, Clause, Document

pytestmark = pytest.mark.db

DSN = os.environ.get("SECUAGENT_DSN", "postgresql://secuagent:secuagent@localhost:5433/secuagent")


@pytest.fixture
def store():
    conn = connect(DSN)
    apply_schema(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE documents RESTART IDENTITY CASCADE")
    conn.commit()
    yield PgDocumentStore(conn)
    conn.close()


def _문서(path="data/raw/a.pdf", clearance=1, depts=()) -> Document:
    return Document(
        id=0,
        title="테스트 문서",
        source_path=path,
        doc_type="pdf",
        required_clearance=clearance,
        allowed_departments=depts,
    )


def _벡터(seed: float = 0.1) -> list[float]:
    return [seed] * EMBEDDING_DIM


def test_구현이_포트를_만족한다(store):
    assert isinstance(store, DocumentStore)


def test_문서를_저장하고_id_를_돌려준다(store):
    doc_id = store.upsert_document(_문서())
    assert doc_id > 0


def test_같은_경로를_두_번_넣어도_행이_늘지_않는다(store):
    first = store.upsert_document(_문서())
    second = store.upsert_document(_문서())
    assert first == second
    with store.conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM documents")
        assert cur.fetchone()[0] == 1


def test_권한_컬럼이_저장된다(store):
    doc_id = store.upsert_document(_문서(clearance=3, depts=("인사팀",)))
    with store.conn.cursor() as cur:
        cur.execute(
            "SELECT required_clearance, allowed_departments FROM documents WHERE id = %s",
            (doc_id,),
        )
        assert cur.fetchone() == (3, ["인사팀"])


def test_허용부서가_비면_NULL_로_저장된다(store):
    # NULL = 전사 공개. 빈 배열과 구분해야 SQL 필터가 단순해진다.
    doc_id = store.upsert_document(_문서(depts=()))
    with store.conn.cursor() as cur:
        cur.execute("SELECT allowed_departments FROM documents WHERE id = %s", (doc_id,))
        assert cur.fetchone()[0] is None


def test_조항을_저장하고_코드_매핑을_돌려준다(store):
    doc_id = store.upsert_document(_문서())
    ids = store.insert_clauses(doc_id, [
        Clause(code="1.1.1", title="가", text="본문 가"),
        Clause(code="2.6.1", title="나", text="본문 나"),
    ])
    assert set(ids) == {"1.1.1", "2.6.1"}


def test_청크와_벡터를_저장한다(store):
    doc_id = store.upsert_document(_문서())
    ids = store.insert_clauses(doc_id, [Clause(code="1.1.1", title="가", text="본문")])
    n = store.insert_chunks(
        doc_id, ids,
        [Chunk(clause_code="1.1.1", ordinal=0, text="청크 본문")],
        [_벡터()],
    )
    assert n == 1
    assert store.count_chunks() == 1


def test_조항_밖_청크도_저장된다(store):
    # 표지·목차는 조항이 없다. clause_id 가 NULL 이어야 한다.
    doc_id = store.upsert_document(_문서())
    store.insert_chunks(doc_id, {}, [Chunk(clause_code=None, ordinal=0, text="목차")], [_벡터()])
    with store.conn.cursor() as cur:
        cur.execute("SELECT clause_id FROM chunks")
        assert cur.fetchone()[0] is None


def test_전문검색_벡터가_채워진다(store):
    # text_tsv 가 비면 키워드 검색이 조용히 0건을 낸다.
    doc_id = store.upsert_document(_문서())
    store.insert_chunks(doc_id, {}, [Chunk(clause_code=None, ordinal=0, text="네트워크 접근 통제")], [_벡터()])
    with store.conn.cursor() as cur:
        cur.execute("SELECT text_tsv IS NOT NULL FROM chunks")
        assert cur.fetchone()[0] is True


def test_문서를_지우면_조항과_청크도_지워진다(store):
    doc_id = store.upsert_document(_문서())
    ids = store.insert_clauses(doc_id, [Clause(code="1.1.1", title="가", text="본문")])
    store.insert_chunks(doc_id, ids, [Chunk(clause_code="1.1.1", ordinal=0, text="청크")], [_벡터()])
    with store.conn.cursor() as cur:
        cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
    store.conn.commit()
    assert store.count_chunks() == 0
```

- [ ] **Step 8: 연결 모듈과 저장소를 구현한다**

`backend/adapters/db/connection.py`:

```python
"""psycopg 연결과 스키마 적용.

DSN 은 환경변수 SECUAGENT_DSN 으로 준다. 기본값은 docker-compose 의 로컬
컨테이너다 — 5432 대신 5433 을 쓰는 이유는 다른 로컬 Postgres 와 부딪히지
않기 위해서다.
"""

import os
from pathlib import Path

import psycopg

DEFAULT_DSN = "postgresql://secuagent:secuagent@localhost:5433/secuagent"
SCHEMA = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


def connect(dsn: str | None = None) -> psycopg.Connection:
    return psycopg.connect(dsn or os.environ.get("SECUAGENT_DSN", DEFAULT_DSN))


def apply_schema(conn: psycopg.Connection) -> None:
    """db/schema.sql 을 적용한다. 전부 IF NOT EXISTS 라 여러 번 돌려도 안전하다."""
    with conn.cursor() as cur:
        cur.execute(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()
```

`backend/adapters/db/document_store.py`:

```python
"""DocumentStore 의 psycopg 구현.

core/ports 의 Protocol 을 만족한다. 도메인은 이 파일을 모른다 — 의존성은
adapters → core 한 방향이다.
"""

from collections.abc import Sequence

import psycopg

from core.types import Chunk, Clause, Document

Vector = list[float]


class PgDocumentStore:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def upsert_document(self, doc: Document) -> int:
        """UNIQUE(source_path) 충돌 시 갱신한다.

        DO NOTHING 이 아니라 DO UPDATE 인 이유: 권한 등급을 바꾼 뒤 재적재로
        반영할 수 있어야 한다. RETURNING 은 삽입이든 갱신이든 id 를 돌려준다.

        allowed_departments 는 비어 있으면 NULL 로 넣는다 — 빈 배열과 NULL 을
        섞으면 SQL 필터에 조건이 하나 더 붙는다.
        """
        depts = list(doc.allowed_departments) or None
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents
                    (title, source_path, doc_type, required_clearance, allowed_departments)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (source_path) DO UPDATE SET
                    title = EXCLUDED.title,
                    doc_type = EXCLUDED.doc_type,
                    required_clearance = EXCLUDED.required_clearance,
                    allowed_departments = EXCLUDED.allowed_departments
                RETURNING id
                """,
                (doc.title, doc.source_path, doc.doc_type, doc.required_clearance, depts),
            )
            doc_id = cur.fetchone()[0]
        self.conn.commit()
        return doc_id

    def insert_clauses(self, document_id: int, clauses: Sequence[Clause]) -> dict[str, int]:
        out: dict[str, int] = {}
        with self.conn.cursor() as cur:
            for c in clauses:
                cur.execute(
                    """
                    INSERT INTO clauses (document_id, code, title, text)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (document_id, code) DO UPDATE SET
                        title = EXCLUDED.title, text = EXCLUDED.text
                    RETURNING id, code
                    """,
                    (document_id, c.code, c.title, c.text),
                )
                cid, code = cur.fetchone()
                out[code] = cid
        self.conn.commit()
        return out

    def insert_chunks(
        self,
        document_id: int,
        clause_ids: dict[str, int],
        chunks: Sequence[Chunk],
        vectors: Sequence[Vector],
    ) -> int:
        """청크를 저장한다.

        text_tsv 를 to_tsvector 로 여기서 채운다. 비워두면 키워드 검색이
        조용히 0건을 낸다 — 에러가 아니라 빈 결과라 발견이 늦다.
        """
        if len(chunks) != len(vectors):
            raise ValueError(f"청크 {len(chunks)}개와 벡터 {len(vectors)}개의 수가 다르다")
        if not chunks:
            return 0

        with self.conn.cursor() as cur:
            for ch, vec in zip(chunks, vectors, strict=True):
                cur.execute(
                    """
                    INSERT INTO chunks (document_id, clause_id, ordinal, text, embedding, text_tsv)
                    VALUES (%s, %s, %s, %s, %s, to_tsvector('simple', %s))
                    """,
                    (
                        document_id,
                        clause_ids.get(ch.clause_code) if ch.clause_code else None,
                        ch.ordinal,
                        ch.text,
                        str(vec),
                        ch.text,
                    ),
                )
        self.conn.commit()
        return len(chunks)

    def count_chunks(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM chunks")
            return cur.fetchone()[0]
```

- [ ] **Step 9: 테스트가 통과하는지 확인한다**

Run: `.venv/bin/python -m pytest -m db -v`

Expected: PASS — 10개

기본 스위트가 DB 없이 도는지도 확인한다:

Run: `.venv/bin/python -m pytest -q`

Expected: PASS — DB 테스트는 마커로 제외된다

- [ ] **Step 10: 커밋한다**

```bash
cd /Users/ryujun/Documents/secu-agent
git add docker-compose.yml backend/db/ backend/adapters/db/ \
        backend/tests/test_schema.py backend/tests/test_db_integration.py
git commit -m "pgvector 컨테이너와 저장소 어댑터를 추가했다

documents 의 required_clearance 와 allowed_departments 가 사전 필터링의
WHERE 절이 된다. 두 컬럼에 인덱스를 둔 이유는 성능만이 아니다 — 필터가
느리면 그 지연이 권한에 따라 달라져 타이밍 누출이 된다.

allowed_departments 는 비어 있으면 NULL 로 넣는다. 빈 배열과 NULL 을 섞으면
SQL 필터에 조건이 하나 더 붙는다.

text_tsv 를 저장 시점에 채운다. 비워두면 키워드 검색이 에러가 아니라
조용히 0건을 내서 발견이 늦다.

스키마 테스트가 벡터 차원과 EMBEDDING_DIM 의 불일치를 잡는지 확인했다 —
384 를 768 로 바꿔 실패를 보고 원복했다.

DB 테스트를 db 마커로 분리해 기본 스위트에서 제외했다. 컨테이너가 없는
환경에서 스위트 전체가 실패하면 안 된다."
```

---

### Task 6: 임베딩 어댑터와 적재 파이프라인

**Files:**
- Create: `backend/adapters/embedding/e5.py`, `backend/pipeline/ingest.py`, `backend/pipeline/cli.py`
- Test: `backend/tests/test_ingest.py`

**Interfaces:**
- Consumes: `core.ports.Embedder`·`DocumentStore`, `adapters.parsing.loader.load`
- Produces:
  - `adapters.embedding.e5.E5Embedder` — `Embedder` 구현
  - `pipeline.ingest.IngestReport` — frozen dataclass(`clauses: int`, `chunks: int`)
  - `pipeline.ingest.ingest(path, doc, loader, embedder, store) -> IngestReport`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_ingest.py`:

```python
from pathlib import Path

from core.types import EMBEDDING_DIM, Chunk, Clause, Document
from pipeline.ingest import IngestReport, ingest


class 스텁임베더:
    """호출 인자를 기록한다 — passage 접두어를 쓰는지 확인하기 위해서다."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    def encode(self, texts, kind):
        self.calls.append((len(texts), kind))
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class 메모리저장소:
    def __init__(self) -> None:
        self.docs: list[Document] = []
        self.clauses: list[Clause] = []
        self.chunks: list[Chunk] = []
        self.vectors: list[list[float]] = []

    def upsert_document(self, doc):
        self.docs.append(doc)
        return len(self.docs)

    def insert_clauses(self, document_id, clauses):
        self.clauses.extend(clauses)
        return {c.code: i for i, c in enumerate(clauses, start=1)}

    def insert_chunks(self, document_id, clause_ids, chunks, vectors):
        self.chunks.extend(chunks)
        self.vectors.extend(vectors)
        return len(chunks)

    def count_chunks(self):
        return len(self.chunks)


def _로더(path: Path):
    return (
        [Clause(code="1.1.1", title="가", text="본문 가"),
         Clause(code="2.6.1", title="나", text="본문 나")],
        [Chunk(clause_code="1.1.1", ordinal=0, text="청크 1"),
         Chunk(clause_code="2.6.1", ordinal=0, text="청크 2")],
    )


def _문서() -> Document:
    return Document(
        id=0, title="테스트", source_path="a.pdf", doc_type="pdf",
        required_clearance=1, allowed_departments=(),
    )


def test_조항과_청크를_적재한다():
    e, s = 스텁임베더(), 메모리저장소()
    report = ingest(Path("a.pdf"), _문서(), _로더, e, s)
    assert isinstance(report, IngestReport)
    assert report.clauses == 2
    assert report.chunks == 2


def test_임베딩은_passage_접두어로_한다():
    # e5 계열은 문서를 passage:, 질의를 query: 로 넣어야 한다.
    # 여기서 query 를 쓰면 검색 품질이 조용히 나빠진다.
    e, s = 스텁임베더(), 메모리저장소()
    ingest(Path("a.pdf"), _문서(), _로더, e, s)
    assert all(kind == "passage" for _, kind in e.calls)


def test_청크와_벡터의_수가_같다():
    e, s = 스텁임베더(), 메모리저장소()
    ingest(Path("a.pdf"), _문서(), _로더, e, s)
    assert len(s.chunks) == len(s.vectors)


def test_청크가_없으면_임베더를_부르지_않는다():
    # 빈 리스트로 API 를 호출하면 비용만 든다.
    def 빈로더(path):
        return [], []

    e, s = 스텁임베더(), 메모리저장소()
    report = ingest(Path("a.pdf"), _문서(), 빈로더, e, s)
    assert report.chunks == 0
    assert e.calls == []


def test_대량_청크는_배치로_임베딩한다():
    # 3천 개를 한 번에 넘기면 메모리가 터진다.
    def 큰로더(path):
        return [], [Chunk(clause_code=None, ordinal=i, text=f"청크 {i}") for i in range(250)]

    e, s = 스텁임베더(), 메모리저장소()
    ingest(Path("a.pdf"), _문서(), 큰로더, e, s, batch_size=64)
    assert len(e.calls) == 4          # 64 · 64 · 64 · 58
    assert all(n <= 64 for n, _ in e.calls)
    assert sum(n for n, _ in e.calls) == 250
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `.venv/bin/python -m pytest tests/test_ingest.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.ingest'`

- [ ] **Step 3: 임베딩 어댑터를 만든다**

`backend/adapters/embedding/e5.py`:

```python
"""multilingual-e5-small 임베딩 어댑터.

이 모델을 고른 이유는 크기가 아니라 cross-lingual 이다 — 한국어 질의로
한국어 규정과 영문 로그를 같은 벡터 공간에서 검색한다(spec 2.5).

e5 계열은 "query: " / "passage: " 접두어를 요구한다. 접두어를 빼면 성능이
눈에 띄게 떨어지는데, 에러가 아니라 조용한 품질 저하라 발견이 늦다.
그래서 포트가 kind 를 필수 인자로 요구한다.
"""

from collections.abc import Sequence
from typing import Literal

from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-small"


class E5Embedder:
    def __init__(self, model_name: str = MODEL_NAME, device: str | None = None) -> None:
        self._model = SentenceTransformer(model_name, device=device)

    def encode(self, texts: Sequence[str], kind: Literal["query", "passage"]) -> list[list[float]]:
        if kind not in ("query", "passage"):
            raise ValueError(f"kind 는 query 또는 passage 여야 한다: {kind!r}")
        prefixed = [f"{kind}: {t}" for t in texts]
        vecs = self._model.encode(prefixed, normalize_embeddings=True)
        return [v.tolist() for v in vecs]
```

- [ ] **Step 4: 적재 오케스트레이터를 만든다**

`backend/pipeline/ingest.py`:

```python
"""문서 적재 오케스트레이션.

이 모듈은 core/ports 의 포트만 안다. psycopg 도 sentence-transformers 도
pypdf 도 모른다 — 그래서 테스트가 DB 없이, 모델 로드 없이 스텁으로 돈다.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from core.ports import DocumentStore, Embedder
from core.types import Chunk, Clause, Document

Loader = Callable[[Path], tuple[list[Clause], list[Chunk]]]

DEFAULT_BATCH = 64


@dataclass(frozen=True)
class IngestReport:
    clauses: int
    chunks: int


def _배치(items: Sequence[Chunk], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def ingest(
    path: Path,
    doc: Document,
    loader: Loader,
    embedder: Embedder,
    store: DocumentStore,
    batch_size: int = DEFAULT_BATCH,
) -> IngestReport:
    """문서를 파싱해 조항·청크·벡터를 저장한다.

    임베딩을 배치로 나누는 이유: 255쪽 문서는 청크가 수천 개가 되고,
    한 번에 넘기면 메모리가 터진다.
    """
    clauses, chunks = loader(path)

    document_id = store.upsert_document(doc)
    clause_ids = store.insert_clauses(document_id, clauses) if clauses else {}

    if not chunks:
        return IngestReport(clauses=len(clauses), chunks=0)

    저장수 = 0
    for batch in _배치(chunks, batch_size):
        # 문서 쪽은 passage 다. query 를 쓰면 검색 품질이 조용히 나빠진다.
        vectors = embedder.encode([c.text for c in batch], kind="passage")
        저장수 += store.insert_chunks(document_id, clause_ids, batch, vectors)

    return IngestReport(clauses=len(clauses), chunks=저장수)
```

- [ ] **Step 5: 테스트가 통과하는지 확인한다**

Run: `.venv/bin/python -m pytest tests/test_ingest.py tests/test_boundaries.py -v`

Expected: PASS — 5개 + 경계 테스트

- [ ] **Step 6: CLI 를 만든다**

`backend/pipeline/cli.py`:

```python
"""파이프라인 CLI.

    python -m pipeline.cli ingest ../data/raw/ismsp.pdf \
        --title "ISMS-P 인증기준 안내서" --clearance 1

권한 등급과 허용 부서를 인자로 받는다. 공개 표준 문서에는 등급 정보가
없으므로 적재하는 사람이 부여한다 — 이 사실은 spec 4.1 에 적혀 있다.
"""

import argparse
import sys
from pathlib import Path

from adapters.db.connection import apply_schema, connect
from adapters.db.document_store import PgDocumentStore
from adapters.embedding.e5 import E5Embedder
from adapters.parsing.loader import load
from core.types import Document
from pipeline.ingest import ingest


def main() -> int:
    ap = argparse.ArgumentParser(description="Secu-Agent 데이터 파이프라인")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ing = sub.add_parser("ingest", help="문서를 적재한다")
    ing.add_argument("path", type=Path)
    ing.add_argument("--title", required=True)
    ing.add_argument("--clearance", type=int, default=1, help="1(사원) 2(팀장) 3(임원)")
    ing.add_argument("--departments", nargs="*", default=[], help="비우면 전사 공개")
    ing.add_argument("--dsn", default=None)

    args = ap.parse_args()

    if args.cmd == "ingest":
        if not args.path.exists():
            print(f"파일이 없다: {args.path}", file=sys.stderr)
            return 1

        conn = connect(args.dsn)
        apply_schema(conn)
        store = PgDocumentStore(conn)

        doc = Document(
            id=0,
            title=args.title,
            source_path=str(args.path),
            doc_type=args.path.suffix.lstrip(".").lower(),
            required_clearance=args.clearance,
            allowed_departments=tuple(args.departments),
        )

        print(f"{args.path} 적재 중… (모델 로드에 시간이 걸린다)")
        report = ingest(args.path, doc, load, E5Embedder(), store)
        print(f"  조항 {report.clauses}개 · 청크 {report.chunks}개")
        print(f"  DB 총 청크: {store.count_chunks()}")
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: 실데이터를 적재한다**

```bash
cd /Users/ryujun/Documents/secu-agent
docker compose up -d
cd backend
.venv/bin/python -m pipeline.cli ingest ../data/raw/ismsp.pdf \
  --title "ISMS-P 인증기준 안내서" --clearance 1
```

Expected: 고유 조항 102개, 청크 수백~수천 개. **출력된 숫자를 기록한다** — Task 4 Step 5 에서 본 조항 수(102)와 일치해야 한다.

멱등성을 확인한다:

```bash
.venv/bin/python -m pipeline.cli ingest ../data/raw/ismsp.pdf \
  --title "ISMS-P 인증기준 안내서" --clearance 1
docker compose exec -T db psql -U secuagent -c "SELECT count(*) FROM documents;"
```

Expected: `documents` 는 1행. **청크는 늘어난다** — `chunks` 에 중복 방지 제약이 없기 때문이다. 이것은 알려진 한계이며 아래 단계에서 기록한다.

- [ ] **Step 8: 청크 중복을 확인하고 기록한다**

```bash
docker compose exec -T db psql -U secuagent -c "SELECT count(*) FROM chunks;"
```

청크가 두 배가 되었다면 **다음 계획으로 넘길 항목**에 적는다. 재적재하려면 `TRUNCATE chunks` 를 먼저 한다.

- [ ] **Step 9: 커밋한다**

```bash
cd /Users/ryujun/Documents/secu-agent
git add backend/adapters/embedding/ backend/pipeline/ backend/tests/test_ingest.py
git commit -m "임베딩 어댑터와 적재 파이프라인을 추가했다

pipeline/ingest.py 는 포트만 안다. psycopg 도 sentence-transformers 도
pypdf 도 모르므로 테스트가 DB 없이, 모델 로드 없이 스텁으로 돈다.

임베딩을 배치로 나눈다. 255쪽 문서는 청크가 수천 개가 되고 한 번에
넘기면 메모리가 터진다.

문서는 passage 접두어로 임베딩한다. e5 계열에서 접두어를 빼면 에러가
아니라 조용한 품질 저하가 나서 발견이 늦다 — 스텁이 kind 를 기록하고
테스트가 passage 인지 확인한다.

권한 등급은 적재 시 인자로 받는다. 공개 표준 문서에는 등급 정보가 없어
적재하는 사람이 부여한다.

문서는 멱등이다. 청크는 아직 아니다 — chunks 에 중복 방지 제약이 없고,
재적재 전에 TRUNCATE chunks 가 필요하다."
```

---

### Task 7: 하이브리드 검색

**Files:**
- Create: `backend/adapters/db/chunk_search.py`, `backend/core/retrieve/hybrid.py`
- Modify: `backend/pipeline/cli.py` (search 서브커맨드)
- Test: `backend/tests/test_hybrid.py`, `backend/tests/test_search_integration.py`

**Interfaces:**
- Consumes: `core.ports.ChunkSearch`·`Embedder`, `core.retrieve.fusion.rrf`, `core.types.Principal`·`PolicyHit`
- Produces:
  - `adapters.db.chunk_search.PgChunkSearch` — `ChunkSearch` 구현
  - `core.retrieve.hybrid.search(query, principal, embedder, searcher, k) -> list[int]`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_hybrid.py`:

```python
from core.retrieve.hybrid import search
from core.types import EMBEDDING_DIM, Principal


class 스텁임베더:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def encode(self, texts, kind):
        self.calls.append(kind)
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class 스텁검색기:
    def __init__(self, vec_hits, kw_hits):
        self.vec_hits, self.kw_hits = vec_hits, kw_hits
        self.받은_주체: list[Principal] = []

    def by_vector(self, vec, principal, k):
        self.받은_주체.append(principal)
        return self.vec_hits[:k]

    def by_keyword(self, query, principal, k):
        self.받은_주체.append(principal)
        return self.kw_hits[:k]


사원 = Principal(department="개발팀", clearance=1)


def test_두_검색_결과를_융합한다():
    s = 스텁검색기(vec_hits=[1, 2, 3], kw_hits=[3, 4, 5])
    # 3 이 양쪽에 있으므로 1위여야 한다
    assert search("질의", 사원, 스텁임베더(), s, k=5)[0] == 3


def test_질의는_query_접두어로_임베딩한다():
    # 문서는 passage, 질의는 query 다. 섞으면 검색 품질이 조용히 나빠진다.
    e = 스텁임베더()
    search("질의", 사원, e, 스텁검색기([1], [2]), k=5)
    assert e.calls == ["query"]


def test_주체를_두_검색기_모두에_넘긴다():
    # 한쪽만 권한 필터를 적용하면 그쪽으로 누출된다(spec 6.1).
    s = 스텁검색기([1], [2])
    search("질의", 사원, 스텁임베더(), s, k=5)
    assert s.받은_주체 == [사원, 사원]


def test_k_개까지만_돌려준다():
    s = 스텁검색기(vec_hits=[1, 2, 3, 4, 5, 6], kw_hits=[7, 8, 9])
    assert len(search("질의", 사원, 스텁임베더(), s, k=3)) == 3


def test_결과가_없으면_빈_리스트다():
    assert search("질의", 사원, 스텁임베더(), 스텁검색기([], []), k=5) == []
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `.venv/bin/python -m pytest tests/test_hybrid.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'core.retrieve.hybrid'`

- [ ] **Step 3: 하이브리드 검색을 구현한다**

`backend/core/retrieve/hybrid.py`:

```python
"""하이브리드 검색 — 벡터와 키워드를 RRF 로 융합한다.

포트만 안다. DB 도 임베딩 모델도 모른다.

두 검색기 모두에 principal 을 넘긴다. 한쪽만 권한 필터를 적용하면
그쪽으로 누출된다(spec 6.1).
"""

from core.ports import ChunkSearch, Embedder
from core.retrieve.fusion import rrf
from core.types import Principal

# 융합 전에 각 검색기에서 가져올 후보 수.
# k 보다 넉넉히 가져와야 융합이 의미를 갖는다 — k 개씩만 가져오면
# 두 리스트가 거의 겹치지 않을 때 융합할 것이 없다.
CANDIDATE_MULTIPLIER = 5


def search(
    query: str,
    principal: Principal,
    embedder: Embedder,
    searcher: ChunkSearch,
    k: int = 10,
) -> list[int]:
    """질의로 chunk id 를 최대 k 개, 관련도 순으로 돌려준다."""
    candidates = k * CANDIDATE_MULTIPLIER

    # 질의는 query 접두어다. 문서(passage)와 섞으면 품질이 조용히 나빠진다.
    qvec = embedder.encode([query], kind="query")[0]

    벡터 = searcher.by_vector(qvec, principal, candidates)
    키워드 = searcher.by_keyword(query, principal, candidates)

    return rrf([벡터, 키워드])[:k]
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `.venv/bin/python -m pytest tests/test_hybrid.py tests/test_boundaries.py -v`

Expected: PASS — 5개 + 경계 테스트

- [ ] **Step 5: DB 검색 어댑터를 구현한다**

`backend/adapters/db/chunk_search.py`:

```python
"""ChunkSearch 의 psycopg 구현.

WHERE 절이 ORDER BY 보다 먼저 적용된다 — 권한 없는 문서는 후보에
들어오지도 않고 LIMIT k 가 항상 채워진다(spec 5.1).

W1 에서는 필터가 사실상 모든 문서를 통과시킨다(전부 clearance 1, 부서 NULL).
그래도 SQL 을 지금 갖춰두는 이유: W2 에서 권한 데이터를 넣는 순간
필터가 저절로 동작해야 한다. 나중에 WHERE 를 끼워 넣으면 빠뜨린 경로가 생긴다.
"""

from collections.abc import Sequence

import psycopg

from core.types import PolicyHit, Principal

Vector = list[float]

# 권한 필터. 두 검색 메서드가 같은 조건을 쓴다 — 한쪽만 적용하면 그쪽으로 누출된다.
_권한_WHERE = """
    d.required_clearance <= %(clearance)s
    AND (d.allowed_departments IS NULL OR %(dept)s = ANY(d.allowed_departments))
"""


class PgChunkSearch:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def by_vector(self, vec: Vector, principal: Principal, k: int) -> list[int]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT c.id
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE {_권한_WHERE}
                ORDER BY c.embedding <=> %(qvec)s
                LIMIT %(k)s
                """,
                {
                    "clearance": principal.clearance,
                    "dept": principal.department,
                    "qvec": str(vec),
                    "k": k,
                },
            )
            return [row[0] for row in cur.fetchall()]

    def by_keyword(self, query: str, principal: Principal, k: int) -> list[int]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT c.id
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE {_권한_WHERE}
                  AND c.text_tsv @@ plainto_tsquery('simple', %(q)s)
                ORDER BY ts_rank(c.text_tsv, plainto_tsquery('simple', %(q)s)) DESC
                LIMIT %(k)s
                """,
                {
                    "clearance": principal.clearance,
                    "dept": principal.department,
                    "q": query,
                    "k": k,
                },
            )
            return [row[0] for row in cur.fetchall()]

    def load_hits(self, ids: Sequence[int]) -> list[PolicyHit]:
        """chunk id → PolicyHit. 결과 표시에 쓴다.

        순서는 호출자가 준 id 순서를 따른다 — SQL 의 반환 순서에 기대면
        융합 결과의 순위가 뒤집힌다.
        """
        if not ids:
            return []
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.text, d.title, cl.code
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                LEFT JOIN clauses cl ON cl.id = c.clause_id
                WHERE c.id = ANY(%s)
                """,
                (list(ids),),
            )
            by_id = {
                row[0]: PolicyHit(chunk_id=row[0], text=row[1], doc_title=row[2], clause_code=row[3])
                for row in cur.fetchall()
            }
        return [by_id[i] for i in ids if i in by_id]
```

- [ ] **Step 6: 통합 테스트를 쓴다**

`backend/tests/test_search_integration.py`:

```python
"""실제 DB 로 하이브리드 검색을 확인한다.

    docker compose up -d
    .venv/bin/python -m pytest -m db -v
"""

import os

import pytest

from adapters.db.chunk_search import PgChunkSearch
from adapters.db.connection import apply_schema, connect
from adapters.db.document_store import PgDocumentStore
from core.ports import ChunkSearch
from core.retrieve.hybrid import search
from core.types import EMBEDDING_DIM, Chunk, Clause, Document, PolicyHit, Principal

pytestmark = pytest.mark.db

DSN = os.environ.get("SECUAGENT_DSN", "postgresql://secuagent:secuagent@localhost:5433/secuagent")
사원 = Principal(department="개발팀", clearance=1)


class 고정임베더:
    """항상 같은 벡터를 준다 — 벡터 검색이 도는지만 본다."""

    def encode(self, texts, kind):
        return [[0.1] * EMBEDDING_DIM for _ in texts]


@pytest.fixture
def db():
    conn = connect(DSN)
    apply_schema(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE documents RESTART IDENTITY CASCADE")
    conn.commit()

    store = PgDocumentStore(conn)
    doc_id = store.upsert_document(Document(
        id=0, title="ISMS-P", source_path="a.pdf", doc_type="pdf",
        required_clearance=1, allowed_departments=(),
    ))
    ids = store.insert_clauses(doc_id, [
        Clause(code="2.6.1", title="네트워크 접근", text="네트워크 접근 통제"),
        Clause(code="2.5.1", title="사용자 계정 관리", text="계정 발급과 관리"),
    ])
    store.insert_chunks(
        doc_id, ids,
        [Chunk(clause_code="2.6.1", ordinal=0, text="네트워크에 대한 비인가 접근을 통제한다"),
         Chunk(clause_code="2.5.1", ordinal=0, text="사용자 계정 발급 절차를 수립한다")],
        [[0.1] * EMBEDDING_DIM, [0.9] * EMBEDDING_DIM],
    )
    yield conn, PgChunkSearch(conn)
    conn.close()


def test_구현이_포트를_만족한다(db):
    _, searcher = db
    assert isinstance(searcher, ChunkSearch)


def test_벡터_검색이_결과를_돌려준다(db):
    _, searcher = db
    assert len(searcher.by_vector([0.1] * EMBEDDING_DIM, 사원, k=10)) == 2


def test_키워드_검색이_본문에_있는_말을_찾는다(db):
    _, searcher = db
    hits = searcher.by_keyword("네트워크", 사원, k=10)
    assert len(hits) == 1


def test_본문에_없는_말은_키워드_검색에서_0건이다(db):
    _, searcher = db
    assert searcher.by_keyword("존재하지않는단어", 사원, k=10) == []


def test_하이브리드_검색이_두_경로를_모두_쓴다(db):
    _, searcher = db
    hits = search("네트워크 접근", 사원, 고정임베더(), searcher, k=10)
    assert len(hits) == 2      # 벡터가 2건을 주고 키워드가 1건을 더한다


def test_조항_코드까지_불러온다(db):
    _, searcher = db
    hits = search("네트워크", 사원, 고정임베더(), searcher, k=10)
    rows = searcher.load_hits(hits)
    assert all(isinstance(r, PolicyHit) for r in rows)
    assert {r.clause_code for r in rows} == {"2.6.1", "2.5.1"}


def test_load_hits_가_준_순서를_지킨다(db):
    # SQL 반환 순서에 기대면 융합 결과의 순위가 뒤집힌다.
    _, searcher = db
    ids = searcher.by_vector([0.1] * EMBEDDING_DIM, 사원, k=10)
    rows = searcher.load_hits(list(reversed(ids)))
    assert [r.chunk_id for r in rows] == list(reversed(ids))
```

- [ ] **Step 7: 테스트가 통과하는지 확인한다**

Run: `.venv/bin/python -m pytest -m db -v`

Expected: PASS — 앞선 10개 + 이번 7개 = 17개

- [ ] **Step 8: CLI 에 search 를 더한다**

`backend/pipeline/cli.py` 의 `sub` 정의 아래에 파서를 추가한다:

```python
    sch = sub.add_parser("search", help="하이브리드 검색")
    sch.add_argument("query")
    sch.add_argument("--clearance", type=int, default=1)
    sch.add_argument("--department", default="개발팀")
    sch.add_argument("-k", type=int, default=5)
    sch.add_argument("--dsn", default=None)
```

`main()` 의 `if args.cmd == "ingest":` 블록 아래에 더한다:

```python
    if args.cmd == "search":
        from adapters.db.chunk_search import PgChunkSearch
        from core.retrieve.hybrid import search as hybrid_search
        from core.types import Principal

        conn = connect(args.dsn)
        searcher = PgChunkSearch(conn)
        principal = Principal(department=args.department, clearance=args.clearance)

        ids = hybrid_search(args.query, principal, E5Embedder(), searcher, k=args.k)
        rows = searcher.load_hits(ids)

        print(f"질의: {args.query}")
        print(f"주체: {principal.department} · 등급 {principal.clearance}")
        print(f"결과: {len(rows)}건\n")
        for i, hit in enumerate(rows, start=1):
            표시 = f"[{hit.clause_code}]" if hit.clause_code else "[조항 밖]"
            print(f"  {i}. {표시} {hit.doc_title}")
            print(f"     {hit.text[:100].strip()}…\n")
        conn.close()
```

- [ ] **Step 9: 실제 검색을 돌려본다**

```bash
cd /Users/ryujun/Documents/secu-agent/backend
.venv/bin/python -m pipeline.cli search "네트워크 접근 통제는 어떻게 해야 하나" -k 5
```

Expected: 5건이 조항 코드와 함께 나온다. **조항 코드가 전부 `[조항 밖]` 이면** 청크가 조항에 연결되지 않은 것이므로 Task 4 의 분할이나 Task 5 의 `clause_ids` 매핑을 확인한다.

한국어 질의가 실제로 의미 있는 조항을 찾는지 눈으로 확인한다 — 이것이 W1 의 완료 판정이다.

- [ ] **Step 10: 커밋한다**

```bash
cd /Users/ryujun/Documents/secu-agent
git add backend/core/retrieve/hybrid.py backend/adapters/db/chunk_search.py \
        backend/pipeline/cli.py backend/tests/test_hybrid.py \
        backend/tests/test_search_integration.py
git commit -m "하이브리드 검색을 추가했다

벡터와 키워드를 RRF 로 융합한다. core/retrieve/hybrid.py 는 포트만 알아
DB 없이 스텁으로 테스트된다.

두 검색기 모두에 principal 을 넘긴다. 한쪽만 권한 필터를 적용하면 그쪽으로
누출된다 — 테스트가 두 검색기가 같은 주체를 받았는지 확인한다.

권한 WHERE 절을 지금 갖췄다. W1 에서는 모든 문서가 통과하지만, W2 에서
권한 데이터를 넣는 순간 필터가 저절로 동작해야 한다. 나중에 WHERE 를
끼워 넣으면 빠뜨린 경로가 생긴다.

질의는 query, 문서는 passage 접두어를 쓴다. 섞으면 에러가 아니라 조용한
품질 저하가 난다 — 테스트가 접두어를 확인한다.

융합 전에 k 의 5배를 후보로 가져온다. k 개씩만 가져오면 두 리스트가 거의
겹치지 않을 때 융합할 것이 없다.

load_hits 는 호출자가 준 id 순서를 지킨다. SQL 반환 순서에 기대면 융합
결과의 순위가 뒤집힌다."
```

---

### Task 8: CI

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md` (개발 절)

**Interfaces:**
- Consumes: Task 1~7 의 `pytest`·`ruff`
- Produces: 없음

- [ ] **Step 1: 워크플로를 만든다**

`.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
    paths-ignore: ['jekyll/**', 'docs/**']
  pull_request:
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true

      - name: 의존성 설치
        working-directory: backend
        run: uv sync --dev

      - name: 린트
        working-directory: backend
        run: |
          uv run ruff check .
          uv run ruff format --check .

      # DB·LLM 테스트는 pyproject 의 addopts 가 기본 제외한다.
      # 컨테이너와 API 키가 없는 환경에서 스위트 전체가 실패하면 안 된다.
      - name: 테스트
        working-directory: backend
        run: uv run pytest -v
```

- [ ] **Step 2: 로컬에서 CI 가 할 일을 그대로 돌린다**

```bash
cd /Users/ryujun/Documents/secu-agent/backend
uv sync --dev
uv run ruff check . && uv run ruff format --check .
uv run pytest -v
```

Expected: 린트 통과, 테스트 전부 통과(DB 테스트 제외)

- [ ] **Step 3: `README.md` 에 개발 절을 확인한다**

이미 있는 `## 개발` 절 아래에 DB 테스트 실행법을 더한다:

```markdown
DB 가 필요한 테스트는 기본 스위트에서 제외됩니다:

```bash
docker compose up -d
cd backend && .venv/bin/python -m pytest -m db -v
```
```

- [ ] **Step 4: 커밋하고 CI 가 도는지 확인한다**

```bash
cd /Users/ryujun/Documents/secu-agent
git add .github/workflows/ci.yml README.md
git commit -m "CI 를 추가했다

푸시마다 린트와 테스트를 돌린다. DB·LLM 테스트는 pyproject 의 addopts 가
기본 제외한다 — 컨테이너와 API 키가 없는 환경에서 스위트 전체가 실패하면
안 된다.

경계 테스트가 여기서 돈다. core/ 에 langchain 이나 psycopg 가 들어오면
CI 가 막는다."
git push -u origin main
gh run watch --exit-status
```

Expected: CI 성공

---

## 완료 조건

- [ ] `docker compose up -d` 로 pgvector 가 뜨고 `vector` 확장이 확인된다
- [ ] `.venv/bin/python -m pytest -q` 가 DB 없이 전부 통과한다
- [ ] `.venv/bin/python -m pytest -m db -v` 가 컨테이너와 함께 전부 통과한다
- [ ] `tests/test_boundaries.py` 가 위반을 **실제로 잡는다** (일부러 어겨 확인)
- [ ] `python -m pipeline.cli ingest ../data/raw/ismsp.pdf --title "ISMS-P 인증기준 안내서"` 가 고유 조항 **102개**를 적재한다 (2.10~2.12 포함 여부로 패턴 자릿수 결함을 잡는다)
- [ ] `python -m pipeline.cli search "네트워크 접근 통제는 어떻게 해야 하나"` 가 **조항 코드와 함께** 결과를 낸다
- [ ] CI 가 통과한다

## 다음 계획으로 넘길 것

- **Access Control 실동작** (W2) — 권한 데이터를 넣고 누출 테스트 3종(개수·순위·타이밍)을 세운다. SQL 은 이미 갖춰져 있다
- **청크 멱등성** — `chunks` 에 중복 방지 제약이 없다. `(document_id, clause_id, ordinal)` UNIQUE 를 걸거나 재적재 전 삭제한다
- **평가 하네스** (W2) — 골든셋과 Recall/MRR/nDCG
- **DOCX·MD 파서** — `loader.load` 가 현재 PDF 만 받고 나머지는 예외를 던진다
- **로그 파이프라인** (W4) — `log_events` 스키마는 이미 있다

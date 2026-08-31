# W2 구현 계획 — Access Control · 누출 테스트 · 평가 하네스

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 권한이 실제로 갈리는 코퍼스를 세우고, 사후 필터링이면 반드시 실패하는 누출 테스트와 검색 품질을 숫자로 재는 평가 하네스를 갖춘다.

**Architecture:** W1 이 사전 필터링 SQL(`_권한_WHERE` · `AS MATERIALIZED`)을 이미 갖췄으므로 W2 는 그 SQL 을 **판별할 수 있는 데이터와 장치**를 붙인다. 권한 규칙의 파이썬 쌍둥이가 `core/access/` 에 생기고, 도구 출력 재검증이 `core/agent/policy.py` 에 생긴다. 둘 다 표준 라이브러리만 쓴다. 합성 사내 규정은 마크다운으로 쓰고 `adapters/parsing/markdown.py` 가 읽는다. 평가는 바깥 계층인 `eval/` 이 소유하되 지표 함수는 DB 를 모르는 순수 함수다.

**Tech Stack:** Python 3.12, psycopg 3, pgvector, pypdf, PyYAML, sentence-transformers(multilingual-e5-small), pytest

**Spec:** `docs/superpowers/specs/2026-08-31-secu-agent-design.md`

**선행 계획:** `docs/superpowers/plans/2026-08-31-w1-document-pipeline.md` (완료)

## Global Constraints

- Python 3.12 이상. 가상환경은 `backend/.venv`, 실행은 `.venv/bin/python`, 작업 디렉토리는 `backend/`.
- **`core/` 는 바깥 계층(`adapters`·`api`·`pipeline`·`eval`)을 import 하지 않는다.**
- **`core/` 는 인프라·프레임워크(`psycopg`·`sqlalchemy`·`anthropic`·`fastapi`·`langchain`·`langgraph`·`sentence_transformers`·`torch`·`transformers`·`pypdf`)를 import 하지 않는다.** 이번 주에 `yaml` 을 쓰지만 `adapters/parsing/` 에서만 쓴다.
- 경계 인터페이스는 `core/ports.py` 가 소유한다. `adapters/` 가 구현한다.
- 임베딩 차원은 `core/types.EMBEDDING_DIM`(384)이 단일 출처다. 모델은 `intfloat/multilingual-e5-small`.
- **e5 계열은 `query:` / `passage:` 접두어를 요구한다.** 접두어를 빼면 검색 품질이 조용히 나빠진다.
- 검색 함수는 `Principal` 을 필수 인자로 받는다 (spec 5.3).
- 테스트 함수 이름은 한국어로 쓴다.
- 커밋 메시지는 한국어, 평서형(`~했다`).
- DB 가 필요한 테스트는 `pytest.mark.db`, 임베딩 모델이 필요하면 `pytest.mark.model` 을 단다. 기본 스위트가 둘 다 제외한다.

---

## 계획을 쓰기 전에 실물로 확인한 것

계획서의 SQL·기하·의존성이 실제 엔진에서 다르게 도는 일을 막기 위해 먼저 재봤다. **두 개가 계획을 바꿨다.**

**① 벽시계 타이밍 테스트는 아무것도 지키지 않는다.** spec 8.2 의 `test_응답시간_차이가_유의하지_않다` 를 벽시계로 짜면 고장난 구현에서도 통과한다.

pgvector:pg16, 공개 300 + 기밀 300 청크, 등급 1 주체가 질의 두 종(A=기밀 축, B=공개 축)을 30회씩:

| | 결과 개수 A / B | 벽시계 중앙값 A / B (비) |
|---|---|---|
| 사전 필터링 (현행) | 10건 / 10건 | 0.42ms / 0.36ms (**1.17**) |
| 사후 필터링 (변종) | **0건** / 10건 | 0.34ms / 0.28ms (**1.21**) |

시간 비율이 사실상 같다 — 어떤 임계를 골라도 두 구현을 가르지 못한다. 반면 **결과 개수는 0 대 10 으로 갈린다.** 그래서 타이밍 채널은 벽시계가 아니라 `EXPLAIN (ANALYZE, FORMAT JSON)` 의 **CTE Scan `Actual Rows`** 로 잰다 — 사전 필터링에서는 A·B 모두 300 으로 동일했다. "훑는 후보 집합이 주체에만 의존하고 질의에는 의존하지 않는다"가 타이밍 채널이 없다는 **구조적 근거**이고, 결정론적이라 CI 에서 흔들리지 않는다. Task 5 가 이 형태로 짓는다.

**② 난수 벡터 픽스처는 기하가 통제되지 않는다.** 384차원 단위벡터 두 개를 뽑았더니 `cos(A,B)=0.101` 이 나왔고, "기밀 문서 근처" 로 심은 청크들이 무관해야 할 질의 B 의 상위 10건 중 9건을 차지했다. 픽스처가 재려던 것을 못 재게 된다. **좌표 블록으로 직교를 강제한다** — 앞 절반은 기밀 축, 뒤 절반은 공개 축으로 두면 내적이 구조적으로 정확히 0 이다. Task 5 의 픽스처가 이 방식이다.

**③ 청크 삭제는 배치 루프 밖에 있어야 한다.** `pipeline/ingest.py` 는 `insert_chunks` 를 배치로 나눠 부른다(255쪽 문서는 청크가 314개). 멱등성을 `insert_chunks` 안의 DELETE 로 구현하면 **두 번째 배치가 첫 번째 배치를 지운다.** Task 1 이 포트 메서드를 따로 두는 이유다.

**④ `UNIQUE (document_id, clause_id, ordinal)` 로는 멱등성이 안 된다.** `clause_id` 가 NULL 인 청크(조항 밖 텍스트)는 SQL 에서 NULL 끼리 서로 다르다고 보므로 제약이 걸리지 않는다. 삭제 후 삽입으로 간다.

**⑤ `pyyaml` 은 선언된 의존성이 아니다.** 지금 `.venv` 에 6.0.3 이 있지만 `transformers`·`huggingface_hub` 의 전이 의존일 뿐이다(`pyproject.toml`·`requirements.txt` 에 없다). 그쪽이 의존을 끊으면 적재가 import 단계에서 깨진다. Task 2 가 명시적으로 선언한다.

**⑥ 골든셋 재료는 충분하다.** 적재된 ISMS-P 조항 102개 중 본문이 200자 미만인 것은 0개, 대부분 1,300~3,500자다. 조항 코드를 정답 라벨로 쓰기에 충분히 길고 구분된다.

---

## File Structure

```
data/
  policies/                     합성 사내 규정 (마크다운) — 8개
    01-정보보안-기본지침.md
    02-계정-비밀번호-운영.md
    03-개발팀-서버접근-절차.md
    04-보안팀-침해사고-대응.md
    05-인사팀-징계-절차.md
    06-팀장-인사평가-운영.md
    07-임원-성과급-산정.md
    08-임원-경영감사-지침.md
  principals.json               시연 계정 3개
backend/
  core/
    types.py                    (수정) PolicyHit 에 권한 메타 두 필드
    ports.py                    (수정) DocumentStore.delete_chunks
    access/
      __init__.py
      visibility.py             가시성 규칙 — 순수 함수. SQL WHERE 의 파이썬 쌍둥이
    agent/
      __init__.py
      policy.py                 도구 출력 재검증 — 위반 시 예외
  adapters/
    parsing/
      chunking.py               (이동) chunk_clauses — pdf 와 markdown 이 공유
      pdf.py                    (수정) chunking 에서 재수출
      markdown.py               front matter + "## 4.1.1 제목" 조항 분할
      loader.py                 (수정) .md 를 받는다
    db/
      document_store.py         (수정) delete_chunks
      chunk_search.py           (수정) load_hits 가 권한 메타를 채운다
  pipeline/
    ingest.py                   (수정) 배치 루프 밖에서 delete_chunks 한 번
    cli.py                      (수정) ingest-dir · seed-principals · demo
  eval/
    data/golden.jsonl           골든셋 30건
    golden.py                   골든셋 로더
    metrics.py                  Recall@k · MRR@k · nDCG@k — 순수 함수
    harness.py                  골든셋을 실제 검색에 물린다
    run.py                      python -m eval.run → 마크다운 표
  tests/
    test_visibility.py          가시성 규칙
    test_policy_enforce.py      도구 출력 재검증
    test_markdown_parsing.py    front matter · 조항 분할
    test_metrics.py             지표 손계산 사례
    test_leakage.py             누출 4종 (db 마커)
```

**책임 분리 근거:** `visibility.py` 가 `policy.py` 와 분리된 것은 전자가 "보이는가"라는 **질문**이고 후자가 "안 보이는 게 섞였으면 터진다"는 **정책**이기 때문이다. 질문은 여러 곳에서 쓰이고 정책은 도구 경계에서만 쓰인다. `metrics.py` 가 DB 를 모르는 것은 의도적이다 — 지표 계산이 조용히 틀리면 모든 숫자가 거짓이 되므로 손계산 사례로 DB 없이 검증되어야 한다.

---

### Task 1: 청크 멱등성

**Files:**
- Modify: `backend/core/ports.py` (`DocumentStore` Protocol)
- Modify: `backend/adapters/db/document_store.py`
- Modify: `backend/pipeline/ingest.py`
- Test: `backend/tests/test_ingest.py`, `backend/tests/test_db_integration.py`

**Interfaces:**
- Consumes: 없음
- Produces: `DocumentStore.delete_chunks(document_id: int) -> int` — 지운 청크 수를 돌려준다. Task 2 가 8개 문서를 반복 적재하며 이것에 기댄다.

W2 는 코퍼스를 여러 번 다시 적재한다. 지금 재적재하면 청크가 **누적된다** — 같은 본문이 두 벌 들어가 검색 결과에 중복이 뜨고, 평가 지표가 거짓이 된다. 다른 모든 태스크가 이것 위에 서므로 먼저 한다.

- [ ] **Step 1: 실패하는 스텁 테스트를 쓴다**

`backend/tests/test_ingest.py` 의 `메모리저장소` 에 메서드를 더하고, 파일 끝에 테스트 두 개를 더한다.

`메모리저장소` 안 `count_all_chunks` 바로 위에 넣는다:

```python
    def delete_chunks(self, document_id):
        지운수 = len(self.chunks)
        self.chunks.clear()
        self.vectors.clear()
        self.delete_calls = getattr(self, "delete_calls", 0) + 1
        return 지운수
```

파일 끝에 더한다:

```python
def test_두_번_적재해도_청크가_누적되지_않는다():
    # 재적재가 누적되면 같은 본문이 두 벌 검색되고 평가 지표가 거짓이 된다.
    e, s = 스텁임베더(), 메모리저장소()
    ingest(Path("a.pdf"), _문서(), _로더, e, s)
    ingest(Path("a.pdf"), _문서(), _로더, e, s)
    assert len(s.chunks) == 2


def test_청크_삭제는_배치마다가_아니라_적재당_한_번이다():
    """배치 루프 안에서 지우면 두 번째 배치가 첫 번째 배치를 지운다.

    실측: 255쪽 ISMS-P 는 청크 314개 · batch_size 64 로 5배치다.
    루프 안에서 지우면 마지막 배치 58개만 남는다.
    """
    def 큰로더(path):
        return [], [Chunk(clause_code=None, ordinal=i, text=f"청크 {i}") for i in range(250)]

    e, s = 스텁임베더(), 메모리저장소()
    ingest(Path("a.pdf"), _문서(), 큰로더, e, s, batch_size=64)
    assert s.delete_calls == 1
    assert len(s.chunks) == 250
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_ingest.py -v`
Expected: 두 테스트 FAIL — `test_두_번_적재해도…` 는 `assert 4 == 2`, `test_청크_삭제는…` 은 `AttributeError: '메모리저장소' object has no attribute 'delete_calls'` (또는 `assert 0 == 1`)

- [ ] **Step 3: 포트에 메서드를 더한다**

`backend/core/ports.py` 의 `DocumentStore` 에서 `count_all_chunks` **바로 위**에 넣는다:

```python
    def delete_chunks(self, document_id: int) -> int:
        """문서의 청크를 전부 지우고 지운 개수를 돌려준다.

        재적재를 멱등하게 만드는 유일한 수단이다. UNIQUE (document_id,
        clause_id, ordinal) 제약으로는 안 된다 — clause_id 가 NULL 인
        청크(조항 밖 텍스트)는 SQL 에서 NULL 끼리 서로 다르다고 보므로
        제약이 아예 걸리지 않는다.
        """
        ...
```

- [ ] **Step 4: 오케스트레이션에서 한 번만 부른다**

`backend/pipeline/ingest.py` 의 `ingest` 안, `document_id = store.upsert_document(doc)` 바로 아래에 넣는다:

```python
    # 배치 루프 **밖**이다. insert_chunks 안에 두면 두 번째 배치가 첫 번째
    # 배치를 지운다 — 314청크짜리 ISMS-P 가 마지막 배치만 남는다.
    store.delete_chunks(document_id)
```

- [ ] **Step 5: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_ingest.py -v`
Expected: PASS (기존 5개 + 새 2개)

- [ ] **Step 6: 어댑터를 구현한다**

`backend/adapters/db/document_store.py` 의 `count_all_chunks` 바로 위에 넣는다:

```python
    def delete_chunks(self, document_id: int) -> int:
        """문서의 청크를 전부 지운다. 재적재 전에 한 번 부른다.

        실패하면 롤백한다 — 실패한 statement 는 커넥션을 aborted 로 남기고,
        그 상태의 다음 에러 메시지는 진짜 원인이 아니다.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
                지운수 = cur.rowcount
            self.conn.commit()
            return 지운수
        except Exception:
            self.conn.rollback()
            raise
```

- [ ] **Step 7: DB 테스트를 쓴다**

`backend/tests/test_db_integration.py` 끝에 더한다:

```python
def test_청크를_지우면_문서와_조항은_남는다(store):
    doc_id = store.upsert_document(_문서())
    ids = store.insert_clauses(doc_id, [Clause(code="2.6.1", title="가", text="본문")])
    store.insert_chunks(
        doc_id, ids, [Chunk(clause_code="2.6.1", ordinal=0, text="청크")], [_벡터()]
    )

    assert store.delete_chunks(doc_id) == 1
    assert store.count_all_chunks() == 0

    # 문서와 조항은 살아 있어야 한다 — 재적재가 새 조항 id 를 만들면
    # 기존 인용(조항 코드)이 가리키던 행이 사라진다.
    with store.conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM documents WHERE id = %s", (doc_id,))
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM clauses WHERE document_id = %s", (doc_id,))
        assert cur.fetchone()[0] == 1


def test_같은_문서를_두_번_적재해도_청크가_늘지_않는다(store):
    def 적재():
        doc_id = store.upsert_document(_문서())
        store.delete_chunks(doc_id)
        ids = store.insert_clauses(doc_id, [Clause(code="2.6.1", title="가", text="본문")])
        store.insert_chunks(
            doc_id, ids, [Chunk(clause_code="2.6.1", ordinal=0, text="청크")], [_벡터()]
        )

    적재()
    적재()
    assert store.count_all_chunks() == 1
```

- [ ] **Step 8: DB 테스트를 돌린다**

```bash
docker compose up -d
cd backend && .venv/bin/python -m pytest -m db tests/test_db_integration.py -v
```
Expected: PASS (기존 12개 + 새 2개)

- [ ] **Step 9: 전체 스위트와 린트를 돌리고 커밋한다**

```bash
cd backend
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format .
.venv/bin/python -m pytest -q
cd /Users/ryujun/Documents/secu-agent
git add backend/core/ports.py backend/adapters/db/document_store.py \
        backend/pipeline/ingest.py backend/tests/test_ingest.py \
        backend/tests/test_db_integration.py
git commit -m "재적재가 청크를 누적하던 것을 고쳤다

DocumentStore 에 delete_chunks 를 두고 ingest 가 배치 루프 밖에서 한 번만
부른다. insert_chunks 안에서 지우면 두 번째 배치가 첫 번째 배치를 지운다 —
314청크짜리 ISMS-P 가 마지막 배치 58개만 남는다.

UNIQUE (document_id, clause_id, ordinal) 로는 안 된다. clause_id 가 NULL 인
조항 밖 청크는 NULL 끼리 서로 다르다고 보므로 제약이 걸리지 않는다."
```

---

### Task 2: 마크다운 파서와 합성 사내 규정 코퍼스

**Files:**
- Modify: `backend/pyproject.toml`, `backend/requirements.txt`
- Create: `backend/adapters/parsing/chunking.py` (`pdf.py` 에서 이동)
- Modify: `backend/adapters/parsing/pdf.py`, `backend/adapters/parsing/loader.py`
- Create: `backend/adapters/parsing/markdown.py`
- Create: `data/policies/*.md` (8개)
- Modify: `backend/pipeline/cli.py`
- Test: `backend/tests/test_markdown_parsing.py`

**Interfaces:**
- Consumes: `DocumentStore.delete_chunks` (Task 1)
- Produces:
  - `adapters.parsing.chunking.chunk_clauses(clauses: list[Clause], max_chars: int = 900, overlap: int = 150) -> list[Chunk]`
  - `adapters.parsing.markdown.parse_front_matter(text: str) -> tuple[dict, str]` — (메타, 본문)
  - `adapters.parsing.markdown.split_clauses(body: str) -> list[Clause]`
  - `adapters.parsing.loader.load(path: Path) -> tuple[list[Clause], list[Chunk]]` — `.pdf`·`.md` 를 받는다
  - `adapters.parsing.loader.load_meta(path: Path) -> dict` — `.md` 의 front matter, `.pdf` 는 `{}`
  - CLI: `python -m pipeline.cli ingest-dir data/policies`

지금 코퍼스는 `documents` 행이 하나(ISMS-P, 등급 1, 전사 공개)다. **권한이 한 종류뿐이라 누출 테스트도 시연도 성립하지 않는다.** ISMS-P 는 진짜 본문·전사 공개로 그대로 두고, 등급·부서가 갈리는 사내 규정을 합성해 옆에 세운다.

**본문까지 합성이라는 사실을 문서에 명시한다.** spec 4.1 의 "본문은 진짜, 권한 구조는 설계" 는 ISMS-P 에만 해당한다. 사내 규정은 둘 다 합성이므로 각 파일 첫 줄에 그렇게 적는다.

- [ ] **Step 1: PyYAML 을 명시적으로 선언한다**

지금 `.venv` 에 PyYAML 6.0.3 이 있지만 `transformers`·`huggingface_hub` 의 **전이 의존**일 뿐이다. 그쪽이 의존을 끊으면 적재가 import 단계에서 깨진다.

`backend/pyproject.toml` 의 `dependencies` 를 아래로 바꾼다:

```toml
dependencies = [
    "psycopg[binary]>=3.2",
    "pypdf>=5.1",
    "pyyaml>=6.0",
    "sentence-transformers>=3.3",
]
```

`backend/requirements.txt` 를 아래로 바꾼다:

```
psycopg[binary]>=3.2
pypdf>=5.1
pyyaml>=6.0
sentence-transformers>=3.3
```

- [ ] **Step 2: `chunk_clauses` 를 공용 모듈로 옮긴다**

두 번째 호출자(markdown)가 생겼기 때문이다. 청킹은 문서 포맷과 무관한 규칙이다.

`backend/adapters/parsing/chunking.py` 를 새로 만들고, **`pdf.py` 의 `chunk_clauses` 함수 본문을 통째로 옮긴다**(독스트링·주석 포함, 한 글자도 바꾸지 않는다):

```python
"""조항 안에서 청킹한다. 문서 포맷과 무관한 규칙이라 파서들이 공유한다.

pdf.py 에 있던 것을 옮겼다 — markdown.py 라는 두 번째 호출자가 생겼기
때문이다. 청킹 규칙이 두 벌로 갈라지면 PDF 와 MD 의 청크 크기가 조용히
달라지고, 평가 지표가 포맷에 따라 흔들린다.
"""

from core.types import Chunk, Clause


def chunk_clauses(clauses: list[Clause], max_chars: int = 900, overlap: int = 150) -> list[Chunk]:
    ...  # pdf.py 에서 옮긴 본문 그대로
```

그리고 `backend/adapters/parsing/pdf.py` 에서 `chunk_clauses` 정의를 지우고 맨 위 import 에 더한다:

```python
from adapters.parsing.chunking import chunk_clauses
```

`pdf.chunk_clauses` 와 `from adapters.parsing.pdf import chunk_clauses` 를 쓰는 곳(`loader.py`·`tests/test_pdf_parsing.py`)이 그대로 돌게 재수출한다. **`__all__` 이 장식이 아니다** — 이것이 없으면 `pdf.py` 의 `chunk_clauses` 는 쓰이지 않는 import 라서 `ruff` 가 F401 로 막고 CI 가 실패한다. `pdf.py` 파일 맨 아래에 더한다:

```python
# loader 와 기존 테스트가 pdf.chunk_clauses 로 부른다. 이름을 유지한다.
__all__ = ["extract_text", "split_clauses", "chunk_clauses", "조항_패턴", "참고자료_표지"]
```

- [ ] **Step 3: 이동이 아무것도 깨지 않았는지 확인한다**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 전부 PASS. 실패하면 옮기는 중에 본문을 바꾼 것이다 — 되돌리고 다시 옮긴다.

- [ ] **Step 4: 마크다운 파서의 실패하는 테스트를 쓴다**

`backend/tests/test_markdown_parsing.py` 를 만든다:

```python
"""마크다운 사내 규정 파서.

front matter 가 권한을 들고 있는 이유: 문서 8개를 CLI 인자 8벌로 적재하면
어느 문서가 어느 등급인지가 셸 히스토리에만 남는다. 문서가 자기 등급을
들고 있어야 재적재가 같은 결과를 낸다.
"""

import pytest

from adapters.parsing.markdown import parse_front_matter, split_clauses

문서 = """---
title: 임원 성과급 산정 기준
clearance: 3
departments: []
---

## 6.1.1 성과급 재원 산정

영업이익의 일정 비율을 재원으로 삼는다.

## 6.1.2 지급 시기

회계연도 종료 후 90일 이내에 지급한다.
"""


def test_front_matter_를_읽는다():
    meta, body = parse_front_matter(문서)
    assert meta["title"] == "임원 성과급 산정 기준"
    assert meta["clearance"] == 3
    assert meta["departments"] == []


def test_front_matter_는_본문에_남지_않는다():
    # 남으면 "clearance: 3" 이 청크로 적재되어 검색된다.
    _, body = parse_front_matter(문서)
    assert "clearance" not in body
    assert body.lstrip().startswith("## 6.1.1")


def test_front_matter_가_없으면_예외를_던진다():
    # 조용히 기본값을 쓰면 등급 3 문서가 등급 1 로 적재된다 —
    # 누출이고, 발견이 아주 늦다.
    with pytest.raises(ValueError):
        parse_front_matter("## 6.1.1 제목\n본문")


def test_조항_코드와_제목을_나눈다():
    _, body = parse_front_matter(문서)
    clauses = split_clauses(body)
    assert [c.code for c in clauses] == ["6.1.1", "6.1.2"]
    assert clauses[0].title == "성과급 재원 산정"


def test_조항_본문이_다음_조항까지만이다():
    _, body = parse_front_matter(문서)
    clauses = split_clauses(body)
    assert "영업이익" in clauses[0].text
    assert "회계연도" not in clauses[0].text


def test_세_자리_조항만_받는다():
    # ISMS-P 파서와 같은 규칙이다. "## 개요" 같은 제목은 조항이 아니다.
    clauses = split_clauses("## 개요\n머리말\n\n## 6.1.1 진짜 조항\n본문")
    assert [c.code for c in clauses] == ["6.1.1"]
    assert "머리말" not in clauses[0].text
```

- [ ] **Step 5: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_markdown_parsing.py -v`
Expected: 전부 FAIL — `ModuleNotFoundError: No module named 'adapters.parsing.markdown'`

- [ ] **Step 6: 마크다운 파서를 구현한다**

`backend/adapters/parsing/markdown.py`:

```python
"""마크다운 → 조항 → 청크.

합성 사내 규정을 읽는다. 각 문서는 front matter 로 자기 권한을 들고 있다 —
CLI 인자로 받으면 어느 문서가 어느 등급인지가 셸 히스토리에만 남고,
재적재가 다른 결과를 낸다.

조항 코드는 ISMS-P 와 같은 세 자리(4.1.1) 형태다. 파서 두 벌이 다른 코드
체계를 쓰면 리포트의 인용 형식이 문서마다 달라진다. 4.x·5.x·6.x 를 쓰는
이유는 ISMS-P 가 1.x~3.x 를 차지하고 있어 코드가 부딪히지 않기 위해서다.

이 모듈은 문서 포맷만 안다 — DB 도 임베딩도 모른다.
"""

import re
from pathlib import Path

import yaml

from adapters.parsing.chunking import chunk_clauses
from core.types import Chunk, Clause

_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)

# "## 6.1.1 성과급 재원 산정" — pdf.조항_패턴 과 같은 세 자리 규칙이다.
# 각 자리가 \d+ 인 것이 중요하다. \d 로 쓰면 4.10.1 이 매치되지 않는다 —
# W1 실측에서 ISMS-P 조항 16개를 그렇게 잃었다.
조항_패턴 = re.compile(r"^##\s+(\d+\.\d+\.\d+)\s+(\S[^\n]{0,60})$", re.MULTILINE)


def parse_front_matter(text: str) -> tuple[dict, str]:
    """(메타, 본문) 으로 나눈다. front matter 가 없으면 예외를 던진다.

    조용히 기본값을 쓰지 않는다 — 등급 3 문서가 등급 1 로 적재되면
    그것이 곧 누출이고, 검색이 되어버리므로 발견이 아주 늦다.
    """
    m = _FRONT_MATTER.match(text)
    if not m:
        raise ValueError("front matter 가 없다 — 문서가 자기 권한을 들고 있어야 한다")
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError(f"front matter 가 매핑이 아니다: {type(meta).__name__}")
    return meta, text[m.end() :]


def split_clauses(body: str) -> list[Clause]:
    """"## 6.1.1 제목" 으로 본문을 조항 단위로 나눈다.

    첫 조항 앞의 머리말은 버린다 — 조항이 아니라서 "규정 어디에 있다"고
    말할 수 없다. PDF 파서가 표지·목차를 버리는 것과 같은 이유다.
    """
    matches = list(조항_패턴.finditer(body))
    clauses: list[Clause] = []
    for i, m in enumerate(matches):
        끝 = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        clauses.append(
            Clause(code=m.group(1), title=m.group(2).strip(), text=body[m.end() : 끝].strip())
        )
    return clauses


def load(path: Path) -> tuple[list[Clause], list[Chunk]]:
    _, body = parse_front_matter(path.read_text(encoding="utf-8"))
    clauses = split_clauses(body)
    return clauses, chunk_clauses(clauses)


def load_meta(path: Path) -> dict:
    meta, _ = parse_front_matter(path.read_text(encoding="utf-8"))
    return meta
```

- [ ] **Step 7: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_markdown_parsing.py -v`
Expected: 6개 PASS

- [ ] **Step 8: 로더가 `.md` 를 받게 한다**

`backend/adapters/parsing/loader.py` 를 통째로 바꾼다:

```python
"""확장자로 파서를 고른다.

DOCX 는 아직 범위 밖이다. 지원하지 않는 포맷은 조용히 건너뛰지 않고
예외를 던진다 — 조용히 넘기면 적재가 끝난 뒤에야 문서가 없다는 것을 안다.
"""

from pathlib import Path

from adapters.parsing import markdown, pdf
from core.types import Chunk, Clause


def load(path: Path) -> tuple[list[Clause], list[Chunk]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        clauses = pdf.split_clauses(pdf.extract_text(path))
        return clauses, pdf.chunk_clauses(clauses)
    if suffix == ".md":
        return markdown.load(path)
    raise ValueError(f"아직 지원하지 않는 포맷이다: {suffix} ({path})")


def load_meta(path: Path) -> dict:
    """문서가 스스로 들고 있는 메타데이터. PDF 에는 없다.

    빈 딕셔너리를 주는 것이 맞다 — PDF 의 권한은 적재하는 사람이
    CLI 인자로 부여한다(spec 4.1).
    """
    if path.suffix.lower() == ".md":
        return markdown.load_meta(path)
    return {}
```

- [ ] **Step 9: 시연과 테스트가 기대는 문서 두 개를 쓴다**

Task 5 의 누출 테스트와 Task 7 의 시연이 이 두 문서에 정확히 기댄다. 내용을 그대로 쓴다.

`data/policies/07-임원-성과급-산정.md`:

```markdown
---
title: 임원 성과급 산정 기준
clearance: 3
departments: []
---

<!-- 합성 문서다. 본문과 권한 모두 이 프로젝트를 위해 지어낸 것이고
     실재하는 회사의 규정이 아니다. ISMS-P 안내서(본문 진짜, 권한 합성)와
     성격이 다르므로 여기 적어둔다. -->

## 6.1.1 성과급 재원 산정

임원 성과급의 재원은 해당 회계연도 영업이익의 100분의 3을 상한으로 한다.
영업이익이 직전 연도 대비 감소한 경우 재원을 편성하지 아니한다.
재원 규모는 보상위원회의 심의를 거쳐 이사회가 확정한다.

## 6.1.2 개인별 배분 기준

개인별 성과급은 전사 목표 달성도 60퍼센트, 담당 부문 목표 달성도 40퍼센트를
가중 평균하여 산정한다. 산정 결과는 기본 연봉의 0퍼센트에서 200퍼센트 사이로 한다.
징계 처분을 받은 임원은 해당 연도 지급 대상에서 제외한다.

## 6.1.3 지급 시기와 환수

성과급은 회계연도 종료 후 90일 이내에 지급한다.
지급 후 산정 근거가 된 재무제표가 정정된 경우 정정일부터 3년 이내에 환수할 수 있다.
```

`data/policies/03-개발팀-서버접근-절차.md`:

```markdown
---
title: 개발팀 서버 접근 절차
clearance: 1
departments: [개발팀]
---

<!-- 합성 문서다. 본문과 권한 모두 이 프로젝트를 위해 지어낸 것이다. -->

## 5.1.1 운영 서버 접근 승인

운영 서버에 접근하려는 개발자는 접근 사유와 기간을 적어 팀장의 승인을 받는다.
승인 없이 부여된 접근 권한은 발견 즉시 회수한다.
긴급 장애 대응은 선조치 후 24시간 이내에 사후 승인을 받는다.

## 5.1.2 접근 계정과 인증

운영 서버 접근은 개인 계정으로만 한다. 공용 계정 사용을 금지한다.
접근 시 다중 인증을 적용하며, 인증 수단은 분기마다 갱신한다.

## 5.1.3 접속 기록 보관

운영 서버 접속 기록은 접속 일시, 계정, 출발지 주소, 실행 명령을 포함하여
1년간 보관한다. 보관된 기록은 임의로 수정하거나 삭제할 수 없다.
```

- [ ] **Step 10: 나머지 문서 여섯 개를 쓴다**

같은 형식이다. 각 문서는 front matter 와 합성 사실을 밝히는 주석, 그리고 조항 3개(각 조항 본문 3~5줄, 200자 이상)를 갖는다. **조항 본문이 200자 미만이면 청크가 지나치게 짧아 검색 품질 평가가 왜곡된다** — 실측: 적재된 ISMS-P 조항 102개 중 200자 미만은 0개다.

| 파일 | title | clearance | departments | 조항 코드와 제목 |
|---|---|---|---|---|
| `01-정보보안-기본지침.md` | 정보보안 기본지침 | 1 | `[]` | `4.1.1` 목적과 적용 범위 · `4.1.2` 임직원의 의무 · `4.1.3` 위반 시 조치 |
| `02-계정-비밀번호-운영.md` | 계정 및 비밀번호 운영 기준 | 1 | `[]` | `4.2.1` 계정 발급과 회수 · `4.2.2` 비밀번호 복잡도와 변경 주기 · `4.2.3` 휴면 계정 처리 |
| `04-보안팀-침해사고-대응.md` | 보안팀 침해사고 대응 절차 | 2 | `[보안팀]` | `5.3.1` 사고 접수와 등급 분류 · `5.3.2` 초동 조치와 격리 · `5.3.3` 사후 분석과 보고 |
| `05-인사팀-징계-절차.md` | 인사팀 징계 절차 | 2 | `[인사팀]` | `5.2.1` 보안 위반 징계 기준 · `5.2.2` 징계위원회 구성 · `5.2.3` 소명 기회 보장 |
| `06-팀장-인사평가-운영.md` | 팀장 인사평가 운영 기준 | 2 | `[]` | `5.4.1` 평가 주기와 방법 · `5.4.2` 평가 등급 분포 · `5.4.3` 이의 제기 절차 |
| `08-임원-경영감사-지침.md` | 임원 경영감사 지침 | 3 | `[]` | `6.2.1` 감사 대상과 범위 · `6.2.2` 감사 결과 보고 · `6.2.3` 지적 사항 이행 점검 |

**등급·부서 배치의 근거:** 시연은 세 계정(개발팀·등급1 / 인사팀·등급2 / 등급3 임원)으로 한다. `03` 은 부서 축만, `06` 은 등급 축만, `05` 는 두 축을 동시에 가른다 — 한 축만 있으면 다른 축의 결함이 안 잡힌다.

- [ ] **Step 11: 디렉토리 적재 명령을 더한다**

`backend/pipeline/cli.py` 의 서브파서 정의부(`sch = sub.add_parser("search"…)` 위)에 더한다:

```python
    ind = sub.add_parser("ingest-dir", help="디렉토리의 마크다운 규정을 전부 적재한다")
    ind.add_argument("path", type=Path)
    ind.add_argument("--dsn", default=None)
```

그리고 `if args.cmd == "ingest":` 블록 **아래**에 더한다:

```python
    if args.cmd == "ingest-dir":
        경로들 = sorted(args.path.glob("*.md"))
        if not 경로들:
            print(f"마크다운 문서가 없다: {args.path}", file=sys.stderr)
            return 1

        conn = connect(args.dsn)
        apply_schema(conn)
        store = PgDocumentStore(conn)
        embedder = E5Embedder()  # 모델을 한 번만 로드한다

        for p in 경로들:
            meta = load_meta(p)
            doc = Document(
                id=0,
                title=meta["title"],
                source_path=str(p),
                doc_type="md",
                required_clearance=int(meta["clearance"]),
                allowed_departments=tuple(meta.get("departments") or ()),
            )
            report = ingest(p, doc, load, embedder, store)
            부서 = ",".join(doc.allowed_departments) or "전사"
            print(
                f"  {p.name}: 조항 {report.clauses}개 · 청크 {report.chunks}개 "
                f"(등급 {doc.required_clearance} · {부서})"
            )

        print(f"DB 총 청크: {store.count_all_chunks()}")
        conn.close()
```

맨 위 import 에 `load_meta` 를 더한다:

```python
from adapters.parsing.loader import load, load_meta
```

- [ ] **Step 12: 실제로 적재한다**

```bash
docker compose up -d
cd backend
.venv/bin/python -m pipeline.cli ingest ../data/raw/ismsp.pdf --title "ISMS-P 인증기준 안내서"
.venv/bin/python -m pipeline.cli ingest-dir ../data/policies
```

Expected: ISMS-P 는 조항 102개 · 청크 314개. 사내 규정 8개는 각각 조항 3개. `DB 총 청크` 가 340 안팎.

**확인:** 재적재가 멱등한지 본다 — 같은 두 명령을 한 번 더 돌리고 `DB 총 청크` 가 같은 수인지 본다. 늘어나면 Task 1 이 덜 된 것이다.

- [ ] **Step 13: 린트하고 커밋한다**

```bash
cd backend
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format .
.venv/bin/python -m pytest -q
cd /Users/ryujun/Documents/secu-agent
git add backend/pyproject.toml backend/requirements.txt backend/adapters/parsing/ \
        backend/pipeline/cli.py backend/tests/test_markdown_parsing.py data/policies/
git commit -m "마크다운 파서와 합성 사내 규정 8개를 더했다

코퍼스가 ISMS-P 한 권뿐이라 권한이 한 종류였고, 그래서 누출 테스트도 시연도
성립하지 않았다. 등급 1·2·3 과 부서가 갈리는 사내 규정을 옆에 세운다.

문서가 front matter 로 자기 권한을 들고 있다. CLI 인자로 받으면 어느 문서가
어느 등급인지가 셸 히스토리에만 남는다. front matter 가 없으면 예외를 던진다 —
조용히 기본값을 쓰면 등급 3 문서가 등급 1 로 적재되고, 그게 곧 누출이다.

chunk_clauses 를 chunking.py 로 옮겼다. 두 번째 호출자가 생겼고, 규칙이 두 벌로
갈라지면 포맷에 따라 청크 크기가 달라진다.

pyyaml 을 명시적으로 선언했다. 지금 있는 것은 transformers 의 전이 의존이라
그쪽이 끊으면 적재가 import 단계에서 깨진다.

사내 규정은 본문까지 합성이다. ISMS-P(본문 진짜·권한 합성)와 성격이 달라
각 파일에 그 사실을 적었다."
```

---

### Task 3: 가시성 규칙과 `PolicyHit` 권한 메타

**Files:**
- Create: `backend/core/access/__init__.py`, `backend/core/access/visibility.py`
- Modify: `backend/core/types.py` (`PolicyHit`)
- Modify: `backend/adapters/db/chunk_search.py` (`load_hits`)
- Modify: `backend/tests/test_types.py`
- Test: `backend/tests/test_visibility.py`, `backend/tests/test_search_integration.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `core.access.visibility.visible(required_clearance: int, allowed_departments: tuple[str, ...], p: Principal) -> bool`
  - `core.types.PolicyHit` 에 `required_clearance: int` 와 `allowed_departments: tuple[str, ...]` 추가 (기본값 없음)

Task 4 의 `enforce` 가 이것 없이는 **아무것도 검증할 수 없다.** 현재 `PolicyHit` 은 `chunk_id · text · doc_title · clause_code` 뿐이라 판단 근거가 없다 — spec 5.4 가 요구하는 재검증이 구조적으로 불가능하다.

**새로 생기는 위험을 먼저 말해둔다.** W1 까지 권한 규칙은 SQL `_권한_WHERE` **한 곳**에만 있었다. 여기서 파이썬 쌍둥이가 생기므로 **둘이 어긋날 수 있다.** Step 7 의 대조 테스트가 그것을 막는다.

- [ ] **Step 1: 가시성 규칙의 실패하는 테스트를 쓴다**

`backend/tests/test_visibility.py`:

```python
"""가시성 규칙 — spec 3.1 의 두 줄.

이 규칙이 단순한 이유가 있다. SQL WHERE 로 그대로 번역되어야 사전
필터링이 된다. 복잡해지면 애플리케이션 레이어로 밀려나고, 그 순간
사후 필터링이 되어 존재가 누출된다.
"""

from core.access.visibility import visible
from core.types import Principal

사원 = Principal(department="개발팀", clearance=1)
팀장 = Principal(department="인사팀", clearance=2)
임원 = Principal(department="경영지원팀", clearance=3)


def test_등급이_충분하면_보인다():
    assert visible(1, (), 사원)


def test_등급이_모자라면_안_보인다():
    assert not visible(3, (), 사원)


def test_등급이_같으면_보인다():
    # 비교가 <= 여야 한다. < 로 쓰면 등급 3 임원이 등급 3 문서를 못 본다.
    assert visible(3, (), 임원)


def test_허용부서가_비면_전사_공개다():
    # 빈 튜플을 "아무도 못 본다"로 읽으면 그 문서는 조용히 사라진다.
    assert visible(1, (), 사원)
    assert visible(1, (), 팀장)


def test_허용부서에_들면_보인다():
    assert visible(1, ("개발팀",), 사원)


def test_허용부서에_없으면_등급이_높아도_안_보인다():
    # 두 조건은 AND 다. 등급이 부서를 덮어쓰면 임원이 모든 부서 문서를 본다.
    assert not visible(1, ("개발팀",), 임원)


def test_두_조건_중_하나만_모자라도_안_보인다():
    assert not visible(2, ("개발팀",), 사원)  # 등급도 부서도 모자람
    assert not visible(3, ("인사팀",), 팀장)  # 부서는 맞고 등급이 모자람
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_visibility.py -v`
Expected: 전부 FAIL — `ModuleNotFoundError: No module named 'core.access'`

- [ ] **Step 3: 가시성 규칙을 구현한다**

```bash
cd backend && mkdir -p core/access && touch core/access/__init__.py
```

`backend/core/access/visibility.py`:

```python
"""가시성 규칙 — 순수 함수.

adapters/db/chunk_search.py 의 _권한_WHERE 와 **같은 판정**을 내야 한다.
두 벌이 존재하는 이유: SQL 은 검색을 사전 필터링하고(존재를 감춘다),
이 함수는 이미 나온 결과를 재검증한다(spec 5.4). 재검증이 SQL 을 다시
부르면 그건 검증이 아니라 같은 코드를 두 번 믿는 것이다.

두 벌이 어긋나면 재검증이 무의미해지므로 tests/test_search_integration.py
가 실제 DB 로 둘을 대조한다.

Document 가 아니라 두 필드를 받는 이유: PolicyHit 도 Document 도 이 규칙을
쓰는데 둘은 다른 타입이다. 공통 조상을 만들면 한 번 쓰는 추상화가 된다.
"""

from core.types import Principal


def visible(required_clearance: int, allowed_departments: tuple[str, ...], p: Principal) -> bool:
    """이 주체에게 보이는가.

    허용부서가 비어 있으면 전사 공개다 — "아무도 못 본다"가 아니다.
    W1 실측: 빈 배열을 안 받아주면 그 문서는 자기 부서에도 안 보이고,
    에러가 아니라 조용한 누락이라 발견이 늦다.
    """
    return required_clearance <= p.clearance and (
        not allowed_departments or p.department in allowed_departments
    )
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_visibility.py -v`
Expected: 7개 PASS

- [ ] **Step 5: `PolicyHit` 에 권한 메타를 더한다**

`backend/core/types.py` 의 `PolicyHit` 를 아래로 바꾼다:

```python
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
```

- [ ] **Step 6: 기존 구성 지점 세 곳을 고친다**

`backend/adapters/db/chunk_search.py` 의 `load_hits` 에서 SELECT 절과 `PolicyHit` 구성을 바꾼다. SELECT 를:

```python
                SELECT c.id, c.text, d.title, cl.code,
                       d.required_clearance, d.allowed_departments
```

로 바꾸고, 구성부를:

```python
            by_id = {
                row[0]: PolicyHit(
                    chunk_id=row[0],
                    text=row[1],
                    doc_title=row[2],
                    clause_code=row[3],
                    required_clearance=row[4],
                    # NULL(전사 공개)은 빈 튜플로 정규화한다. core 쪽 규칙은
                    # 빈 튜플을 전사 공개로 읽으므로 여기서 맞춰준다.
                    allowed_departments=tuple(row[5] or ()),
                )
                for row in cur.fetchall()
            }
```

로 바꾼다.

`backend/tests/test_types.py` 의 두 구성 지점(53행·60행 부근)에 필드를 더한다:

```python
    h = PolicyHit(
        chunk_id=1, text="본문", doc_title="ISMS-P", clause_code="2.6.1",
        required_clearance=1, allowed_departments=(),
    )
```

```python
    h = PolicyHit(
        chunk_id=1, text="목차", doc_title="ISMS-P", clause_code=None,
        required_clearance=1, allowed_departments=(),
    )
```

- [ ] **Step 7: SQL 과 파이썬 규칙을 실제 DB 로 대조하는 테스트를 쓴다**

`backend/tests/test_search_integration.py` 끝에 더한다:

```python
def test_load_hits_가_권한_메타를_채운다(db):
    conn, searcher = db
    cid = _텍스트로_id(conn, "네트워크에 대한 비인가")
    hit = searcher.load_hits([cid], 사원)[0]
    assert hit.required_clearance == 1
    assert hit.allowed_departments == ()  # NULL 은 빈 튜플로 정규화된다


def test_SQL_필터와_파이썬_규칙이_같은_판정을_낸다(db):
    """권한 규칙이 두 벌 존재한다 — SQL 의 _권한_WHERE 와 core 의 visible.

    어긋나면 enforce 의 재검증이 무의미해진다. 실제 DB 의 모든 청크에 대해
    두 판정을 대조한다. 픽스처에는 등급 축(임원 전용)과 부서 축(인사팀 내규)이
    모두 들어 있다.
    """
    from core.access.visibility import visible

    conn, searcher = db
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM chunks ORDER BY id")
        전체 = [r[0] for r in cur.fetchall()]
    assert len(전체) >= 5, "픽스처가 비면 이 테스트는 공허하게 통과한다"

    for p in (
        Principal("개발팀", 1),
        Principal("인사팀", 1),
        Principal("인사팀", 2),
        Principal("경영지원팀", 3),
    ):
        # SQL 판정: load_hits 가 돌려준 것이 곧 "보인다"
        sql_보임 = {h.chunk_id for h in searcher.load_hits(전체, p)}

        # 파이썬 판정: 권한 메타를 등급 3 · 그 부서 주체로 전부 읽어와 계산한다
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, d.required_clearance, d.allowed_departments
                FROM chunks c JOIN documents d ON d.id = c.document_id
                """
            )
            파이썬_보임 = {
                cid for cid, cl, depts in cur.fetchall() if visible(cl, tuple(depts or ()), p)
            }

        assert sql_보임 == 파이썬_보임, f"{p} 에서 SQL 과 파이썬 판정이 다르다"
```

- [ ] **Step 8: 전부 돌린다**

```bash
cd backend
.venv/bin/python -m pytest -q
docker compose -f ../docker-compose.yml up -d
.venv/bin/python -m pytest -m db -v
```
Expected: 전부 PASS

- [ ] **Step 9: 변이 검사 — 두 벌이 어긋나면 정말 잡히는가**

통과하는 대조 테스트는 그 자체로 아무것도 증명하지 않는다. 일부러 어긋나게 만들고 실패를 본다.

`backend/core/access/visibility.py` 의 비교를 `required_clearance < p.clearance` 로 **일시적으로** 바꾼다.

Run: `cd backend && .venv/bin/python -m pytest -m db tests/test_search_integration.py::test_SQL_필터와_파이썬_규칙이_같은_판정을_낸다 -v`
Expected: **FAIL** — `Principal(department='개발팀', clearance=1) 에서 SQL 과 파이썬 판정이 다르다`

`tests/test_visibility.py::test_등급이_같으면_보인다` 도 함께 FAIL 해야 한다.

확인했으면 `<=` 로 되돌리고 다시 돌려 PASS 를 본다. **되돌리는 것을 잊으면 안 된다.**

- [ ] **Step 10: 린트하고 커밋한다**

```bash
cd backend
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format .
cd /Users/ryujun/Documents/secu-agent
git add backend/core/access/ backend/core/types.py backend/adapters/db/chunk_search.py \
        backend/tests/test_visibility.py backend/tests/test_types.py \
        backend/tests/test_search_integration.py
git commit -m "가시성 규칙을 core 에 두고 PolicyHit 에 권한 메타를 담았다

spec 5.4 의 enforce 가 도구 출력을 재검증하려면 판단 근거가 결과 안에 있어야
한다. PolicyHit 에 chunk_id·text·doc_title·clause_code 뿐이라 재검증이 구조적으로
불가능했다 — enforce 는 DB 를 다시 부르거나 전부 통과시키는 수밖에 없었다.

권한 규칙이 SQL 과 파이썬 두 벌이 되었으므로 어긋날 위험이 새로 생긴다.
실제 DB 의 모든 청크를 네 주체로 대조하는 테스트를 함께 넣었고, 비교를
일부러 < 로 바꿔 실패하는 것을 확인한 뒤 되돌렸다.

PolicyHit 의 새 필드에 기본값을 주지 않았다. 기본값이 있으면 새 호출자가
빠뜨려도 조용히 '등급 1 전사 공개'가 되고 enforce 가 통과시킨다."
```

---

### Task 4: 도구 출력 재검증 — `policy.enforce`

**Files:**
- Create: `backend/core/agent/__init__.py`, `backend/core/agent/policy.py`
- Test: `backend/tests/test_policy_enforce.py`

**Interfaces:**
- Consumes: `core.access.visibility.visible`, `core.types.PolicyHit` 의 권한 메타 (Task 3)
- Produces:
  - `core.agent.policy.AccessViolation` (Exception)
  - `core.agent.policy.enforce(hits: Sequence[PolicyHit], p: Principal) -> list[PolicyHit]`

W3 의 LangChain 런너는 도구가 돌려준 것을 **그대로** LLM 에 넘긴다. 권한 밖 항목이 섞여도 프레임워크는 막지 않는다. 도구가 W3 에 생기더라도 **검증 자체는 검색 결과에 대한 것**이므로 지금 만들고 지금 테스트한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_policy_enforce.py`:

```python
"""도구 출력 재검증.

정상 경로에서는 절대 발동하지 않는다 — 발동했다는 것은 사전 필터링이
깨졌다는 뜻이다. 그래서 조용히 걸러내지 않고 터진다(spec 5.4).
"""

import pytest

from core.agent.policy import AccessViolation, enforce
from core.types import PolicyHit, Principal

사원 = Principal(department="개발팀", clearance=1)


def _hit(chunk_id=1, clearance=1, depts=(), text="본문"):
    return PolicyHit(
        chunk_id=chunk_id,
        text=text,
        doc_title="문서",
        clause_code="2.6.1",
        required_clearance=clearance,
        allowed_departments=depts,
    )


def test_전부_권한_안이면_그대로_돌려준다():
    hits = [_hit(1), _hit(2)]
    assert enforce(hits, 사원) == hits


def test_빈_결과는_그대로_통과한다():
    # 볼 수 있는 문서가 없는 것과 규칙이 깨진 것은 다르다.
    assert enforce([], 사원) == []


def test_등급이_높은_항목이_섞이면_예외가_난다():
    with pytest.raises(AccessViolation):
        enforce([_hit(1), _hit(2, clearance=3)], 사원)


def test_타부서_항목이_섞이면_예외가_난다():
    with pytest.raises(AccessViolation):
        enforce([_hit(1, depts=("인사팀",))], 사원)


def test_조용히_걸러내지_않는다():
    """걸러내면 사후 필터링이 되고, 버그가 결과 개수 뒤에 숨는다."""
    with pytest.raises(AccessViolation):
        enforce([_hit(1), _hit(2, clearance=3)], 사원)


def test_예외_메시지가_본문을_담지_않는다():
    """메시지는 로그와 에러 응답을 타고 나간다.

    권한 밖 문서의 본문을 담으면 이 예외 자체가 내용 누출 경로가 된다 —
    막으려고 만든 장치가 통로가 된다.
    """
    비밀 = "임원 성과급은 영업이익의 100분의 3을 상한으로 한다"
    with pytest.raises(AccessViolation) as e:
        enforce([_hit(7, clearance=3, text=비밀)], 사원)
    메시지 = str(e.value)
    assert 비밀 not in 메시지
    assert "문서" not in 메시지  # doc_title 도 담지 않는다
    assert "7" in 메시지  # chunk_id 는 있어야 추적이 된다
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_policy_enforce.py -v`
Expected: 전부 FAIL — `ModuleNotFoundError: No module named 'core.agent'`

- [ ] **Step 3: 구현한다**

```bash
cd backend && mkdir -p core/agent && touch core/agent/__init__.py
```

`backend/core/agent/policy.py`:

```python
"""에이전트 실행 정책 — 도구 출력 검증.

LangChain 은 도구가 돌려준 것을 그대로 LLM 에 넘긴다. 권한 밖 문서가
도구 출력에 섞이면 프레임워크는 막지 않는다(spec 5.4).

이 모듈이 core/ 에 있는 것이 요점이다. adapters/agent/ 의 런너가 도구를
@tool 로 감쌀 때도 이 검증을 우회할 수 없다.
"""

from collections.abc import Sequence

from core.access.visibility import visible
from core.types import PolicyHit, Principal


class AccessViolation(Exception):
    """도구 출력에 권한 밖 항목이 있다. 사전 필터링이 깨졌다는 뜻이다."""


def enforce(hits: Sequence[PolicyHit], p: Principal) -> list[PolicyHit]:
    """권한 밖 항목이 있으면 예외를 던진다. 없으면 그대로 돌려준다.

    정상 경로에서는 절대 발동하지 않는다 — 발동했다는 것은 사전 필터링이
    깨졌다는 뜻이고, 조용히 걸러내면 그 사실이 묻힌다. 걸러내는 순간
    사후 필터링이 되고, 버그가 결과 개수 뒤에 숨는다.

    메시지에 chunk_id 만 담는다. 본문이나 문서 제목을 담으면 이 예외가
    로그와 에러 응답을 타고 나가면서 내용 누출 경로가 된다 — 막으려고
    만든 장치가 통로가 된다.
    """
    위반 = [h.chunk_id for h in hits if not visible(h.required_clearance, h.allowed_departments, p)]
    if 위반:
        raise AccessViolation(
            f"권한 밖 청크가 도구 출력에 섞였다: {위반} "
            f"(부서 {p.department} · 등급 {p.clearance}) — 사전 필터링이 깨졌다"
        )
    return list(hits)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_policy_enforce.py -v`
Expected: 6개 PASS

- [ ] **Step 5: 경계 테스트가 새 파일들을 집었는지 확인한다**

`tests/test_boundaries.py` 는 `core/**/*.py` 를 parametrize 한다. 새 파일이 목록에 나오는지 눈으로 본다.

Run: `cd backend && .venv/bin/python -m pytest tests/test_boundaries.py -v | grep -E "policy|visibility"`
Expected: `core/agent/policy.py` 와 `core/access/visibility.py` 가 각각 두 번씩(바깥 계층·인프라) 나오고 전부 PASS

- [ ] **Step 6: 린트하고 커밋한다**

```bash
cd backend
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format .
.venv/bin/python -m pytest -q
cd /Users/ryujun/Documents/secu-agent
git add backend/core/agent/ backend/tests/test_policy_enforce.py
git commit -m "도구 출력 재검증을 core 에 두었다

LangChain 은 도구가 돌려준 것을 그대로 LLM 에 넘긴다. 권한 밖 항목이 섞여도
프레임워크는 막지 않으므로 core 가 한 번 더 본다.

조용히 걸러내지 않고 예외를 던진다. 걸러내면 사후 필터링이 되고 버그가
결과 개수 뒤에 숨는다.

예외 메시지에 chunk_id 만 담는다. 본문이나 문서 제목을 담으면 이 예외가
로그를 타고 나가면서 내용 누출 경로가 된다 — 막으려고 만든 장치가 통로가
되는 것을 테스트로 막았다."
```

---

### Task 5: 누출 테스트 4종

**Files:**
- Create: `backend/tests/test_leakage.py`

**Interfaces:**
- Consumes: `_벡터_SQL` · `PgChunkSearch` (W1), `core.agent.policy.enforce` (Task 4), `PolicyHit` 권한 메타 (Task 3)
- Produces: 없음 (검사 전용)

이 주차의 핵심이다. spec 5.2 의 누출 경로 세 가지(개수·순위·타이밍)와 spec 5.4 의 출력 검증을 각각 검사한다.

**픽스처 규모가 판별력을 결정한다 — 실측으로 확인했다.**

`AS MATERIALIZED` 를 `AS NOT MATERIALIZED` 로 바꿔(= 사후 필터링) 등급 1 주체로 재봤다:

| 문서당 청크 | 총 청크 | 변이 시 질의 A 결과 | 판별하는가 |
|---|---|---|---|
| 300 | 600 | **10건** | ❌ 못 잡는다 |
| 2,000 | 4,000 | **0건** | ✅ 잡는다 |

600청크에서는 플래너가 인라인해도 순차 스캔으로 정확 검색을 해버려 결과가 같다. HNSW 의 `ef_search` 근사가 실제로 후보를 잘라내려면 규모가 필요하다. **문서당 2,000청크 아래로 줄이면 이 테스트는 고장난 구현에서도 통과한다.** `executemany` 로 4,000청크 적재에 3.9초가 걸렸고, 모듈 스코프 픽스처라 한 번만 낸다.

**기하는 좌표 블록으로 강제한다.** 난수 단위벡터 두 개를 뽑았더니 `cos=0.101` 이 나와 픽스처가 재려던 것을 못 쟀다. 앞 절반을 기밀 축, 뒤 절반을 공개 축으로 두면 내적이 구조적으로 정확히 0 이다.

- [ ] **Step 1: 픽스처와 테스트를 쓴다**

`backend/tests/test_leakage.py`:

```python
"""누출 테스트 — 사후 필터링이면 반드시 실패한다.

docker compose up -d
.venv/bin/python -m pytest -m db tests/test_leakage.py -v

**이 테스트들은 TRUNCATE 로 시작한다.** 돌리고 나면 개발용으로 적재해둔
ISMS-P 와 사내 규정이 사라진다. 평가 하네스를 돌리기 전에 다시 적재한다:

    .venv/bin/python -m pipeline.cli ingest ../data/raw/ismsp.pdf \
        --title "ISMS-P 인증기준 안내서"
    .venv/bin/python -m pipeline.cli ingest-dir ../data/policies
"""

import os
import random
import statistics
import time

import pytest

from adapters.db.chunk_search import _벡터_SQL, PgChunkSearch
from adapters.db.connection import apply_schema, connect
from core.agent.policy import AccessViolation, enforce
from core.types import EMBEDDING_DIM, Principal

pytestmark = pytest.mark.db

DSN = os.environ.get("SECUAGENT_DSN", "postgresql://secuagent:secuagent@localhost:5433/secuagent")

사원 = Principal(department="개발팀", clearance=1)
팀장 = Principal(department="개발팀", clearance=2)
임원 = Principal(department="개발팀", clearance=3)

# 문서당 청크 수. **2,000 아래로 줄이면 이 파일의 판별력이 사라진다.**
# 실측(pgvector:pg16): AS MATERIALIZED 를 NOT MATERIALIZED 로 바꿨을 때
# 문서당 300개(총 600)면 여전히 10건이 나오고, 2,000개(총 4,000)여야 0건이
# 된다. 600 규모에서는 플래너가 인라인해도 순차 스캔으로 정확 검색을 해서
# 근사 인덱스의 후보 절단이 일어나지 않는다.
문서당_청크 = 2000

절반 = EMBEDDING_DIM // 2

# 좌표 블록으로 직교를 강제한다. 난수 단위벡터로 하면 안 된다 —
# 실측: 384차원에서 난수 두 개의 cos 가 0.101 이 나왔고, "기밀 축 근처"로
# 심은 청크들이 무관해야 할 질의의 상위 10건 중 9건을 차지했다.
질의_기밀축 = [1.0] * 절반 + [0.0] * 절반
질의_공개축 = [0.0] * 절반 + [1.0] * 절반


def _벡터(앞쪽: bool, rng: random.Random) -> str:
    앞 = [1.0 + rng.uniform(0, 0.1) if 앞쪽 else 0.0 for _ in range(절반)]
    뒤 = [0.0 if 앞쪽 else 1.0 + rng.uniform(0, 0.1) for _ in range(절반)]
    return str(앞 + 뒤)


@pytest.fixture(scope="module")
def 코퍼스():
    """공개 2,000 + 기밀 2,000 청크. executemany 로 약 4초 걸린다."""
    conn = connect(DSN)
    apply_schema(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE documents RESTART IDENTITY CASCADE")

        def 문서(title, path, clearance, depts=None):
            cur.execute(
                "INSERT INTO documents (title, source_path, doc_type, "
                "required_clearance, allowed_departments) "
                "VALUES (%s, %s, 'md', %s, %s) RETURNING id",
                (title, path, clearance, depts),
            )
            return cur.fetchone()[0]

        공개 = 문서("공개 규정", "pub.md", 1)
        기밀 = 문서("임원 전용 규정", "sec.md", 3)
        타부서 = 문서("인사팀 내규", "hr.md", 1, ["인사팀"])

        rng = random.Random(7)
        삽입 = (
            "INSERT INTO chunks (document_id, clause_id, ordinal, text, embedding, text_tsv) "
            "VALUES (%s, NULL, %s, %s, %s, to_tsvector('simple', %s))"
        )
        for doc_id, 앞쪽, 이름 in ((기밀, True, "기밀"), (공개, False, "공개")):
            cur.executemany(
                삽입,
                [
                    (doc_id, i, f"{이름}조항 {i}", _벡터(앞쪽, rng), f"{이름}조항 {i}")
                    for i in range(문서당_청크)
                ],
            )
        # 부서 축을 가르는 소량. 등급은 사원과 같고 부서만 다르다.
        cur.executemany(
            삽입,
            [
                (타부서, i, f"인사조항 {i}", _벡터(True, rng), f"인사조항 {i}")
                for i in range(50)
            ],
        )
    conn.commit()
    yield conn, PgChunkSearch(conn)
    conn.close()


def _검색(searcher, q, principal, k=10):
    return searcher.by_vector(q, principal, k)


# ─────────────────────────── 누출 경로 ① 개수 ───────────────────────────


def test_결과_개수가_주체에_따라_달라지지_않는다(코퍼스):
    """사후 필터링이면 등급이 낮을수록 결과가 줄어든다."""
    _, searcher = 코퍼스
    개수 = [len(_검색(searcher, 질의_기밀축, p)) for p in (사원, 팀장, 임원)]
    assert 개수 == [10, 10, 10], f"등급별 결과 개수가 다르다: {개수}"


def test_결과_개수가_질의에_따라_달라지지_않는다(코퍼스):
    """**이 테스트가 사후 필터링을 잡는다.**

    고정 주체(등급 1)가 두 질의를 던진다. 하나는 자기가 못 보는 기밀 축을
    정확히 가리키고, 하나는 자기가 볼 수 있는 공개 축을 가리킨다.

    사후 필터링이면 기밀 축 질의의 상위 후보가 전부 걸러져 0건이 되고,
    그 0 이 "내가 못 보는 곳에 이 질의와 아주 가까운 문서가 있다"를
    알려준다. 실측: AS NOT MATERIALIZED 로 바꾸면 기밀축 0건 · 공개축 10건.
    """
    _, searcher = 코퍼스
    기밀축 = len(_검색(searcher, 질의_기밀축, 사원))
    공개축 = len(_검색(searcher, 질의_공개축, 사원))
    assert 기밀축 == 공개축 == 10, f"질의에 따라 개수가 갈린다: 기밀축 {기밀축} · 공개축 {공개축}"


# ─────────────────────────── 누출 경로 ② 순위 ───────────────────────────


def test_두_주체에게_모두_보이는_문서의_상대_순위가_같다(코퍼스):
    """등급 3 문서가 후보에 끼어들어도 공개 문서끼리의 상대 순위는 그대로여야 한다.

    흔들리면 "상위권에서 빠진 자리"가 보이고, 그 빈자리가 존재를 알린다.
    """
    _, searcher = 코퍼스
    사원_결과 = _검색(searcher, 질의_공개축, 사원, k=30)
    임원_결과 = _검색(searcher, 질의_공개축, 임원, k=30)

    공통 = set(사원_결과) & set(임원_결과)
    assert len(공통) >= 10, f"공통 문서가 너무 적어 순위를 비교할 수 없다: {len(공통)}"

    사원_순서 = [i for i in 사원_결과 if i in 공통]
    임원_순서 = [i for i in 임원_결과 if i in 공통]
    assert 사원_순서 == 임원_순서, "두 주체 모두에게 보이는 청크의 상대 순위가 다르다"


# ─────────────────────────── 누출 경로 ③ 타이밍 ───────────────────────────


def _계획(conn, sql, params) -> dict:
    with conn.cursor() as cur:
        cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + sql, params)
        return cur.fetchone()[0][0]


def _CTE_스캔_행수(plan: dict) -> int:
    찾은 = []

    def 훑기(node):
        if node.get("Node Type") == "CTE Scan":
            찾은.append(node["Actual Rows"])
        for ch in node.get("Plans", []):
            훑기(ch)

    훑기(plan["Plan"])
    assert 찾은, (
        "CTE Scan 노드가 없다 — 플래너가 CTE 를 인라인했다는 뜻이고, "
        "그 순간 권한 필터가 순위 뒤로 밀려 사후 필터링이 된다"
    )
    return 찾은[0]


def test_훑는_후보_집합이_질의와_무관하다(코퍼스):
    """타이밍 채널을 벽시계가 아니라 구조로 잰다.

    **벽시계로 재면 안 된다 — 실측으로 확인했다.** 사전/사후 두 구현의
    중앙값 비가 각각 1.17 과 1.21 로 사실상 같아, 어떤 임계를 골라도
    두 구현을 가르지 못한다. 통과하지만 아무것도 지키지 않는 테스트가 된다.

    타이밍이 새지 않는 진짜 근거는 "훑는 후보 집합이 주체에만 의존하고
    질의에는 의존하지 않는다"이다. EXPLAIN 이 그것을 결정론적으로 보여준다.
    실측: 등급 1 은 질의와 무관하게 2,000행, 등급 3 은 4,000행.
    """
    conn, _ = 코퍼스
    행수 = {}
    for 이름, q in (("기밀축", 질의_기밀축), ("공개축", 질의_공개축)):
        계획 = _계획(
            conn,
            _벡터_SQL,
            {"clearance": 사원.clearance, "dept": 사원.department, "qvec": str(q), "k": 10},
        )
        행수[이름] = _CTE_스캔_행수(계획)

    assert 행수["기밀축"] == 행수["공개축"], (
        f"질의에 따라 훑는 후보 수가 다르다: {행수} — 응답 시간이 질의에 따라 갈리고, "
        "그 차이가 숨겨진 문서의 존재를 알린다"
    )


def test_후보_집합이_주체의_권한_범위와_일치한다(코퍼스):
    """등급이 오르면 후보가 늘어나는 것은 누출이 아니다 — 주체는 남의 응답
    시간을 관측할 수 없다. 다만 그 수가 권한 범위와 정확히 맞아야 사전
    필터링이 실제로 걸렸다는 증거가 된다.

    실측: 등급 1 은 공개 2,000, 등급 3 은 공개 2,000 + 기밀 2,000 = 4,000.
    (부서 축 50개는 개발팀에게 안 보인다.)
    """
    conn, _ = 코퍼스
    def 행수(p):
        return _CTE_스캔_행수(
            _계획(
                conn,
                _벡터_SQL,
                {"clearance": p.clearance, "dept": p.department, "qvec": str(질의_기밀축), "k": 10},
            )
        )

    assert 행수(사원) == 문서당_청크
    assert 행수(임원) == 문서당_청크 * 2


@pytest.mark.slow
def test_응답시간이_질의에_따라_갈리지_않는다(코퍼스):
    """벽시계 보조 측정.

    **이 테스트만으로는 사후 필터링을 잡지 못한다** — 실측에서 고장난
    구현도 통과했다. 1급 근거는 위의 EXPLAIN 테스트다. 이것은 구조가
    맞는데도 시간이 크게 갈리는 예상 밖의 상황을 잡는 그물일 뿐이며,
    그래서 임계가 관대하다.
    """
    _, searcher = 코퍼스
    def 중앙값(q):
        ts = []
        for _ in range(30):
            t0 = time.perf_counter()
            _검색(searcher, q, 사원)
            ts.append(time.perf_counter() - t0)
        return statistics.median(ts)

    비 = 중앙값(질의_기밀축) / 중앙값(질의_공개축)
    assert 0.5 < 비 < 2.0, f"질의별 응답시간 비가 {비:.2f} 다"


# ─────────────────────── 누출 경로 ④ 도구 출력 ───────────────────────


def test_도구_출력에_권한_밖_항목이_있으면_예외가_난다(코퍼스):
    """enforce 가 조용히 걸러내지 않고 터지는지 실제 데이터로 확인한다."""
    conn, searcher = 코퍼스

    # 임원에게만 보이는 청크 하나를 골라 사원의 결과에 억지로 섞는다.
    임원_ids = _검색(searcher, 질의_기밀축, 임원)
    기밀_hits = searcher.load_hits(임원_ids, 임원)
    assert 기밀_hits, "임원 결과가 비면 이 테스트는 공허하다"
    기밀 = next(h for h in 기밀_hits if h.required_clearance == 3)

    사원_hits = searcher.load_hits(_검색(searcher, 질의_공개축, 사원), 사원)
    assert enforce(사원_hits, 사원) == 사원_hits  # 정상 경로는 통과한다

    with pytest.raises(AccessViolation):
        enforce([*사원_hits, 기밀], 사원)


def test_load_hits_는_권한_밖_id_를_조용히_뺀다(코퍼스):
    """예외를 던지면 안 된다 — "그 id 는 접근 불가"라는 응답 자체가 존재 확인이다."""
    _, searcher = 코퍼스
    임원_ids = _검색(searcher, 질의_기밀축, 임원)
    사원_결과 = searcher.load_hits(임원_ids, 사원)  # 예외가 나면 안 된다
    assert 사원_결과 == []
```

- [ ] **Step 2: `slow` 마커를 등록한다**

`backend/pyproject.toml` 의 `markers` 에 한 줄 더한다:

```toml
    "slow: 반복 측정처럼 느린 테스트 (기본 스위트에 포함, 필요하면 -m 'not slow')",
```

`addopts` 는 바꾸지 않는다 — `slow` 는 제외하지 않는다.

- [ ] **Step 3: 돌려서 통과를 확인한다**

```bash
docker compose up -d
cd backend && .venv/bin/python -m pytest -m db tests/test_leakage.py -v
```
Expected: 8개 PASS. 픽스처 적재에 4초 안팎이 걸린다.

- [ ] **Step 4: 변이 검사 — 사후 필터링으로 바꿔 실패를 본다**

**이 단계를 건너뛰면 이 파일 전체가 아무것도 증명하지 않는다.**

`backend/adapters/db/chunk_search.py` 의 `_벡터_SQL` 에서 `AS MATERIALIZED` 를 `AS NOT MATERIALIZED` 로 **일시적으로** 바꾼다.

> `AS MATERIALIZED` 를 그냥 지우면 안 된다. `WITH 허용 (` 가 되어 컬럼 별칭 목록으로 파싱되고 `syntax error at or near "SELECT"` 가 난다 — 테스트가 아니라 SQL 이 깨진다.

Run: `cd backend && .venv/bin/python -m pytest -m db tests/test_leakage.py -v`

Expected: 아래 넷이 FAIL 한다.
- `test_결과_개수가_질의에_따라_달라지지_않는다` — `질의에 따라 개수가 갈린다: 기밀축 0 · 공개축 10`
- `test_결과_개수가_주체에_따라_달라지지_않는다` — `[0, 0, 10]`
- `test_훑는_후보_집합이_질의와_무관하다` — `CTE Scan 노드가 없다 — 플래너가 CTE 를 인라인했다는 뜻이고…`
- `test_후보_집합이_주체의_권한_범위와_일치한다` — 같은 이유

> **실행 후 정정.** 이 목록은 처음에 앞의 셋만 적었고, 실제로 돌려보니 넷이 실패했다.
> `test_결과_개수가_주체에_따라_달라지지_않는다` 가 `[0, 0, 10]` 으로 함께 깨진다 — 기밀 축
> 질의의 근사 후보가 전부 기밀 청크라 등급 1·2 에게는 사후 필터 뒤에 아무것도 안 남기
> 때문이다. **개수 테스트가 질의 축과 등급 축 양쪽에서 사후 필터링을 잡는다**는 뜻이고,
> 예측보다 나은 결과다.

그리고 `tests/test_search_sql.py::test_MATERIALIZED_힌트가_있다` 도 FAIL 한다(DB 없이).

`test_응답시간이_질의에_따라_갈리지_않는다` 는 **PASS 한다.** 그것이 이 테스트를 1급 근거로 쓰지 않는 이유다 — 눈으로 확인한다.

- [ ] **Step 5: 되돌리고 다시 통과를 본다**

`AS MATERIALIZED` 로 되돌린다.

Run: `cd backend && .venv/bin/python -m pytest -m db -v`
Expected: 전부 PASS

- [ ] **Step 6: 개발용 코퍼스를 다시 적재한다**

누출 테스트가 TRUNCATE 했다. Task 6 의 평가 하네스가 실제 코퍼스를 필요로 한다.

```bash
cd backend
.venv/bin/python -m pipeline.cli ingest ../data/raw/ismsp.pdf --title "ISMS-P 인증기준 안내서"
.venv/bin/python -m pipeline.cli ingest-dir ../data/policies
```

- [ ] **Step 7: 린트하고 커밋한다**

```bash
cd backend
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format .
cd /Users/ryujun/Documents/secu-agent
git add backend/tests/test_leakage.py backend/pyproject.toml
git commit -m "누출 테스트 4종을 세웠다

개수·순위·타이밍·도구출력. 사후 필터링으로 바꾸면(AS NOT MATERIALIZED)
개수 테스트와 EXPLAIN 테스트 셋이 실패하는 것을 확인하고 되돌렸다.

타이밍은 벽시계로 재지 않는다. 실측에서 사전/사후 두 구현의 중앙값 비가
1.17 대 1.21 로 사실상 같아, 어떤 임계를 골라도 고장난 구현이 통과한다.
대신 EXPLAIN 의 CTE Scan Actual Rows 로 '훑는 후보 집합이 주체에만 의존하고
질의에는 의존하지 않는다'를 결정론적으로 검사한다. 벽시계 측정은 slow 마커를
달아 보조로만 남겼다.

픽스처를 문서당 2,000청크로 잡았다. 300청크에서는 변이가 재현되지 않는다 —
플래너가 인라인해도 순차 스캔으로 정확 검색을 해서 근사 인덱스의 후보 절단이
일어나지 않는다. 규모를 줄이면 이 파일은 고장난 구현에서도 통과한다.

벡터는 좌표 블록으로 직교를 강제했다. 난수 단위벡터로 뽑았더니 384차원에서
cos 가 0.101 이 나와, 무관해야 할 질의의 상위 10건 중 9건을 기밀 청크가
차지했다."
```

---

### Task 6: 평가 하네스

**Files:**
- Create: `backend/eval/data/golden.jsonl`, `backend/eval/golden.py`, `backend/eval/metrics.py`, `backend/eval/harness.py`, `backend/eval/run.py`
- Modify: `backend/core/ports.py` (`ChunkSearch` 에 `load_hits` 선언 — Step 8 참고)
- Test: `backend/tests/test_metrics.py`, `backend/tests/test_golden.py`

**Interfaces:**
- Consumes: `core.retrieve.hybrid.search`, `PgChunkSearch`, `E5Embedder`, `PolicyHit.clause_code`
- Produces:
  - `eval.metrics.recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float`
  - `eval.metrics.mrr_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float`
  - `eval.metrics.ndcg_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float`
  - `eval.golden.GoldenQuery` — `query · principal · relevant`
  - `eval.golden.load(path: Path) -> list[GoldenQuery]`
  - `eval.harness.evaluate(queries, embedder, searcher, k=10) -> EvalResult`
  - CLI: `python -m eval.run`

**RAGAS 를 쓰지 않는다.** RAGAS 의 Faithfulness 는 LLM 심판을 쓴다. 조항 코드의 실재는 문자열로 확정되므로 결정론적으로 잰다 — 개념은 차용하되 측정은 재현 가능하게(spec 8.1).

**지표 함수가 DB 를 모르는 것이 요점이다.** 지표가 조용히 틀리면 이후 모든 숫자가 거짓이 되므로 손계산 사례로 DB 없이 검증한다.

- [ ] **Step 1: 지표의 실패하는 테스트를 쓴다**

`backend/tests/test_metrics.py`:

```python
"""검색 지표 — 손으로 계산한 값과 대조한다.

지표가 조용히 틀리면 이후 모든 숫자가 거짓이 된다. 그래서 DB 도 모델도
없이, 답을 손으로 아는 사례로만 검증한다.
"""

import math

from eval.metrics import mrr_at_k, ndcg_at_k, recall_at_k


def test_recall_은_정답_중_찾은_비율이다():
    # 정답 2개 중 1개를 상위 10 안에서 찾았다.
    assert recall_at_k(["2.6.1", "2.5.1", "9.9.9"], {"2.6.1", "2.7.1"}, 10) == 0.5


def test_recall_은_k_밖을_세지_않는다():
    # 2.7.1 이 3위에 있지만 k=2 면 못 찾은 것이다.
    assert recall_at_k(["9.9.9", "8.8.8", "2.7.1"], {"2.7.1"}, 2) == 0.0


def test_recall_은_전부_찾으면_1이다():
    assert recall_at_k(["2.6.1", "2.7.1"], {"2.6.1", "2.7.1"}, 10) == 1.0


def test_정답이_없으면_recall_은_0이다():
    # 0으로 나누면 안 된다.
    assert recall_at_k(["2.6.1"], set(), 10) == 0.0


def test_mrr_은_첫_정답_순위의_역수다():
    assert mrr_at_k(["2.6.1", "9.9.9"], {"2.6.1"}, 10) == 1.0
    assert mrr_at_k(["9.9.9", "8.8.8", "2.6.1"], {"2.6.1"}, 10) == 1 / 3


def test_mrr_은_정답을_못_찾으면_0이다():
    assert mrr_at_k(["9.9.9"], {"2.6.1"}, 10) == 0.0


def test_ndcg_는_손계산과_맞는다():
    # 1위 정답, 2위 오답, 3위 정답.
    #   DCG  = 1/log2(2) + 0 + 1/log2(4) = 1 + 0.5 = 1.5
    #   IDCG = 1/log2(2) + 1/log2(3)     = 1 + 0.63093 = 1.63093
    #   nDCG = 1.5 / 1.63093 = 0.91972
    got = ndcg_at_k(["A", "X", "B"], {"A", "B"}, 10)
    assert math.isclose(got, 1.5 / (1 + 1 / math.log2(3)), rel_tol=1e-9)
    assert math.isclose(got, 0.91972, abs_tol=1e-5)


def test_ndcg_는_완벽하면_1이다():
    assert math.isclose(ndcg_at_k(["A", "B", "X"], {"A", "B"}, 10), 1.0)


def test_ndcg_는_하나도_못_찾으면_0이다():
    assert ndcg_at_k(["X", "Y"], {"A"}, 10) == 0.0


def test_중복_조항은_한_번만_센다():
    """한 조항에서 청크 여러 개가 뽑히면 같은 코드가 반복된다.

    중복을 그대로 세면 Recall 이 부풀고, 순위가 뒤로 밀린 정답이 앞에
    있는 것처럼 보인다. 처음 등장한 위치를 순위로 삼는다.
    """
    assert recall_at_k(["A", "A", "A", "B"], {"A", "B"}, 10) == 1.0
    # A 가 세 번 나와도 B 의 순위는 2위다 — 4위가 아니다.
    assert mrr_at_k(["A", "A", "A", "B"], {"B"}, 10) == 0.5
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_metrics.py -v`
Expected: 전부 FAIL — `ModuleNotFoundError: No module named 'eval.metrics'`

- [ ] **Step 3: 지표를 구현한다**

`backend/eval/metrics.py`:

```python
"""검색 지표 — 순수 함수. DB 도 모델도 모른다.

이진 관련도를 쓴다. 정답 조항이거나 아니거나 둘 중 하나이고, 등급을
매기려면 사람이 3단계 판정을 30건 x 10위 = 300번 해야 한다. 3~4주
일정에서 그 노동은 값을 하지 못한다.

**입력의 중복을 함수 안에서 제거한다.** 한 조항에서 청크가 여러 개
뽑히면 같은 코드가 반복되는데, 그대로 세면 Recall 이 부풀고 뒤에 있는
정답이 앞에 있는 것처럼 보인다. 호출자를 믿지 않고 여기서 정규화한다.
"""

import math
from collections.abc import Sequence


def _고유_상위(retrieved: Sequence[str], k: int) -> list[str]:
    """중복을 없애고 앞에서 k 개. 처음 등장한 위치가 순위다."""
    본_것: set[str] = set()
    출력: list[str] = []
    for code in retrieved:
        if code in 본_것:
            continue
        본_것.add(code)
        출력.append(code)
        if len(출력) == k:
            break
    return 출력


def recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """정답 조항 중 상위 k 안에서 찾은 비율."""
    if not relevant:
        return 0.0
    상위 = set(_고유_상위(retrieved, k))
    return len(상위 & relevant) / len(relevant)


def mrr_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """첫 정답 순위의 역수. 상위 k 안에 없으면 0."""
    for i, code in enumerate(_고유_상위(retrieved, k), start=1):
        if code in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """이진 관련도 nDCG. 이상적 순서(정답이 전부 앞에)로 정규화한다."""
    if not relevant:
        return 0.0
    상위 = _고유_상위(retrieved, k)
    dcg = sum(1.0 / math.log2(i + 1) for i, c in enumerate(상위, start=1) if c in relevant)
    이상적_개수 = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, 이상적_개수 + 1))
    return dcg / idcg if idcg else 0.0
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_metrics.py -v`
Expected: 10개 PASS

- [ ] **Step 5: 골든셋을 쓴다**

`backend/eval/data/golden.jsonl` — 한 줄에 한 건. **질의 문장이 조항 제목의 낱말을 그대로 쓰지 않는 것이 요점이다.** 제목을 베끼면 키워드 검색이 지나치게 잘 맞아 지표가 부풀고 회귀 감지력이 떨어진다.

```jsonl
{"query": "직원이 퇴사할 때 계정과 접근 권한을 어떻게 정리해야 하나", "department": "개발팀", "clearance": 1, "relevant": ["2.2.5"]}
{"query": "협력업체 직원에게 시스템 접근을 허용할 때 계약에 넣어야 할 것", "department": "개발팀", "clearance": 1, "relevant": ["2.3.2"]}
{"query": "서버실에 아무나 들어가지 못하게 하려면 어떻게 해야 하나", "department": "개발팀", "clearance": 1, "relevant": ["2.4.2"]}
{"query": "비밀번호를 몇 자리로 하고 얼마나 자주 바꾸게 해야 하나", "department": "개발팀", "clearance": 1, "relevant": ["2.5.4"]}
{"query": "관리자 권한을 가진 계정을 따로 관리해야 하는 이유", "department": "개발팀", "clearance": 1, "relevant": ["2.5.5"]}
{"query": "재택근무자가 사내망에 접속할 때 어떤 통제가 필요한가", "department": "개발팀", "clearance": 1, "relevant": ["2.6.6"]}
{"query": "사내 무선랜을 외부인이 쓰지 못하게 하려면", "department": "개발팀", "clearance": 1, "relevant": ["2.6.5"]}
{"query": "개인정보를 저장할 때 암호화를 어떤 기준으로 적용하나", "department": "개발팀", "clearance": 1, "relevant": ["2.7.1"]}
{"query": "암호키를 어디에 어떻게 보관해야 하나", "department": "개발팀", "clearance": 1, "relevant": ["2.7.2"]}
{"query": "개발 환경과 운영 환경을 나눠야 하는 이유", "department": "개발팀", "clearance": 1, "relevant": ["2.8.3"]}
{"query": "테스트에 실제 고객 자료를 그대로 써도 되나", "department": "개발팀", "clearance": 1, "relevant": ["2.8.4"]}
{"query": "소스코드에 대한 접근을 제한해야 하는 이유", "department": "개발팀", "clearance": 1, "relevant": ["2.8.5"]}
{"query": "시스템에 장애가 났을 때 어떻게 대응해야 하나", "department": "개발팀", "clearance": 1, "relevant": ["2.9.2"]}
{"query": "백업을 얼마나 자주 받고 어디에 보관해야 하나", "department": "개발팀", "clearance": 1, "relevant": ["2.9.3"]}
{"query": "접속기록을 얼마나 오래 보관해야 하나", "department": "개발팀", "clearance": 1, "relevant": ["2.9.4"]}
{"query": "쓰던 노트북을 버릴 때 안에 든 자료는 어떻게 하나", "department": "개발팀", "clearance": 1, "relevant": ["2.9.7"]}
{"query": "클라우드에 시스템을 올릴 때 확인해야 할 보안 사항", "department": "개발팀", "clearance": 1, "relevant": ["2.10.2"]}
{"query": "보안 패치를 언제까지 적용해야 하나", "department": "개발팀", "clearance": 1, "relevant": ["2.10.8"]}
{"query": "인증 실패가 반복되는 계정을 어떻게 찾아내나", "department": "개발팀", "clearance": 1, "relevant": ["2.11.3"]}
{"query": "침해사고가 났을 때 누구에게 먼저 알리고 무엇부터 하나", "department": "개발팀", "clearance": 1, "relevant": ["2.11.5"]}
{"query": "취약점 점검은 얼마나 자주 해야 하나", "department": "개발팀", "clearance": 1, "relevant": ["2.11.2"]}
{"query": "지진이나 화재에 대비해 무엇을 준비해야 하나", "department": "개발팀", "clearance": 1, "relevant": ["2.12.1"]}
{"query": "고객 정보를 마케팅에 활용하려면 무엇이 필요한가", "department": "개발팀", "clearance": 1, "relevant": ["3.1.7"]}
{"query": "주민등록번호를 받아도 되는 경우가 있나", "department": "개발팀", "clearance": 1, "relevant": ["3.1.3"]}
{"query": "개인정보를 해외 서버에 두어도 되나", "department": "개발팀", "clearance": 1, "relevant": ["3.3.4"]}
{"query": "임원 성과급은 어떤 기준으로 정해지나", "department": "경영지원팀", "clearance": 3, "relevant": ["6.1.1", "6.1.2"]}
{"query": "성과급을 지급한 뒤에 되돌려받을 수 있나", "department": "경영지원팀", "clearance": 3, "relevant": ["6.1.3"]}
{"query": "운영 서버에 접속하려면 어떤 승인을 받아야 하나", "department": "개발팀", "clearance": 1, "relevant": ["5.1.1"]}
{"query": "운영 서버 접속 기록은 얼마나 보관하나", "department": "개발팀", "clearance": 1, "relevant": ["5.1.3"]}
{"query": "보안 규정을 어긴 직원을 징계하는 절차", "department": "인사팀", "clearance": 2, "relevant": ["5.2.1"]}
```

**주체 배분의 근거:** 25건은 전사 공개 ISMS-P 라 등급 1 사원으로 던진다. 나머지 5건은 각각 등급 축(임원 2건)·부서 축(개발팀 2건)·두 축(인사팀 1건)을 탄다. 권한이 붙은 질의가 하나도 없으면 하네스가 `principal` 을 무시해도 지표가 똑같이 나온다.

- [ ] **Step 6: 골든셋 로더와 그 테스트를 쓴다**

`backend/tests/test_golden.py`:

```python
from eval.golden import DEFAULT_PATH, load


def test_골든셋이_서른_건이다():
    qs = load(DEFAULT_PATH)
    assert len(qs) == 30


def test_모든_질의가_정답_조항을_갖는다():
    # 정답이 빈 건이 있으면 그 건의 지표가 조용히 0 이 되어 평균을 끌어내린다.
    assert all(q.relevant for q in load(DEFAULT_PATH))


def test_질의가_조항_제목을_그대로_베끼지_않는다():
    """제목을 베끼면 키워드 검색이 지나치게 잘 맞아 지표가 부푼다."""
    베낀_제목 = {"네트워크 접근", "사용자 계정 관리", "이상행위 분석 및 모니터링"}
    for q in load(DEFAULT_PATH):
        assert q.query not in 베낀_제목


def test_권한이_필요한_질의가_섞여_있다():
    # 전부 전사 공개면 하네스가 principal 을 무시해도 지표가 같다.
    qs = load(DEFAULT_PATH)
    assert any(q.principal.clearance > 1 for q in qs)
    assert any(q.principal.department != "개발팀" for q in qs)
```

`backend/eval/golden.py`:

```python
"""골든셋 로더.

JSONL 인 이유: 한 줄에 한 건이라 diff 가 읽히고, 건을 더해도 기존 줄이
움직이지 않는다.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from core.types import Principal

DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "golden.jsonl"


@dataclass(frozen=True)
class GoldenQuery:
    query: str
    principal: Principal
    relevant: frozenset[str]


def load(path: Path = DEFAULT_PATH) -> list[GoldenQuery]:
    출력: list[GoldenQuery] = []
    for 줄 in path.read_text(encoding="utf-8").splitlines():
        줄 = 줄.strip()
        if not 줄:
            continue
        d = json.loads(줄)
        출력.append(
            GoldenQuery(
                query=d["query"],
                principal=Principal(department=d["department"], clearance=int(d["clearance"])),
                relevant=frozenset(d["relevant"]),
            )
        )
    return 출력
```

- [ ] **Step 7: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_golden.py -v`
Expected: 4개 PASS. 30건이 아니면 골든셋을 세어본다.

- [ ] **Step 8: 하네스를 구현한다**

`backend/eval/harness.py`:

```python
"""골든셋을 실제 검색에 물려 지표를 낸다.

권한 축을 반드시 태운다 — GoldenQuery 마다 다른 principal 로 검색한다.
전부 같은 주체로 돌리면 하네스가 principal 을 무시해도 지표가 같게 나온다.
"""

import statistics
import time
from collections.abc import Sequence
from dataclasses import dataclass

from core.ports import ChunkSearch, Embedder
from core.retrieve.hybrid import search
from eval.golden import GoldenQuery
from eval.metrics import mrr_at_k, ndcg_at_k, recall_at_k


@dataclass(frozen=True)
class QueryResult:
    query: str
    recall: float
    mrr: float
    ndcg: float
    latency_ms: float
    retrieved: tuple[str, ...]


@dataclass(frozen=True)
class EvalResult:
    k: int
    per_query: tuple[QueryResult, ...]

    @property
    def recall(self) -> float:
        return statistics.mean(r.recall for r in self.per_query)

    @property
    def mrr(self) -> float:
        return statistics.mean(r.mrr for r in self.per_query)

    @property
    def ndcg(self) -> float:
        return statistics.mean(r.ndcg for r in self.per_query)

    @property
    def p50(self) -> float:
        return statistics.median(r.latency_ms for r in self.per_query)

    @property
    def p95(self) -> float:
        정렬 = sorted(r.latency_ms for r in self.per_query)
        # 30건에서 p95 는 보간 없이 상위 5% 경계 원소를 쓴다 — 건수가 적어
        # 보간을 해도 정밀도가 늘지 않는다.
        return 정렬[min(len(정렬) - 1, int(len(정렬) * 0.95))]


def evaluate(
    queries: Sequence[GoldenQuery],
    embedder: Embedder,
    searcher: ChunkSearch,
    k: int = 10,
) -> EvalResult:
    결과: list[QueryResult] = []
    for q in queries:
        t0 = time.perf_counter()
        ids = search(q.query, q.principal, embedder, searcher, k=k)
        지연 = (time.perf_counter() - t0) * 1000

        hits = searcher.load_hits(ids, q.principal)
        # 조항 밖 청크(표지·목차)는 코드가 없다. 정답이 될 수 없으므로 뺀다.
        코드 = [h.clause_code for h in hits if h.clause_code]

        정답 = set(q.relevant)
        결과.append(
            QueryResult(
                query=q.query,
                recall=recall_at_k(코드, 정답, k),
                mrr=mrr_at_k(코드, 정답, k),
                ndcg=ndcg_at_k(코드, 정답, k),
                latency_ms=지연,
                retrieved=tuple(코드),
            )
        )
    return EvalResult(k=k, per_query=tuple(결과))
```

> `evaluate` 가 `searcher.load_hits` 를 부르므로 `ChunkSearch` Protocol 이 `load_hits` 를 선언하고 있어야 한다. W1 의 `core/ports.py` 에는 `by_vector` 와 `by_keyword` 만 있고 `load_hits` 가 빠져 있다. `core/ports.py` 의 `ChunkSearch` 에 더한다:
>
> ```python
>     def load_hits(self, ids: Sequence[int], principal: Principal) -> list[PolicyHit]:
>         """chunk id → PolicyHit. 권한 밖 id 는 조용히 빠진다.
>
>         principal 이 필수인 이유: 이 메서드는 본문을 돌려준다. 권한 검사를
>         검색 쪽에만 두면 id 를 아는 호출자가 이 경로로 본문을 가져간다.
>         """
>         ...
> ```
>
> `core/ports.py` 맨 위 import 에 `PolicyHit` 을 더한다:
> `from core.types import Chunk, Clause, Document, PolicyHit, Principal`

- [ ] **Step 9: 실행 진입점을 구현한다**

`backend/eval/run.py`:

```python
"""python -m eval.run — 골든셋을 돌려 마크다운 표를 낸다.

    .venv/bin/python -m eval.run
    .venv/bin/python -m eval.run --per-query   # 건별 상세
"""

import argparse
import sys
from pathlib import Path

from adapters.db.chunk_search import PgChunkSearch
from adapters.db.connection import connect
from adapters.embedding.e5 import E5Embedder
from eval.golden import DEFAULT_PATH, load
from eval.harness import evaluate


def main() -> int:
    ap = argparse.ArgumentParser(description="검색 품질 평가")
    ap.add_argument("--golden", default=str(DEFAULT_PATH))
    ap.add_argument("-k", type=int, default=10)
    ap.add_argument("--per-query", action="store_true")
    ap.add_argument("--dsn", default=None)
    args = ap.parse_args()

    queries = load(Path(args.golden))
    conn = connect(args.dsn)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM chunks")
        총청크 = cur.fetchone()[0]
    if 총청크 == 0:
        print("코퍼스가 비어 있다. 먼저 적재한다:", file=sys.stderr)
        print("  python -m pipeline.cli ingest ../data/raw/ismsp.pdf "
              '--title "ISMS-P 인증기준 안내서"', file=sys.stderr)
        print("  python -m pipeline.cli ingest-dir ../data/policies", file=sys.stderr)
        return 1

    r = evaluate(queries, E5Embedder(), PgChunkSearch(conn), k=args.k)
    conn.close()

    print(f"\n## 검색 품질 (골든셋 {len(queries)}건 · k={r.k} · 코퍼스 {총청크}청크)\n")
    print("| 지표 | 값 |")
    print("|---|---|")
    print(f"| Recall@{r.k} | {r.recall:.3f} |")
    print(f"| MRR@{r.k} | {r.mrr:.3f} |")
    print(f"| nDCG@{r.k} | {r.ndcg:.3f} |")
    print(f"| 지연 p50 | {r.p50:.0f}ms |")
    print(f"| 지연 p95 | {r.p95:.0f}ms |")

    if args.per_query:
        print("\n### 건별\n")
        print("| 질의 | Recall | MRR | nDCG |")
        print("|---|---|---|---|")
        for q in sorted(r.per_query, key=lambda x: x.recall):
            print(f"| {q.query} | {q.recall:.2f} | {q.mrr:.2f} | {q.ndcg:.2f} |")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 10: 실제로 돌린다**

```bash
docker compose up -d
cd backend
# 누출 테스트가 TRUNCATE 했을 수 있다. 적재 상태를 먼저 확인한다.
.venv/bin/python -m eval.run --per-query
```

Expected: 표가 나온다. **숫자 자체에 합격선을 두지 않는다** — 이번 주의 목표는 "잴 수 있게 되는 것"이고, 기준선은 이 실행의 결과가 된다.

**Recall 이 0.3 아래로 나오면 멈추고 원인을 본다.** `--per-query` 로 0.00 인 건을 보고, 그 질의를 `python -m pipeline.cli search "<질의>"` 로 직접 던져 무엇이 올라오는지 확인한다. 흔한 원인 두 가지: 골든셋의 정답 조항이 틀렸거나, 임베더가 `query:` 접두어를 안 붙이고 있거나.

- [ ] **Step 11: 결과를 README 에 기록한다**

`README.md` 의 `## 개발` 절 **위**에 절을 더한다. `<>` 안의 숫자는 Step 10 의 실제 출력으로 채운다.

````markdown
## 검색 품질

골든셋 30건(ISMS-P 25 · 사내 규정 5), k=10, 코퍼스 <N>청크 기준.

| 지표 | 값 |
|---|---|
| Recall@10 | <값> |
| MRR@10 | <값> |
| nDCG@10 | <값> |
| 지연 p50 / p95 | <값> / <값> |

```bash
cd backend && .venv/bin/python -m eval.run --per-query
```

Faithfulness 는 LLM 심판이 아니라 조항 코드의 실재 여부로 잽니다 — W3 에서 붙입니다.
````

- [ ] **Step 12: 린트하고 커밋한다**

```bash
cd backend
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format .
.venv/bin/python -m pytest -q
cd /Users/ryujun/Documents/secu-agent
git add backend/eval/ backend/core/ports.py backend/tests/test_metrics.py \
        backend/tests/test_golden.py README.md
git commit -m "평가 하네스를 세웠다

골든셋 30건에 Recall@10 · MRR@10 · nDCG@10 과 지연 p50/p95 를 낸다.

지표 함수는 DB 도 모델도 모른다. 조용히 틀리면 이후 모든 숫자가 거짓이
되므로 답을 손으로 아는 사례로만 검증한다.

중복 조항을 함수 안에서 제거한다. 한 조항에서 청크가 여러 개 뽑히면 같은
코드가 반복되는데, 그대로 세면 Recall 이 부풀고 뒤에 있는 정답이 앞에 있는
것처럼 보인다.

골든셋 30건 중 5건에 권한을 태웠다. 전부 전사 공개면 하네스가 principal 을
무시해도 지표가 같게 나온다.

ChunkSearch 포트에 load_hits 가 빠져 있던 것을 더했다 — 구현에는 있는데
Protocol 에 없어서 하네스가 포트만 보고는 부를 수 없었다.

RAGAS 를 쓰지 않는다. RAGAS 의 Faithfulness 는 LLM 심판을 쓰지만 조항 코드의
실재는 문자열로 확정된다."
```

---

### Task 7: 시연 계정과 검증 기록

**Files:**
- Create: `data/principals.json`
- Modify: `backend/pipeline/cli.py` (`seed-principals` · `demo`)
- Modify: `jekyll/verification.markdown`
- Test: `backend/tests/test_db_integration.py`

**Interfaces:**
- Consumes: 앞의 모든 태스크
- Produces: CLI `python -m pipeline.cli seed-principals` · `python -m pipeline.cli demo "<질의>"`

**"같은 질문을 세 계정으로 던지면 결과가 달라진다"가 이 프로젝트에서 가장 강한 한 장면이다**(spec 9). W3 의 UI 가 그것을 화면에 그리지만, 그 전에 CLI 로 성립하는지 확인한다. 화면을 만든 뒤에 데이터가 안 갈린다는 것을 알면 늦다.

- [ ] **Step 1: 시연 계정을 정의한다**

`data/principals.json`:

```json
[
  {"name": "김개발", "department": "개발팀",     "clearance": 1},
  {"name": "박인사", "department": "인사팀",     "clearance": 2},
  {"name": "최임원", "department": "경영지원팀", "clearance": 3}
]
```

이 셋이 코퍼스의 세 축을 각각 다르게 통과한다.

| 계정 | 03 개발팀 서버접근 (등급1·개발팀) | 05 인사팀 징계 (등급2·인사팀) | 07 임원 성과급 (등급3·전사) |
|---|---|---|---|
| 김개발 (개발팀·1) | 보임 | 안 보임 | 안 보임 |
| 박인사 (인사팀·2) | 안 보임 | 보임 | 안 보임 |
| 최임원 (경영지원팀·3) | 안 보임 | 안 보임 | 보임 |

세 계정이 서로 다른 것을 보고, **어느 계정도 전부 보지 못한다.** 등급 3 이 모든 것을 보면 부서 축이 시연에서 사라진다.

- [ ] **Step 2: 시드 명령과 시연 명령을 더한다**

`backend/pipeline/cli.py` 의 서브파서 정의부에 더한다:

```python
    sub.add_parser("seed-principals", help="시연 계정을 넣는다")

    dem = sub.add_parser("demo", help="같은 질의를 세 계정으로 던진다")
    dem.add_argument("query")
    dem.add_argument("-k", type=int, default=5)
    dem.add_argument("--dsn", default=None)
```

`seed-principals` 는 `--dsn` 을 받지 않는다 — 환경변수로 충분하고 인자를 늘릴 이유가 없다.

`if args.cmd == "search":` 블록 아래에 더한다:

```python
    if args.cmd == "seed-principals":
        import json

        경로 = Path(__file__).resolve().parents[2] / "data" / "principals.json"
        계정들 = json.loads(경로.read_text(encoding="utf-8"))

        conn = connect(None)
        apply_schema(conn)
        with conn.cursor() as cur:
            for p in 계정들:
                cur.execute(
                    """
                    INSERT INTO principals (name, department, clearance)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        department = EXCLUDED.department,
                        clearance = EXCLUDED.clearance
                    """,
                    (p["name"], p["department"], p["clearance"]),
                )
        conn.commit()
        for p in 계정들:
            print(f"  {p['name']} · {p['department']} · 등급 {p['clearance']}")
        conn.close()

    if args.cmd == "demo":
        from adapters.db.chunk_search import PgChunkSearch
        from core.retrieve.hybrid import search as hybrid_search
        from core.types import Principal

        conn = connect(args.dsn)
        searcher = PgChunkSearch(conn)
        embedder = E5Embedder()  # 세 계정이 모델을 공유한다

        with conn.cursor() as cur:
            cur.execute("SELECT name, department, clearance FROM principals ORDER BY clearance")
            계정들 = cur.fetchall()
        if not 계정들:
            print("시연 계정이 없다. 먼저: python -m pipeline.cli seed-principals",
                  file=sys.stderr)
            return 1

        print(f'질의: "{args.query}"\n')
        for 이름, 부서, 등급 in 계정들:
            principal = Principal(department=부서, clearance=등급)
            ids = hybrid_search(args.query, principal, embedder, searcher, k=args.k)
            rows = searcher.load_hits(ids, principal)
            print(f"── {이름} ({부서} · 등급 {등급}) — {len(rows)}건")
            for i, hit in enumerate(rows, start=1):
                표시 = f"[{hit.clause_code}]" if hit.clause_code else "[조항 밖]"
                print(f"   {i}. {표시} {hit.doc_title}")
            print()
        conn.close()
```

- [ ] **Step 3: `principals` 시드의 멱등성을 테스트한다**

`backend/tests/test_db_integration.py` 끝에 더한다:

```python
def test_같은_이름의_계정을_두_번_넣으면_갱신된다(store):
    """시연 계정 시드를 여러 번 돌려도 행이 늘면 안 된다.

    principals.name 에 UNIQUE 가 걸려 있어 ON CONFLICT 가 동작해야 한다.
    """
    with store.conn.cursor() as cur:
        for 등급 in (1, 3):
            cur.execute(
                "INSERT INTO principals (name, department, clearance) VALUES (%s, %s, %s) "
                "ON CONFLICT (name) DO UPDATE SET clearance = EXCLUDED.clearance",
                ("김개발", "개발팀", 등급),
            )
        cur.execute("SELECT count(*), max(clearance) FROM principals WHERE name = '김개발'")
        개수, 등급 = cur.fetchone()
    store.conn.commit()
    assert (개수, 등급) == (1, 3)
```

- [ ] **Step 4: 시연을 실제로 돌린다**

```bash
docker compose up -d
cd backend
.venv/bin/python -m pipeline.cli seed-principals
.venv/bin/python -m pipeline.cli demo "임원 성과급은 어떤 기준으로 정해지나"
.venv/bin/python -m pipeline.cli demo "운영 서버에 접속하려면 어떤 승인이 필요한가"
```

Expected:
- 첫 질의에서 **최임원에게만** `[6.1.1]`·`[6.1.2]` 가 뜬다. 김개발·박인사는 같은 개수(k=5)의 다른 결과를 받는다.
- 둘째 질의에서 **김개발에게만** `[5.1.1]` 이 뜬다.
- **세 계정의 결과 개수가 전부 같아야 한다.** 하나라도 적으면 사전 필터링이 깨진 것이다 — 멈추고 Task 5 의 누출 테스트를 돌린다.

이 두 출력을 그대로 복사해 둔다. Step 5 가 쓴다.

- [ ] **Step 5: 검증 페이지에 W2 기록을 남긴다**

`jekyll/verification.markdown` 의 `### Access Control 누출 테스트` 절을 아래로 바꾼다. 앞부분(사전/사후 비교 블록)은 그대로 두고, 테스트 목록 아래에 이어 붙인다.

````markdown
네 가지 누출 경로를 각각 테스트합니다.

```python
def test_결과_개수가_주체에_따라_달라지지_않는다()        # 개수 — 등급 축
def test_결과_개수가_질의에_따라_달라지지_않는다()        # 개수 — 질의 축
def test_두_주체에게_모두_보이는_문서의_상대_순위가_같다()  # 순위
def test_훑는_후보_집합이_질의와_무관하다()               # 타이밍
def test_도구_출력에_권한_밖_항목이_있으면_예외가_난다()    # 도구 출력
```

#### 장치가 잡은 것 ①: 벽시계 타이밍 테스트는 아무것도 지키지 않았다

설계 문서는 타이밍 누출을 `test_응답시간_차이가_유의하지_않다` 로 잡는다고 적었습니다. 구현 전에 실제로 재봤습니다 — 사전 필터링과 **일부러 고장낸** 사후 필터링을, 등급 1 주체가 질의 두 종(기밀 축 · 공개 축)으로 각 30회씩.

| | 결과 개수 (기밀축 / 공개축) | 벽시계 중앙값 비 |
|---|---|---|
| 사전 필터링 | 10건 / 10건 | 1.17 |
| **사후 필터링 (고장난 구현)** | **0건 / 10건** | **1.21** |

시간 비율이 사실상 같습니다. **어떤 임계를 골라도 고장난 구현이 통과합니다.** 통과하지만 아무것도 지키지 않는 테스트를, 쓰기 전에 버렸습니다.

대신 `EXPLAIN (ANALYZE, FORMAT JSON)` 으로 **훑는 후보 집합의 크기**를 봅니다. 타이밍이 새지 않는 진짜 근거는 "후보 집합이 주체에만 의존하고 질의에는 의존하지 않는다"이고, 이건 결정론적으로 확인됩니다 — 등급 1 은 질의와 무관하게 2,000행, 등급 3 은 4,000행.

#### 장치가 잡은 것 ②: 픽스처가 작으면 테스트가 거짓말을 한다

같은 누출 테스트를 픽스처 규모만 바꿔 돌렸습니다.

| 문서당 청크 | 고장난 구현에서 기밀축 질의 결과 | 테스트가 |
|---|---|---|
| 300 | 10건 | **통과합니다** ← 거짓 |
| 2,000 | 0건 | 실패합니다 ← 정상 |

600청크 규모에서는 플래너가 CTE 를 인라인해도 순차 스캔으로 정확 검색을 해버려, 근사 인덱스의 후보 절단이 아예 일어나지 않습니다. **테스트 코드가 옳아도 데이터가 작으면 아무것도 증명하지 못합니다.**

#### 장치가 잡은 것 ③: 난수 픽스처는 기하가 통제되지 않는다

"기밀 문서 근처"와 "무관한" 질의 벡터를 384차원 난수 단위벡터로 뽑았더니 `cos = 0.101` 이 나왔고, 기밀 청크가 **무관해야 할 질의**의 상위 10건 중 9건을 차지했습니다. 픽스처가 재려던 것을 재지 못하는 상태였습니다. 좌표 블록을 앞뒤로 갈라 내적이 구조적으로 0 이 되게 고쳤습니다.

#### 장치가 잡은 것 ④: 재검증이 구조적으로 불가능했다

설계 문서는 `enforce(hits, principal)` 이 도구 출력을 재검증한다고 적었습니다. 그런데 `PolicyHit` 에는 `chunk_id · text · doc_title · clause_code` 뿐이라 **판단할 근거가 결과 안에 없었습니다.** `enforce` 가 할 수 있는 일은 DB 를 다시 부르거나(그건 재검증이 아니라 같은 코드를 두 번 믿는 것) 전부 통과시키는 것뿐이었습니다. 권한 메타를 결과에 담도록 타입을 고쳤습니다.
````

그리고 같은 파일의 **갖춘 장치** 표에서 `평가 하네스` 행의 "언제 도는가" 를 `수동 (python -m eval.run)` 으로 바꾼다.

- [ ] **Step 6: 시연 결과를 README 에 넣는다**

`README.md` 의 `## 검색 품질` 절 **위**에 더한다. `<...>` 는 Step 4 의 실제 출력으로 채운다.

````markdown
## 권한에 따라 결과가 달라진다

같은 질문을 세 계정으로 던집니다.

```
$ python -m pipeline.cli demo "임원 성과급은 어떤 기준으로 정해지나"

<Step 4 의 실제 출력>
```

**세 계정의 결과 개수가 같습니다.** 최임원만 `6.1.1` 을 받고, 나머지 둘은 다른 문서로 채워진 같은 개수의 결과를 받습니다 — 숨겨진 문서가 있다는 신호가 개수에도 순위에도 남지 않습니다.

시연 계정과 사내 규정 문서는 합성입니다. ISMS-P 안내서는 본문이 실제 공개 표준이고 권한 등급만 부여했습니다.
````

- [ ] **Step 7: 전부 돌리고 커밋한다**

```bash
cd backend
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format .
.venv/bin/python -m pytest -q
docker compose -f ../docker-compose.yml up -d
.venv/bin/python -m pytest -m db -v
# 누출 테스트가 TRUNCATE 했으므로 다시 적재하고 시연이 여전히 도는지 본다
.venv/bin/python -m pipeline.cli ingest ../data/raw/ismsp.pdf --title "ISMS-P 인증기준 안내서"
.venv/bin/python -m pipeline.cli ingest-dir ../data/policies
.venv/bin/python -m pipeline.cli seed-principals
.venv/bin/python -m pipeline.cli demo "임원 성과급은 어떤 기준으로 정해지나"
cd /Users/ryujun/Documents/secu-agent
git add data/principals.json backend/pipeline/cli.py \
        backend/tests/test_db_integration.py jekyll/verification.markdown README.md
git commit -m "시연 계정 세 개와 검증 기록을 더했다

같은 질문을 세 계정으로 던지면 결과가 달라지는 것을 CLI 로 먼저 확인한다.
화면을 만든 뒤에 데이터가 안 갈린다는 것을 알면 늦다.

세 계정이 서로 다른 것을 보고 어느 계정도 전부 보지는 못한다. 등급 3 이
모든 것을 보면 부서 축이 시연에서 사라진다.

검증 페이지에 이번 주 장치가 잡은 네 가지를 적었다 — 벽시계 타이밍 테스트가
고장난 구현을 통과시킨 것, 작은 픽스처가 테스트를 거짓말하게 만든 것, 난수
벡터의 기하가 통제되지 않은 것, PolicyHit 에 근거가 없어 재검증이 구조적으로
불가능했던 것."
```

---

## 완료 조건

- [ ] `.venv/bin/python -m pytest -q` 가 DB 없이 전부 통과한다
- [ ] `docker compose up -d && .venv/bin/python -m pytest -m db -v` 가 전부 통과한다
- [ ] `.venv/bin/python -m pytest -m model -v` 가 전부 통과한다
- [ ] `ruff check .` · `ruff format --check .` 가 exit 0 이다
- [ ] `tests/test_leakage.py` 가 **실제로 사후 필터링을 잡는다** — `AS MATERIALIZED` 를 `AS NOT MATERIALIZED` 로 바꿔 세 테스트가 실패하는 것을 보고 되돌렸다
- [ ] `tests/test_visibility.py` 와 SQL 대조 테스트가 **실제로 어긋남을 잡는다** — 비교를 `<` 로 바꿔 실패를 보고 되돌렸다
- [ ] `ingest-dir` 로 사내 규정 8개가 적재되고, 두 번 돌려도 `DB 총 청크` 가 같다
- [ ] `python -m eval.run` 이 Recall@10 · MRR@10 · nDCG@10 · p50 · p95 를 낸다
- [ ] `python -m pipeline.cli demo "임원 성과급은 어떤 기준으로 정해지나"` 에서 **세 계정의 결과 개수가 같고**, 최임원에게만 `6.1.1` 이 뜬다
- [ ] `README.md` 에 실제 측정값이 들어갔다 (`<값>` 자리표시자가 남아 있지 않다)
- [ ] `jekyll/verification.markdown` 에 W2 가 잡은 네 가지가 기록됐다

**주의: `-m db` 테스트는 코퍼스를 TRUNCATE 한다.** 완료 조건을 확인하는 순서는 `pytest -m db` → 재적재 → `eval.run` → `demo` 다.

## 다음 계획으로 넘길 것

- **에이전트와 도구 3개** (W3) — `search_policy` · `query_logs` · `draft_report`. `enforce` 와 `visible` 이 준비돼 있다
- **인용 실재 검증** (`verify_clauses`, W3) — 검증할 리포트가 있어야 만들 수 있다. `clauses` 테이블의 코드 집합이 정답이다
- **API 와 UI, 배포** (W3) — `demo` 명령이 보여주는 장면을 화면으로 옮긴다
- **로그 파이프라인과 리포트** (W4) — `log_events` 스키마는 이미 있다. 부서별 허용 호스트 매핑이 아직 없다
- **DOCX 파서** — `loader.load` 가 `.pdf`·`.md` 만 받는다. 요구가 생기면 그때 더한다
- **골든셋 확장** — 30건은 Recall@10 을 읽을 수 있는 최소 규모다. 회귀 감지력을 높이려면 60건이 낫다
- **코퍼스가 커질 때의 벡터 인덱스** — `AS MATERIALIZED` 는 HNSW 를 포기한다. 10만 청크를 넘으면 권한 컬럼을 `chunks` 로 비정규화하고 부분 인덱스를 검토한다. 근사 인덱스 위의 사후 필터링으로 돌아가서는 안 된다

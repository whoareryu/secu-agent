# W3 구현 계획 — 에이전트 · API · UI · 배포

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 권한이 반영된 규정 검색을 도구로 쓰는 에이전트를 세우고, 구글 로그인 뒤에서 그것을 쓰는 한 페이지를 배포된 URL 로 올린다.

**Architecture:** 도구의 실제 로직은 `core/agent/tools.py` 에 순수 파이썬으로 있고 LangChain 을 모른다. `adapters/agent/runner.py` 가 그것을 `@tool` 로 감싸되 **`principal` 을 도구 스키마에서 뺀다** — 런타임 컨텍스트로 주입한다. FastAPI 가 얇은 HTTP 계층이고, Next.js 가 BFF 로서 브라우저와 백엔드 사이에 선다. 백엔드는 Cloudflare Container, DB 는 Neon, 프론트는 Vercel.

**Tech Stack:** Python 3.12, langchain 1.3, langgraph 1.2, langchain-google-genai 4.3, FastAPI, uvicorn, Next.js(App Router), Auth.js, Docker, Wrangler 4

**Spec:** `docs/superpowers/specs/2026-09-01-w3-deployment-design.md` (배포·인증·API·UI)
**상위 Spec:** `docs/superpowers/specs/2026-08-31-secu-agent-design.md` (도메인·검색·권한)

**선행:** W1 `2026-08-31-w1-document-pipeline.md` · W2 `2026-09-01-w2-access-control.md` (둘 다 완료, main 병합됨)

## Global Constraints

- Python 3.12 이상. 가상환경은 `backend/.venv`, 실행은 `.venv/bin/python`, 작업 디렉토리는 `backend/`.
- **`core/` 는 바깥 계층(`adapters`·`api`·`pipeline`·`eval`)을 import 하지 않는다.**
- **`core/` 는 인프라·프레임워크(`psycopg`·`sqlalchemy`·`langchain_google_genai`·`google`·`fastapi`·`langchain`·`langgraph`·`sentence_transformers`·`torch`·`transformers`·`pypdf`·`yaml`)를 import 하지 않는다.** `backend/tests/test_boundaries.py` 가 강제한다.
- 경계 인터페이스는 `core/ports.py` 가 소유한다. `adapters/` 가 구현한다.
- 임베딩 차원은 `core/types.EMBEDDING_DIM`(384)이 단일 출처다. 모델은 `intfloat/multilingual-e5-small`.
- e5 는 `query:` / `passage:` 접두어를 요구한다.
- 생성 모델은 `gemini-3.7-flash` 다. 모델 ID 에 날짜 접미사를 붙이지 않는다.
- 테스트 함수 이름은 한국어로 쓴다.
- 커밋 메시지는 한국어, 평서형(`~했다`).
- 마커: `db`(DB 필요) · `model`(임베딩 모델 로드) · `llm`(실제 LLM 호출) 은 기본 스위트에서 제외된다.
- **`pytest -m db` 는 적재된 코퍼스를 파괴한다.** 모든 DB 픽스처가 `TRUNCATE documents RESTART IDENTITY CASCADE` 로 시작한다. 돌린 뒤에는 재적재한다.

---

## 계획을 쓰기 전에 실물로 확인한 것

상위 spec §10 이 "LangChain 1.x API 를 기억으로 쓰면 막힌다"를 최상위 리스크로 지목했으므로 임시 환경(`langchain 1.3.18` · `langgraph 1.2.11` · `langchain-google-genai 4.3.7`)에 설치해 직접 읽었다. **여섯 개가 계획을 바꿨다.**

**① `create_react_agent` 는 deprecated 다.** `from langchain.agents import create_agent` 이 현재 API 다. 실제 파라미터: `model` · `tools` · `system_prompt` · `middleware` · `response_format` · `state_schema` · `context_schema` · `checkpointer` · `store` · `interrupt_before` · `interrupt_after` · `debug` · `name` · `cache` · `transformers`.

**② `recursion_limit` 인자가 없다.** 도구 호출 상한은 `ToolCallLimitMiddleware(*, tool_name=None, thread_limit=None, run_limit=None, exit_behavior='continue')` 다. `exit_behavior` 세 값 중 상위 spec §7.2 의 "중단하고 그때까지의 결과로 답한다"에 맞는 것은 `continue` 뿐이다 — `error` 는 예외를 던지고, `end` 는 *왜 멈췄는지*를 답한다.

**③ `principal` 은 `ToolRuntime` 으로 뺀다.** 도구 함수가 `runtime: ToolRuntime[AgentContext]` 를 받으면 그 인자는 모델이 보는 스키마에서 사라진다. 실측:

```
tool_call_schema properties → ['k', 'query']      ← principal 없음
```

**④ 보안 테스트는 `tool_call_schema` 를 봐야 한다. `args_schema` 를 보면 안 된다.** `args_schema` 에는 `runtime` 이 남아 있고, `args_schema.model_json_schema()` 를 호출하면 **`PydanticInvalidForJsonSchema` 예외가 난다** — `ToolRuntime` 이 `stream_writer` 라는 callable 필드를 갖기 때문이다. 실수로 이걸 검사하면 테스트가 엉뚱하게 깨진다.

**⑤ 컨텍스트 주입은 컴파일된 그래프를 거쳐야만 된다.** `tool.invoke(..., context=...)` 는 `ValidationError: runtime Field required` 로 실패하고, 맨 `ToolNode` 도 `ValueError: Missing required config key` 로 실패한다. 따라서 도구를 단독으로 단위 테스트할 수 없다 — **순수 로직을 `core/` 에 두고 거기를 테스트하는 설계가 필수다.** 래퍼는 스키마 테스트와 그래프 통과 테스트로 덮는다.

**⑥ API 키 없이 에이전트를 끝까지 테스트할 수 있다.** `BaseChatModel` 을 상속해 `bind_tools`(자기 자신을 돌려줌)와 `_generate`(대본을 순서대로 냄)만 구현하면 된다. `GenericFakeChatModel` 은 `bind_tools` 를 구현하지 않아 `NotImplementedError` 가 나므로 쓸 수 없다. 실측 결과:

```
주입된 principal : Principal(department='인사팀', clearance=2)
최종 답변        : 규정 2.6.1 에 네트워크 접근 통제가 있습니다.
메시지 수        : 4   (user → tool_call → tool → answer)
```

**⑦ Cloudflare Containers 설정 형태** — `containers[]`(`class_name`·`image`·`max_instances`·`instance_type`) + `durable_objects.bindings` + `migrations`(**`new_sqlite_classes`**, `new_classes` 가 아니다). Worker 는 `Container` 를 상속한 클래스에 `defaultPort`·`sleepAfter`·`envVars` 를 두고 `env.BINDING.getByName(...)` 으로 라우팅한다. 이미지 상한 20GB, 인스턴스 최대 4 vCPU · 12 GiB, **Workers Paid $5/월 필요.**

**⑧ 이 환경에는 Gemini 자격증명이 없다.** `GOOGLE_API_KEY` 미설정, `ant` CLI 없음. Task 2 의 `llm` 마커 테스트와 배포는 사람이 키를 발급해 넣어야 돈다 — 계획이 그 단계를 명시한다.

---

## 실행 구조 — 두 국면

| 국면 | 태스크 | 성격 | 검증 |
|---|---|---|---|
| **A. 로컬에서 도는 백엔드** | 1 ~ 4 | 전부 에이전트가 실행 가능 | `pytest`, 로컬 컨테이너 |
| **B. 배포** | 5 ~ 8 | **외부 계정·결제·OAuth 등록이 섞인다** | 배포된 URL 스모크 |

국면 B 의 일부 단계는 사람만 할 수 있다(계정 생성, 결제, 시크릿 발급). 그런 단계는 **`👤 사람이 하는 단계`** 로 표시했다. 에이전트는 그 앞에서 멈추고 결과를 받아 이어간다.

국면 A 가 끝나면 그 자체로 동작하는 소프트웨어다 — 로컬에서 `POST /ask` 가 답을 낸다. 국면 B 를 미뤄도 A 는 값이 있다.

---

## File Structure

```
backend/
  core/
    agent/
      tools.py            search_policy 의 실제 로직 — 순수 파이썬, 포트만 안다
      policy.py           (수정) MAX_TOOL_CALLS = 8 을 더한다
  adapters/
    llm/
      __init__.py
      gemini.py           ChatGoogleGenerativeAI 구성 — 모델 ID·max_output_tokens 한 곳
    agent/
      __init__.py
      context.py          AgentContext — principal 을 나르는 런타임 컨텍스트
      runner.py           create_agent 조립. @tool 이 principal 을 노출하지 않는다
  api/
    __init__.py
    security.py           공유 시크릿 검사 — 상수 시간 비교
    schemas.py            AskRequest · AskResponse · PolicyHitView · PersonaView
    deps.py               싱글턴 조립 (임베더·검색기·에이전트) + principal 조회
    main.py               FastAPI 앱. POST /ask · GET /healthz
  tests/
    fake_chat.py          대본 모델 — bind_tools 를 구현한 테스트 더블
    test_agent_tools.py   core 도구 로직 (스텁 포트)
    test_agent_runner.py  스키마 은닉 + 대본 모델로 그래프 통과
    test_api.py           TestClient
    test_api_security.py  시크릿 검사
  Dockerfile
  .dockerignore
frontend/
  app/
    layout.tsx  page.tsx
    api/auth/[...nextauth]/route.ts
    api/ask/route.ts      BFF — 세션 확인 후 백엔드 호출
  components/
    AskForm.tsx  PersonaPicker.tsx  Answer.tsx
  auth.ts               Auth.js 설정
  package.json  next.config.ts  tsconfig.json  .env.example
infra/
  wrangler.jsonc        Cloudflare Worker + Container 설정
  worker.ts             Container 라우팅
docs/
  (기존 spec 2개)
```

**책임 분리 근거:** `core/agent/tools.py` 와 `adapters/agent/runner.py` 를 나눈 것은 실물 확인 ⑤ 때문이다 — 컨텍스트 주입이 그래프를 거쳐야만 되므로, 로직이 래퍼 안에 있으면 단위 테스트가 불가능해진다. `api/security.py` 를 따로 둔 것은 시크릿 비교가 조용히 틀리기 쉬운 곳이고(비상수 시간 비교), 한 파일로 격리해야 그 테스트가 판별력을 갖기 때문이다.

---

# 국면 A — 로컬에서 도는 백엔드

### Task 1: 의존성과 도구 로직

**Files:**
- Modify: `backend/pyproject.toml`, `backend/requirements.txt`
- Create: `backend/core/agent/tools.py`
- Modify: `backend/core/agent/policy.py`
- Test: `backend/tests/test_agent_tools.py`

**Interfaces:**
- Consumes: `core.retrieve.hybrid.search(query, principal, embedder, searcher, k)` · `ChunkSearch.load_hits(ids, principal)` · `core.agent.policy.enforce(hits, principal)` (전부 W1·W2 산출물)
- Produces:
  - `core.agent.tools.search_policy(query: str, principal: Principal, embedder: Embedder, searcher: ChunkSearch, k: int = 10) -> list[PolicyHit]`
  - `core.agent.policy.MAX_TOOL_CALLS: int = 8`

**W2 가 남긴 구멍을 여기서 메운다.** W2 최종 리뷰가 "`enforce` 는 프로덕션 호출자가 0이고 테스트만 쓴다"고 적었다. 이 도구가 첫 호출자다 — 도구 경계에서 재검증하는 것이 spec §5.4 의 원래 의도다.

- [ ] **Step 1: 의존성을 더한다**

`backend/pyproject.toml` 의 `dependencies` 를 아래로 바꾼다.

```toml
dependencies = [
    "fastapi>=0.115",
    "langchain>=1.3",
    "langchain-google-genai>=4.3",
    "langgraph>=1.2",
    "psycopg[binary]>=3.2",
    "pypdf>=5.1",
    "pyyaml>=6.0",
    "sentence-transformers>=3.3",
    "uvicorn[standard]>=0.32",
]
```

`backend/requirements.txt` 를 아래로 바꾼다.

```
fastapi>=0.115
langchain>=1.3
langchain-google-genai>=4.3
langgraph>=1.2
psycopg[binary]>=3.2
pypdf>=5.1
pyyaml>=6.0
sentence-transformers>=3.3
uvicorn[standard]>=0.32
```

`[dependency-groups]` 의 `dev` 에 `httpx` 를 더한다 — FastAPI `TestClient` 가 요구한다.

```toml
dev = [
    "httpx>=0.27",
    "pytest>=8.0",
    "ruff>=0.6",
]
```

설치한다:

```bash
cd /Users/ryujun/Documents/secu-agent/backend
uv pip install --python .venv/bin/python -e . --group dev
.venv/bin/python -c "
from importlib.metadata import version
for p in ('langchain','langgraph','langchain-google-genai','fastapi','uvicorn','httpx'):
    print(p, version(p))"
```

Expected: 전부 출력된다. `langchain` 은 1.3 이상, `langgraph` 는 1.2 이상.

- [ ] **Step 2: 경계 테스트가 여전히 통과하는지 본다**

새 패키지가 `core/` 로 새어들지 않았는지 먼저 확인한다.

Run: `cd backend && .venv/bin/python -m pytest tests/test_boundaries.py -q`
Expected: PASS. `langchain`·`langgraph` 는 이미 금지 목록에 있다.

- [ ] **Step 3: 실패하는 테스트를 쓴다**

`backend/tests/test_agent_tools.py`:

```python
"""도구 로직 — LangChain 도 LLM 도 DB 도 없이 검사한다.

이 파일이 존재할 수 있는 이유가 곧 설계 근거다. LangChain 의 컨텍스트
주입은 컴파일된 그래프를 거쳐야만 동작하므로(실측), 로직이 @tool 래퍼
안에 있으면 단위 테스트할 방법이 없다. 그래서 로직은 core 에 있다.
"""

import pytest

from core.agent.policy import AccessViolation
from core.agent.tools import search_policy
from core.types import EMBEDDING_DIM, PolicyHit, Principal

사원 = Principal(department="개발팀", clearance=1)


class 고정임베더:
    def encode(self, texts, kind):
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class 스텁검색기:
    """받은 principal 을 기록하고, 미리 정해둔 hit 을 돌려준다."""

    def __init__(self, hits: list[PolicyHit]) -> None:
        self.hits = hits
        self.받은_주체: list[Principal] = []
        self.받은_k: list[int] = []

    def by_vector(self, vec, principal, k):
        self.받은_주체.append(principal)
        self.받은_k.append(k)
        return [h.chunk_id for h in self.hits]

    def by_keyword(self, query, principal, k):
        self.받은_주체.append(principal)
        return [h.chunk_id for h in self.hits]

    def load_hits(self, ids, principal):
        self.받은_주체.append(principal)
        by_id = {h.chunk_id: h for h in self.hits}
        return [by_id[i] for i in ids if i in by_id]


def _hit(chunk_id=1, clearance=1, depts=(), code="2.6.1"):
    return PolicyHit(
        chunk_id=chunk_id,
        text=f"본문 {chunk_id}",
        doc_title="ISMS-P 인증기준 안내서",
        clause_code=code,
        required_clearance=clearance,
        allowed_departments=depts,
    )


def test_권한_안의_결과를_그대로_돌려준다():
    검색기 = 스텁검색기([_hit(1), _hit(2)])
    결과 = search_policy("네트워크 접근", 사원, 고정임베더(), 검색기)
    assert [h.chunk_id for h in 결과] == [1, 2]


def test_모든_검색_경로에_같은_주체를_넘긴다():
    """한 경로라도 다른 주체를 쓰면 그쪽으로 누출된다(spec 6.1)."""
    검색기 = 스텁검색기([_hit(1)])
    search_policy("질의", 사원, 고정임베더(), 검색기)
    assert 검색기.받은_주체, "검색기가 한 번도 안 불렸다"
    assert all(p == 사원 for p in 검색기.받은_주체)


def test_권한_밖_항목이_섞이면_예외가_난다():
    """검색기가 고장나 권한 밖 항목을 돌려주면 도구가 터진다.

    조용히 걸러내면 사후 필터링이 되고, 버그가 결과 개수 뒤에 숨는다.
    이 도구가 core.agent.policy.enforce 의 첫 프로덕션 호출자다.
    """
    검색기 = 스텁검색기([_hit(1), _hit(2, clearance=3)])
    with pytest.raises(AccessViolation):
        search_policy("질의", 사원, 고정임베더(), 검색기)


def test_k_를_검색에_전달한다():
    검색기 = 스텁검색기([_hit(1)])
    search_policy("질의", 사원, 고정임베더(), 검색기, k=3)
    # hybrid.search 가 후보를 k 의 배수로 가져가므로 k 자체가 아니라
    # 그것에 비례한 값이 온다. 0 이나 고정값이 아닌 것만 확인한다.
    assert 검색기.받은_k and all(n >= 3 for n in 검색기.받은_k)


def test_결과가_없으면_빈_리스트다():
    """볼 수 있는 것이 없는 것과 규칙이 깨진 것은 다르다."""
    검색기 = 스텁검색기([])
    assert search_policy("질의", 사원, 고정임베더(), 검색기) == []
```

- [ ] **Step 4: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_agent_tools.py -q`
Expected: 수집 단계에서 FAIL — `ModuleNotFoundError: No module named 'core.agent.tools'`

- [ ] **Step 5: 상한 상수를 더한다**

`backend/core/agent/policy.py` 의 `AccessViolation` 클래스 **바로 위**에 넣는다:

```python
# 도구 호출 상한. 넘으면 그 도구만 막고 모델은 그때까지의 결과로 답한다.
# 상한이 없으면 에이전트가 도구를 반복 호출하며 비용과 지연이 무한정 늘어난다.
# 8 은 "규정 검색 → 재검색" 을 여러 바퀴 돌 수 있는 여유다(상위 spec 7.2).
MAX_TOOL_CALLS = 8
```

- [ ] **Step 6: 도구 로직을 구현한다**

`backend/core/agent/tools.py`:

```python
"""에이전트 도구의 실제 로직.

LangChain 도 LLM 도 모른다. 포트만 안다.

adapters/agent/runner.py 와 분리한 것은 스타일이 아니다. LangChain 의
컨텍스트 주입은 컴파일된 그래프를 거쳐야만 동작한다 — 실측: 도구를
직접 invoke 하면 ValidationError, 맨 ToolNode 로도 ValueError 다.
로직이 @tool 래퍼 안에 있으면 단위 테스트할 방법이 없어진다.
"""

from core.agent.policy import enforce
from core.ports import ChunkSearch, Embedder
from core.retrieve.hybrid import search
from core.types import PolicyHit, Principal

DEFAULT_K = 10


def search_policy(
    query: str,
    principal: Principal,
    embedder: Embedder,
    searcher: ChunkSearch,
    k: int = DEFAULT_K,
) -> list[PolicyHit]:
    """권한이 반영된 규정 청크를 관련도 순으로 돌려준다.

    principal 이 필수 인자다 — 권한 없는 검색을 호출할 방법이 없다(spec 5.3).

    돌려주기 전에 enforce 로 한 번 더 검사한다. 정상 경로에서는 절대
    발동하지 않는다. 발동했다면 사전 필터링이 깨졌다는 뜻이고, 그 사실이
    조용히 묻히면 안 된다(spec 5.4).

    embedder 와 searcher 를 인자로 받는 이유: core 는 어댑터를 만들 수
    없다. 어댑터 쪽이 이 둘을 묶어 LLM 에게는 (query, k) 만 보이는 도구로
    감싼다.
    """
    ids = search(query, principal, embedder, searcher, k=k)
    hits = searcher.load_hits(ids, principal)
    return enforce(hits, principal)
```

- [ ] **Step 7: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_agent_tools.py -v`
Expected: 5개 PASS

- [ ] **Step 8: 변이 검사 — enforce 가 정말 이 경로에 걸려 있는가**

`search_policy` 의 마지막 줄을 `return hits` 로 **일시적으로** 바꾼다.

Run: `cd backend && .venv/bin/python -m pytest tests/test_agent_tools.py -q`
Expected: **`test_권한_밖_항목이_섞이면_예외가_난다` 가 FAIL** (`DID NOT RAISE`)

되돌리고 다시 통과를 본다. 되돌리는 것을 잊으면 안 된다.

- [ ] **Step 9: 린트하고 커밋한다**

```bash
cd backend
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format .
.venv/bin/python -m pytest -q
cd /Users/ryujun/Documents/secu-agent
git add backend/pyproject.toml backend/requirements.txt \
        backend/core/agent/tools.py backend/core/agent/policy.py \
        backend/tests/test_agent_tools.py
git commit -m "도구 로직을 core 에 두었다

search_policy 의 실제 로직이 LangChain 을 모르는 곳에 있다. 이 분리는
스타일이 아니라 필수다 — LangChain 의 컨텍스트 주입은 컴파일된 그래프를
거쳐야만 동작해서, 로직이 @tool 래퍼 안에 있으면 단위 테스트할 방법이 없다.

도구가 결과를 돌려주기 전에 enforce 를 통과시킨다. W2 에서 enforce 는
프로덕션 호출자가 없었고 테스트만 썼다 — 이것이 첫 호출자이고, 도구
경계에서 재검증하는 것이 spec 5.4 의 원래 의도다.

enforce 를 빼면 권한 밖 항목 테스트가 실패하는 것을 확인하고 되돌렸다."
```

---

### Task 2: 에이전트 런너 — `principal` 을 스키마에서 뺀다

**Files:**
- Create: `backend/adapters/llm/__init__.py`, `backend/adapters/llm/gemini.py`
- Create: `backend/adapters/agent/__init__.py`, `backend/adapters/agent/context.py`, `backend/adapters/agent/runner.py`
- Create: `backend/tests/fake_chat.py`, `backend/tests/test_agent_runner.py`
- Modify: `backend/pyproject.toml` (마커)

**Interfaces:**
- Consumes: `core.agent.tools.search_policy(...)` · `core.agent.policy.MAX_TOOL_CALLS` (Task 1)
- Produces:
  - `adapters.agent.context.AgentContext(principal: Principal, collected: list[PolicyHit])`
  - `adapters.agent.runner.build_tools(embedder, searcher) -> list`
  - `adapters.agent.runner.build_agent(embedder, searcher, model) -> CompiledStateGraph`
  - `adapters.llm.gemini.build_model(api_key: str | None = None) -> ChatGoogleGenerativeAI` · `MODEL_ID = "gemini-3.7-flash"`
  - `tests.fake_chat.대본모델(대본: list[AIMessage])`

**이 태스크가 W3 의 보안 결정을 담는다.** W2 최종 리뷰가 *"`principal` 이 필수 인자인 것은 **누락**을 불가능하게 하지만 **사칭**은 막지 않는다"* 고 지적했다. 도구 스키마에 `principal` 이 보이면 LLM 이 `clearance: 3` 을 써넣을 수 있고, **그 사고는 조용하다** — 에이전트는 여전히 답을 내고 스위트는 초록이다. 스키마를 직접 들여다보는 테스트가 아니면 잡히지 않는다.

- [ ] **Step 1: `llm` 마커를 등록한다**

`backend/pyproject.toml` 의 `markers` 에 이미 `llm` 이 있다. 확인만 하고 없으면 더한다:

```toml
    "llm: 실제 LLM API 를 호출하는 테스트 (기본 제외)",
```

- [ ] **Step 2: 대본 모델(테스트 더블)을 쓴다**

`backend/tests/fake_chat.py`:

```python
"""대본대로 답하는 가짜 채팅 모델.

이것이 있어야 에이전트를 API 키 없이, 비용 없이 끝까지 테스트할 수 있다.

langchain_core 의 GenericFakeChatModel 을 쓸 수 없다 — bind_tools 를
구현하지 않아 create_agent 안에서 NotImplementedError 가 난다(실측).
필요한 것은 bind_tools 와 _generate 둘뿐이다.
"""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class 대본모델(BaseChatModel):
    """정해둔 AIMessage 를 순서대로 낸다. 대본이 끝나면 마지막 것을 반복한다."""

    대본: list[AIMessage] = []
    호출수: int = 0
    본_도구: list[Any] = []

    @property
    def _llm_type(self) -> str:
        return "대본모델"

    def bind_tools(self, tools, **kwargs):
        # 어떤 도구가 모델에게 전달되는지 기록한다 — 스키마 검사가 이걸 본다.
        self.본_도구 = list(tools)
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        msg = self.대본[min(self.호출수, len(self.대본) - 1)]
        self.호출수 += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])
```

- [ ] **Step 3: 실패하는 테스트를 쓴다**

`backend/tests/test_agent_runner.py`:

```python
"""에이전트 런너 — LLM 없이 검사한다.

가장 중요한 것은 test_principal_이_도구_스키마에_없다 다. principal 이
스키마에 새어 들어오면 LLM 이 등급을 지정할 수 있게 되는데, 그 사고는
조용하다 — 에이전트는 여전히 답을 내고 나머지 테스트도 전부 통과한다.
"""

import pytest
from langchain_core.messages import AIMessage

from adapters.agent.context import AgentContext
from adapters.agent.runner import build_agent, build_tools
from core.types import EMBEDDING_DIM, PolicyHit, Principal
from tests.fake_chat import 대본모델

사원 = Principal(department="개발팀", clearance=1)
팀장 = Principal(department="인사팀", clearance=2)


class 고정임베더:
    def encode(self, texts, kind):
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class 스텁검색기:
    def __init__(self, hits):
        self.hits = hits
        self.받은_주체 = []

    def by_vector(self, vec, principal, k):
        self.받은_주체.append(principal)
        return [h.chunk_id for h in self.hits]

    def by_keyword(self, query, principal, k):
        self.받은_주체.append(principal)
        return [h.chunk_id for h in self.hits]

    def load_hits(self, ids, principal):
        self.받은_주체.append(principal)
        by_id = {h.chunk_id: h for h in self.hits}
        return [by_id[i] for i in ids if i in by_id]


def _hit(chunk_id=1, code="2.6.1"):
    return PolicyHit(
        chunk_id=chunk_id,
        text="네트워크에 대한 비인가 접근을 통제한다",
        doc_title="ISMS-P 인증기준 안내서",
        clause_code=code,
        required_clearance=1,
        allowed_departments=(),
    )


def _도구_호출(query="네트워크 접근"):
    return AIMessage(
        content="",
        tool_calls=[{"name": "search_policy", "args": {"query": query}, "id": "c1", "type": "tool_call"}],
    )


# ────────────────────── 보안: 스키마 은닉 ──────────────────────


def test_principal_이_도구_스키마에_없다():
    """**이 파일에서 가장 중요한 테스트다.**

    모델에게 전달되는 스키마는 tool_call_schema 다. 여기에 principal 이
    보이면 LLM 이 clearance 를 직접 지정할 수 있다 — 필수 인자로 두는
    것은 누락을 막을 뿐 사칭을 막지 못한다.

    args_schema 를 검사하면 안 된다. 거기에는 runtime 이 남아 있고,
    args_schema.model_json_schema() 는 PydanticInvalidForJsonSchema 를
    던진다 — ToolRuntime 이 callable 필드를 갖기 때문이다(실측).
    """
    도구들 = build_tools(고정임베더(), 스텁검색기([_hit()]))
    assert len(도구들) == 1

    스키마 = 도구들[0].tool_call_schema.model_json_schema()
    필드 = set(스키마["properties"])

    assert "principal" not in 필드
    assert "runtime" not in 필드
    assert "clearance" not in 필드
    assert "department" not in 필드
    assert 필드 == {"query", "k"}, f"모델이 보는 필드가 예상과 다르다: {필드}"


def test_스키마에_query_는_있다():
    """은닉이 지나쳐 도구가 아무것도 못 받게 되면 안 된다."""
    도구들 = build_tools(고정임베더(), 스텁검색기([_hit()]))
    스키마 = 도구들[0].tool_call_schema.model_json_schema()
    assert "query" in 스키마["properties"]
    assert "query" in 스키마["required"]


# ────────────────────── 컨텍스트 주입 ──────────────────────


def test_요청의_주체가_검색까지_전달된다():
    검색기 = 스텁검색기([_hit()])
    모델 = 대본모델(대본=[_도구_호출(), AIMessage(content="답변")])
    agent = build_agent(고정임베더(), 검색기, 모델)

    agent.invoke(
        {"messages": [{"role": "user", "content": "네트워크 접근 통제"}]},
        context=AgentContext(principal=팀장),
    )
    assert 검색기.받은_주체, "검색기가 불리지 않았다"
    assert all(p == 팀장 for p in 검색기.받은_주체)


def test_인용_근거가_컨텍스트에_모인다():
    """API 가 인용을 꺼내는 경로다. 컨텍스트 객체가 그대로 전달된다(실측)."""
    검색기 = 스텁검색기([_hit(1, "2.6.1"), _hit(2, "2.5.1")])
    모델 = 대본모델(대본=[_도구_호출(), AIMessage(content="답변")])
    ctx = AgentContext(principal=사원)

    build_agent(고정임베더(), 검색기, 모델).invoke(
        {"messages": [{"role": "user", "content": "질문"}]}, context=ctx
    )
    assert [h.clause_code for h in ctx.collected] == ["2.6.1", "2.5.1"]


def test_도구를_안_부르면_근거가_비어_있다():
    검색기 = 스텁검색기([_hit()])
    모델 = 대본모델(대본=[AIMessage(content="도구 없이 바로 답한다")])
    ctx = AgentContext(principal=사원)

    res = build_agent(고정임베더(), 검색기, 모델).invoke(
        {"messages": [{"role": "user", "content": "안녕"}]}, context=ctx
    )
    assert ctx.collected == []
    assert res["messages"][-1].content == "도구 없이 바로 답한다"


# ────────────────────── 결과 없음 ──────────────────────


def test_결과가_없어도_권한을_이유로_말하지_않는다():
    """"권한이 없어 못 보여준다" 는 문장 자체가 존재 확인이 된다.

    볼 수 있는 것이 없는 것과 문서가 숨겨진 것을 구분해 말하면,
    그 구분이 곧 누출 채널이다.
    """
    검색기 = 스텁검색기([])
    모델 = 대본모델(대본=[_도구_호출(), AIMessage(content="답변")])
    ctx = AgentContext(principal=사원)

    res = build_agent(고정임베더(), 검색기, 모델).invoke(
        {"messages": [{"role": "user", "content": "질문"}]}, context=ctx
    )
    도구_메시지 = [m for m in res["messages"] if m.__class__.__name__ == "ToolMessage"]
    assert 도구_메시지, "도구 메시지가 없다"
    본문 = 도구_메시지[0].content
    for 금지 in ("권한", "등급", "clearance", "접근 불가"):
        assert 금지 not in 본문, f"결과 없음 메시지가 '{금지}' 를 말한다: {본문}"


# ────────────────────── 상한 ──────────────────────


def test_도구_호출_상한이_걸려_있다():
    """상한이 없으면 비용과 지연이 무한정 늘어난다(상위 spec 7.2)."""
    from core.agent.policy import MAX_TOOL_CALLS

    검색기 = 스텁검색기([_hit()])
    모델 = 대본모델(대본=[_도구_호출()])  # 끝없이 도구만 부른다
    agent = build_agent(고정임베더(), 검색기, 모델)

    res = agent.invoke(
        {"messages": [{"role": "user", "content": "질문"}]},
        context=AgentContext(principal=사원),
    )
    실제_호출수 = sum(1 for m in res["messages"] if m.__class__.__name__ == "ToolMessage")
    assert 실제_호출수 <= MAX_TOOL_CALLS, f"{실제_호출수}회 불렸다 — 상한이 안 걸렸다"
```

- [ ] **Step 4: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_agent_runner.py -q`
Expected: 수집 단계에서 FAIL — `ModuleNotFoundError: No module named 'adapters.agent.context'`

- [ ] **Step 5: 런타임 컨텍스트를 구현한다**

```bash
cd backend && mkdir -p adapters/agent adapters/llm && touch adapters/agent/__init__.py adapters/llm/__init__.py
```

`backend/adapters/agent/context.py`:

```python
"""에이전트 한 번의 실행에 딸리는 런타임 컨텍스트.

principal 이 여기 있는 것이 요점이다 — 도구 인자가 아니라 컨텍스트다.
그래서 LLM 이 볼 수도, 지정할 수도 없다.

collected 는 도구가 채우고 호출자가 읽는다. 컨텍스트 객체는 그래프를
지나 도구까지 **같은 객체로** 전달되므로(실측: id 가 일치), 도구가 여기에
담은 것을 invoke 가 끝난 뒤 바깥에서 그대로 꺼낼 수 있다. API 가
인용 근거를 얻는 경로가 이것이다.
"""

from dataclasses import dataclass, field

from core.types import PolicyHit, Principal


@dataclass
class AgentContext:
    principal: Principal
    collected: list[PolicyHit] = field(default_factory=list)
```

- [ ] **Step 6: 런너를 구현한다**

`backend/adapters/agent/runner.py`:

```python
"""LangGraph 런너 — core 의 도구 로직을 감싸기만 한다.

프레임워크는 이 파일에만 산다. core/ 는 langchain 을 모르고 경계 테스트가
그것을 강제한다(상위 spec 2.3).

**principal 은 도구 스키마에 없다.** 도구 함수가 ToolRuntime 을 받으면
그 인자는 모델이 보는 tool_call_schema 에서 빠진다. 필수 인자로 두면
누락은 막지만 사칭은 막지 못한다 — LLM 이 clearance: 3 을 써넣을 수 있다.

create_react_agent 를 쓰지 않는다. langgraph.prebuilt 의 그것은
deprecated 이고 langchain.agents.create_agent 가 현재 API 다.
"""

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.tools import ToolRuntime, tool
from langchain_core.language_models import BaseChatModel

from adapters.agent.context import AgentContext
from core.agent import tools as core_tools
from core.agent.policy import MAX_TOOL_CALLS
from core.ports import ChunkSearch, Embedder

SYSTEM_PROMPT = """너는 사내 보안 규정을 안내하는 도우미다.

규정에 관한 질문에는 반드시 search_policy 도구로 근거를 찾은 뒤 답한다.
도구가 돌려준 조항만 인용한다. 조항 번호를 지어내지 않는다.
도구가 아무것도 돌려주지 않으면 찾지 못했다고 답한다 — 권한이나 등급을
이유로 들지 않는다.
답은 한국어로, 인용한 조항 번호를 본문에 함께 적는다."""

# 도구가 결과 없음을 알릴 때 쓰는 문장. 권한을 이유로 말하지 않는다 —
# "권한이 없어 못 보여준다" 는 문장 자체가 문서의 존재를 확인해준다.
결과_없음 = "관련된 조항을 찾지 못했다."


def build_tools(embedder: Embedder, searcher: ChunkSearch) -> list:
    """모델에게 넘길 도구 목록을 만든다.

    embedder 와 searcher 를 클로저로 닫는다 — 이것들도 LLM 이 볼 이유가 없다.
    """

    @tool
    def search_policy(query: str, runtime: ToolRuntime[AgentContext], k: int = 10) -> str:
        """사내 보안 규정에서 질의와 관련된 조항을 찾는다.

        Args:
            query: 찾고 싶은 내용을 한국어 자연어로 쓴다.
            k: 가져올 조항 수. 기본 10.
        """
        ctx = runtime.context
        hits = core_tools.search_policy(query, ctx.principal, embedder, searcher, k=k)
        ctx.collected.extend(hits)

        if not hits:
            return 결과_없음

        줄 = []
        for h in hits:
            표시 = f"[{h.clause_code}]" if h.clause_code else "[조항 밖]"
            줄.append(f"{표시} {h.doc_title}\n{h.text}")
        return "\n\n".join(줄)

    return [search_policy]


def build_agent(embedder: Embedder, searcher: ChunkSearch, model: BaseChatModel):
    """컴파일된 에이전트를 만든다.

    exit_behavior 가 "continue" 인 이유: 세 값 중 상위 spec 7.2 의 "넘으면
    중단하고 그때까지의 결과로 답한다"에 맞는 것이 이것뿐이다. "error" 는
    예외를 던지고, "end" 는 결과가 아니라 왜 멈췄는지를 답한다.
    """
    return create_agent(
        model=model,
        tools=build_tools(embedder, searcher),
        system_prompt=SYSTEM_PROMPT,
        context_schema=AgentContext,
        middleware=[
            ToolCallLimitMiddleware(run_limit=MAX_TOOL_CALLS, exit_behavior="continue")
        ],
    )
```

- [ ] **Step 7: 모델 어댑터를 구현한다**

`backend/adapters/llm/gemini.py`:

```python
"""Gemini 모델 구성. 모델 ID 가 이 파일에만 있다.

프로바이더를 바꾸는 변경이 이 파일 하나로 끝나는 것이 adapters 격리의
목적이다 — adapters/agent/runner.py 는 BaseChatModel 만 알고, core/ 는
LLM 이 있다는 사실조차 모른다.

환경변수가 GOOGLE_API_KEY 인 이유: langchain-google-genai 는 GOOGLE_API_KEY 와
GEMINI_API_KEY 를 모두 읽지만 GOOGLE_API_KEY 를 권장하고, 둘 다 설정되면
그것을 쓰면서 경고를 낸다. 하나만 쓴다.
"""

import os

from langchain_google_genai import ChatGoogleGenerativeAI

# 공식 문서가 "복잡한 코딩, 에이전트 워크플로, 신뢰할 수 있는 다단계 실행" 용으로
# 명시한 모델이다. 이 프로젝트는 도구를 부르는 에이전트다.
MODEL_ID = "gemini-3.7-flash"
MAX_OUTPUT_TOKENS = 4096


def build_model(api_key: str | None = None) -> ChatGoogleGenerativeAI:
    key = api_key or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "GOOGLE_API_KEY 가 없다. 환경변수로 주거나 build_model(api_key=...) 로 넘긴다."
        )
    return ChatGoogleGenerativeAI(
        model=MODEL_ID, max_output_tokens=MAX_OUTPUT_TOKENS, api_key=key
    )
```

- [ ] **Step 8: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_agent_runner.py -v`
Expected: 7개 PASS

- [ ] **Step 9: 변이 검사 — 스키마 은닉이 정말 검사되는가**

**이 단계를 건너뛰면 이 태스크의 핵심 장치가 아무것도 증명하지 않는다.**

`runner.py` 의 도구 시그니처를 **일시적으로** 아래로 바꾼다(사칭 가능한 형태를 흉내낸다):

```python
    def search_policy(query: str, runtime: ToolRuntime[AgentContext], principal_override: str = "", k: int = 10) -> str:
```

Run: `cd backend && .venv/bin/python -m pytest tests/test_agent_runner.py -q`
Expected: **`test_principal_이_도구_스키마에_없다` 가 FAIL** — `모델이 보는 필드가 예상과 다르다: {'query', 'k', 'principal_override'}`

되돌리고 다시 통과를 본다.

- [ ] **Step 9-b: 실제 LLM 을 부르는 테스트를 쓴다 (기본 제외)**

spec §8 의 테스트 표가 `adapters/agent/runner.py` 에 실제 LLM 호출 테스트를 요구한다. 이 환경에는 키가 없으므로(실물 확인 ⑧) **쓰되 돌리지는 않는다.** `llm` 마커가 기본 스위트에서 제외한다.

`backend/tests/test_agent_runner.py` 끝에 더한다:

```python
@pytest.mark.llm
def test_실제_모델이_도구를_부르고_한국어로_답한다():
    """실제 Gemini 호출. GOOGLE_API_KEY 가 필요하다.

        .venv/bin/python -m pytest -m llm -v

    대본 모델로는 확인할 수 없는 것을 본다 — 진짜 모델이 이 도구 설명과
    시스템 프롬프트를 보고 실제로 도구를 부르는가.
    """
    import os

    if not os.environ.get("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY 가 없다")

    from adapters.llm.gemini import build_model

    검색기 = 스텁검색기([_hit(1, "2.5.4")])
    ctx = AgentContext(principal=사원)
    res = build_agent(고정임베더(), 검색기, build_model()).invoke(
        {"messages": [{"role": "user", "content": "비밀번호는 얼마나 자주 바꿔야 하나"}]},
        context=ctx,
    )
    assert ctx.collected, "실제 모델이 도구를 부르지 않았다 — 도구 설명이나 시스템 프롬프트를 손봐야 한다"
    assert res["messages"][-1].content.strip(), "답변이 비었다"
```

- [ ] **Step 10: 경계 테스트를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_boundaries.py -q`
Expected: PASS. `core/agent/tools.py` 는 langchain 을 import 하지 않는다.

**일부러 어겨 확인한다:** `core/agent/tools.py` 맨 위에 `import langchain` 을 넣고 위 명령을 돌리면 그 파일을 지목하며 FAIL 해야 한다. 확인 후 지운다.

- [ ] **Step 11: 린트하고 커밋한다**

```bash
cd backend
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format .
.venv/bin/python -m pytest -q
cd /Users/ryujun/Documents/secu-agent
git add backend/adapters/llm/ backend/adapters/agent/ \
        backend/tests/fake_chat.py backend/tests/test_agent_runner.py backend/pyproject.toml
git commit -m "에이전트 런너를 세우고 principal 을 도구 스키마에서 뺐다

도구 함수가 ToolRuntime 을 받으면 그 인자가 모델이 보는 tool_call_schema
에서 빠진다. principal 을 필수 인자로 두는 것은 누락을 막을 뿐 사칭을
막지 못한다 — LLM 이 clearance: 3 을 써넣을 수 있다.

스키마에 인자를 하나 더해보고 은닉 테스트가 실패하는 것을 확인한 뒤
되돌렸다. 이 사고는 조용해서, 스키마를 직접 들여다보는 테스트가 아니면
에이전트가 멀쩡히 답하는 동안 아무도 모른다.

args_schema 가 아니라 tool_call_schema 를 검사한다. args_schema 에는
runtime 이 남아 있고 model_json_schema() 가 예외를 던진다.

create_react_agent 는 deprecated 라 langchain.agents.create_agent 를 쓴다.
호출 상한은 ToolCallLimitMiddleware 이고 exit_behavior 는 continue 다 —
세 값 중 '중단하고 그때까지의 결과로 답한다'에 맞는 유일한 값이다.

테스트용 대본 모델을 만들었다. GenericFakeChatModel 은 bind_tools 를
구현하지 않아 create_agent 안에서 NotImplementedError 가 난다."
```

---

### Task 3: FastAPI — 얇은 HTTP 계층

**Files:**
- Modify: `backend/core/ports.py` (`PrincipalStore` Protocol)
- Create: `backend/adapters/db/principal_store.py`
- Create: `backend/api/__init__.py`, `backend/api/security.py`, `backend/api/schemas.py`, `backend/api/deps.py`, `backend/api/main.py`
- Modify: `backend/tests/test_types.py` (포트 스텁)
- Create: `backend/tests/test_api_security.py`, `backend/tests/test_api.py`
- Modify: `backend/tests/test_db_integration.py`

**Interfaces:**
- Consumes: `build_agent(embedder, searcher, model)` · `AgentContext` (Task 2)
- Produces:
  - `core.ports.PrincipalStore.find(name: str) -> Principal | None`
  - `adapters.db.principal_store.PgPrincipalStore(conn)`
  - `api.main.app` (FastAPI) · `api.main.build_app(agent_factory, principal_store)`
  - `api.security.시크릿_검사`

> **주의 — 반복되는 함정.** `core/ports.py` 의 Protocol 은 `@runtime_checkable` 이고 `backend/tests/test_types.py` 의 `test_포트를_스텁이_만족한다` 가 로컬 스텁을 `isinstance` 로 검사한다. **새 Protocol 을 더하면 그 테스트에 스텁을 함께 더해야 한다.** W2 에서 이 함정을 두 번 밟았다. Step 5 가 그것을 처리한다.

- [ ] **Step 1: 시크릿 검사의 실패하는 테스트를 쓴다**

`backend/tests/test_api_security.py`:

```python
"""공유 시크릿 검사.

백엔드는 Vercel 의 Route Handler 하고만 대화한다. 시크릿이 없으면
백엔드가 공개 엔드포인트가 되고, 그 뒤에는 LLM 이 있다 — 아무나
요금을 태울 수 있다.
"""

import pytest
from fastapi import HTTPException

from api.security import 시크릿_검사


def test_맞는_시크릿은_통과한다(monkeypatch):
    monkeypatch.setenv("BACKEND_SHARED_SECRET", "s3cret")
    시크릿_검사("s3cret")  # 예외가 없으면 통과


def test_틀린_시크릿은_401_이다(monkeypatch):
    monkeypatch.setenv("BACKEND_SHARED_SECRET", "s3cret")
    with pytest.raises(HTTPException) as e:
        시크릿_검사("wrong")
    assert e.value.status_code == 401


def test_시크릿이_없으면_401_이다(monkeypatch):
    monkeypatch.setenv("BACKEND_SHARED_SECRET", "s3cret")
    with pytest.raises(HTTPException) as e:
        시크릿_검사(None)
    assert e.value.status_code == 401


def test_서버에_시크릿이_설정되지_않았으면_500_이고_통과시키지_않는다(monkeypatch):
    """설정 누락이 '아무나 통과' 로 이어지면 안 된다 — 닫히는 쪽으로 실패한다."""
    monkeypatch.delenv("BACKEND_SHARED_SECRET", raising=False)
    with pytest.raises(HTTPException) as e:
        시크릿_검사("무엇이든")
    assert e.value.status_code == 500


def test_401_응답이_이유를_설명하지_않는다(monkeypatch):
    """'시크릿이 틀렸다' 와 '시크릿이 없다' 를 구분해 알려줄 이유가 없다."""
    monkeypatch.setenv("BACKEND_SHARED_SECRET", "s3cret")
    메시지 = []
    for 값 in ("wrong", None):
        with pytest.raises(HTTPException) as e:
            시크릿_검사(값)
        메시지.append(e.value.detail)
    assert 메시지[0] == 메시지[1]


def test_상수_시간_비교를_쓴다():
    """== 로 비교하면 타이밍으로 시크릿을 한 글자씩 알아낼 수 있다."""
    import inspect

    from api import security

    소스 = inspect.getsource(security)
    assert "compare_digest" in 소스, "hmac.compare_digest 를 쓰지 않는다"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_api_security.py -q`
Expected: `ModuleNotFoundError: No module named 'api.security'`

- [ ] **Step 3: 시크릿 검사를 구현한다**

```bash
cd backend && mkdir -p api && touch api/__init__.py
```

`backend/api/security.py`:

```python
"""공유 시크릿 검사.

브라우저는 이 백엔드를 직접 부르지 않는다. Vercel 의 Route Handler 가
세션을 확인한 뒤 이 시크릿을 달고 부른다.

hmac.compare_digest 를 쓴다. == 로 비교하면 첫 불일치 지점에서 빠져나가
응답 시간이 일치한 글자 수에 따라 달라지고, 그것으로 시크릿을 한 글자씩
알아낼 수 있다.
"""

import hmac
import os

from fastapi import Header, HTTPException

_설정_없음 = "서버 설정 오류"
_거부 = "인증되지 않았다"


def 시크릿_검사(x_backend_secret: str | None = Header(default=None)) -> None:
    기대값 = os.environ.get("BACKEND_SHARED_SECRET", "")
    if not 기대값:
        # 닫히는 쪽으로 실패한다. 설정 누락이 '아무나 통과' 가 되면 안 된다.
        raise HTTPException(status_code=500, detail=_설정_없음)
    if x_backend_secret is None or not hmac.compare_digest(x_backend_secret, 기대값):
        # 없는 것과 틀린 것을 구분해 알려줄 이유가 없다.
        raise HTTPException(status_code=401, detail=_거부)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest tests/test_api_security.py -v`
Expected: 6개 PASS

- [ ] **Step 5: 주체 저장소 포트와 어댑터를 더한다**

`backend/core/ports.py` 의 `ChunkSearch` **아래**에 더한다:

```python
@runtime_checkable
class PrincipalStore(Protocol):
    def find(self, name: str) -> Principal | None:
        """이름으로 주체를 찾는다. 없으면 None.

        API 가 페르소나 이름을 Principal 로 바꿀 때 쓴다. 클라이언트가
        department·clearance 를 직접 보내지 않는 이유가 이것이다 —
        보내게 하면 그 값이 곧 사칭 경로다.
        """
        ...
```

**같은 파일의 `test_types.py` 스텁을 함께 고친다.** `backend/tests/test_types.py` 의 `test_포트를_스텁이_만족한다` 안, `검색기` 클래스 **아래**에 더하고 단언도 더한다:

```python
    class 주체저장소:
        def find(self, name):
            return None
```

```python
    assert isinstance(주체저장소(), PrincipalStore)
```

그리고 그 파일 맨 위 import 에 `PrincipalStore` 를 더한다:

```python
from core.ports import ChunkSearch, DocumentStore, Embedder, PrincipalStore
```

`backend/adapters/db/principal_store.py`:

```python
"""PrincipalStore 의 psycopg 구현.

principals 테이블은 W2 의 seed-principals 가 채운다. 페르소나 목록을
코드에 다시 적지 않는 이유: 두 벌이 되면 어긋난다.
"""

import psycopg

from core.types import Principal


class PgPrincipalStore:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def find(self, name: str) -> Principal | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT department, clearance FROM principals WHERE name = %s", (name,)
            )
            row = cur.fetchone()
        if row is None:
            return None
        return Principal(department=row[0], clearance=row[1])
```

`backend/tests/test_db_integration.py` 끝에 더한다:

```python
def test_주체를_이름으로_찾는다(store):
    from adapters.db.principal_store import PgPrincipalStore
    from core.ports import PrincipalStore

    with store.conn.cursor() as cur:
        cur.execute(
            "INSERT INTO principals (name, department, clearance) VALUES (%s, %s, %s) "
            "ON CONFLICT (name) DO UPDATE SET clearance = EXCLUDED.clearance",
            ("박인사", "인사팀", 2),
        )
    store.conn.commit()

    저장소 = PgPrincipalStore(store.conn)
    assert isinstance(저장소, PrincipalStore)
    assert 저장소.find("박인사") == Principal(department="인사팀", clearance=2)
    assert 저장소.find("없는사람") is None
```

`test_db_integration.py` 맨 위 import 에 `Principal` 을 더한다.

- [ ] **Step 6: API 의 실패하는 테스트를 쓴다**

`backend/tests/test_api.py`:

```python
"""API — DB 도 LLM 도 없이 검사한다."""

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from adapters.agent.runner import build_agent
from api.main import build_app
from core.types import EMBEDDING_DIM, PolicyHit, Principal
from tests.fake_chat import 대본모델

시크릿 = "테스트시크릿"
헤더 = {"X-Backend-Secret": 시크릿}


class 고정임베더:
    def encode(self, texts, kind):
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class 스텁검색기:
    def __init__(self, hits):
        self.hits = hits

    def by_vector(self, vec, principal, k):
        return [h.chunk_id for h in self.hits]

    def by_keyword(self, query, principal, k):
        return [h.chunk_id for h in self.hits]

    def load_hits(self, ids, principal):
        by_id = {h.chunk_id: h for h in self.hits}
        return [by_id[i] for i in ids if i in by_id]


class 스텁주체저장소:
    def __init__(self, 목록):
        self.목록 = 목록

    def find(self, name):
        return self.목록.get(name)


def _hit(chunk_id=1, code="2.6.1"):
    return PolicyHit(
        chunk_id=chunk_id,
        text="네트워크에 대한 비인가 접근을 통제한다",
        doc_title="ISMS-P 인증기준 안내서",
        clause_code=code,
        required_clearance=1,
        allowed_departments=(),
    )


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)
    검색기 = 스텁검색기([_hit()])
    저장소 = 스텁주체저장소({"박인사": Principal("인사팀", 2)})

    def 에이전트_공장():
        모델 = 대본모델(
            대본=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "search_policy", "args": {"query": "네트워크"}, "id": "c1", "type": "tool_call"}
                    ],
                ),
                AIMessage(content="규정 2.6.1 을 참고한다."),
            ]
        )
        return build_agent(고정임베더(), 검색기, 모델)

    return TestClient(build_app(에이전트_공장, 저장소))


def test_시크릿_없이는_401_이다(client):
    r = client.post("/ask", json={"query": "질문", "persona": "박인사"})
    assert r.status_code == 401


def test_답변과_인용을_돌려준다(client):
    r = client.post("/ask", json={"query": "네트워크 접근", "persona": "박인사"}, headers=헤더)
    assert r.status_code == 200
    본문 = r.json()
    assert 본문["answer"] == "규정 2.6.1 을 참고한다."
    assert [h["clause_code"] for h in 본문["hits"]] == ["2.6.1"]
    assert 본문["persona"] == {"name": "박인사", "department": "인사팀", "clearance": 2}
    assert 본문["tool_calls"] == 1


def test_모르는_페르소나는_400_이다(client):
    r = client.post("/ask", json={"query": "질문", "persona": "없는사람"}, headers=헤더)
    assert r.status_code == 400


def test_400_응답이_존재하는_이름을_알려주지_않는다(client):
    r = client.post("/ask", json={"query": "질문", "persona": "없는사람"}, headers=헤더)
    본문 = str(r.json())
    for 이름 in ("김개발", "박인사", "최임원"):
        assert 이름 not in 본문


def test_clearance_를_직접_보내도_무시된다(client):
    """클라이언트가 등급을 지정할 수 있으면 그 값이 곧 사칭 경로다."""
    r = client.post(
        "/ask",
        json={"query": "질문", "persona": "박인사", "clearance": 3, "department": "임원실"},
        headers=헤더,
    )
    assert r.status_code == 200
    assert r.json()["persona"]["clearance"] == 2


def test_healthz_는_시크릿_없이도_열린다(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert set(r.json()) >= {"status", "db", "model"}
```

- [ ] **Step 7: 스키마와 앱을 구현한다**

`backend/api/schemas.py`:

```python
"""HTTP 경계의 타입.

AskRequest 에 department·clearance 가 **없다**. 클라이언트가 그것을
보낼 수 있으면 그 값이 곧 사칭 경로다. 페르소나 이름만 받고 서버가
principals 테이블에서 번역한다.
"""

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
```

`backend/api/main.py`:

```python
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
        return {
            "status": "ok",
            "db": bool(주체저장소),
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
        도구_호출수 = sum(
            1 for m in 결과["messages"] if m.__class__.__name__ == "ToolMessage"
        )
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
```

`backend/api/deps.py`:

```python
"""프로덕션 조립. 무거운 것을 한 번만 만든다.

임베딩 모델 로드가 수십 초 걸리므로 프로세스당 한 번만 한다.
에이전트는 요청마다 새로 만든다 — 도구가 클로저로 검색기를 닫고 있고,
그래프 조립 자체는 싸다.
"""

import os
from functools import lru_cache

from adapters.agent.runner import build_agent
from adapters.db.chunk_search import PgChunkSearch
from adapters.db.connection import connect
from adapters.db.principal_store import PgPrincipalStore
from adapters.embedding.e5 import E5Embedder
from adapters.llm.gemini import build_model
from api.main import build_app


@lru_cache(maxsize=1)
def _자원():
    conn = connect(os.environ.get("SECUAGENT_DSN"))
    embedder = E5Embedder()
    os.environ["SECUAGENT_MODEL_READY"] = "ready"
    return conn, embedder


def create_app():
    conn, embedder = _자원()
    searcher = PgChunkSearch(conn)
    저장소 = PgPrincipalStore(conn)

    def 에이전트_공장():
        return build_agent(embedder, searcher, build_model())

    return build_app(에이전트_공장, 저장소)


app = create_app()
```

- [ ] **Step 8: 통과를 확인한다**

```bash
cd backend
.venv/bin/python -m pytest tests/test_api.py tests/test_api_security.py -v
.venv/bin/python -m pytest -q
```
Expected: API 6개 + 시크릿 6개 PASS, 전체 스위트 PASS

- [ ] **Step 9: DB 테스트를 돌리고 코퍼스를 되살린다**

```bash
docker compose up -d
cd backend && .venv/bin/python -m pytest -m db -q
```
Expected: PASS

`-m db` 가 코퍼스를 지웠다. 되살린다:

```bash
cd /Users/ryujun/Documents/secu-agent/backend
.venv/bin/python -c "
from adapters.db.connection import connect
c = connect()
with c.cursor() as cur: cur.execute('TRUNCATE documents RESTART IDENTITY CASCADE')
c.commit(); c.close()"
.venv/bin/python -m pipeline.cli ingest ../data/raw/ismsp.pdf --title "ISMS-P 인증기준 안내서"
.venv/bin/python -m pipeline.cli ingest-dir ../data/policies
.venv/bin/python -m pipeline.cli seed-principals
```
Expected: 9문서 · 126조항 · 338청크, 계정 3개

- [ ] **Step 10: 린트하고 커밋한다**

```bash
cd backend
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format .
cd /Users/ryujun/Documents/secu-agent
git add backend/api/ backend/core/ports.py backend/adapters/db/principal_store.py \
        backend/tests/test_api.py backend/tests/test_api_security.py \
        backend/tests/test_types.py backend/tests/test_db_integration.py
git commit -m "FastAPI 계층을 더했다

POST /ask 와 GET /healthz 둘뿐이다. 요청은 페르소나 이름만 보내고 서버가
principals 테이블에서 Principal 로 번역한다 — 클라이언트가 department 나
clearance 를 보낼 수 있으면 그 값이 곧 사칭 경로다.

공유 시크릿을 hmac.compare_digest 로 검사한다. == 로 비교하면 응답 시간이
일치한 글자 수에 따라 달라져 한 글자씩 알아낼 수 있다. 시크릿이 서버에
설정되지 않았으면 500 으로 닫히는 쪽으로 실패한다 — 설정 누락이 '아무나
통과' 가 되면 안 된다.

401 과 400 응답이 이유를 설명하지 않는다. 어떤 페르소나가 존재하는지
알려주는 것 자체가 정보다."
```

---

### Task 4: Dockerfile 과 로컬 컨테이너 검증

**Files:**
- Create: `backend/Dockerfile`, `backend/.dockerignore`
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: `api.deps.app` (Task 3)
- Produces: 로컬에서 뜨는 백엔드 이미지

**배포 전에 로컬에서 같은 이미지를 띄운다.** 상위 spec §9 가 "처음 배포에서 나오는 문제(환경변수·모델 파일 크기·DB 연결·메모리)는 예측이 안 된다"고 했다. 그 문제를 클라우드가 아니라 여기서 만난다.

- [ ] **Step 1: `.dockerignore` 를 쓴다**

`backend/.dockerignore`:

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
tests/
.ruff_cache/
```

- [ ] **Step 2: Dockerfile 을 쓴다**

`backend/Dockerfile`:

```dockerfile
# CPU 전용 torch 를 쓴다. 기본 wheel 은 CUDA 를 끌고 와 이미지가 몇 GB 더 커진다.
FROM python:3.12-slim

WORKDIR /app

# 의존성을 먼저 설치해 레이어를 캐시한다 — 소스가 바뀌어도 재설치하지 않는다.
COPY requirements.txt .
RUN pip install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      -r requirements.txt

# 임베딩 모델을 빌드 시점에 받아 이미지에 굽는다. 런타임에 받으면
# 첫 요청이 다운로드까지 기다리고, 네트워크가 막히면 아예 못 뜬다.
ENV HF_HOME=/app/.hf
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('intfloat/multilingual-e5-small')"

COPY core/ ./core/
COPY adapters/ ./adapters/
COPY pipeline/ ./pipeline/
COPY api/ ./api/
COPY db/ ./db/

EXPOSE 8080
CMD ["uvicorn", "api.deps:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 3: 빌드하고 크기를 잰다**

```bash
cd /Users/ryujun/Documents/secu-agent/backend
docker build -t secu-agent-backend .
docker images secu-agent-backend --format "{{.Size}}"
```

Expected: 빌드 성공. 크기를 기록한다 — Cloudflare 상한은 20GB 라 여유가 크지만, 실제 값이 배포 시간을 좌우한다.

**빌드가 실패하면 멈추고 보고한다.** 흔한 원인 둘: `--extra-index-url` 없이 CUDA torch 를 받아 디스크가 모자라거나, 모델 다운로드가 네트워크에서 막히는 것이다.

- [ ] **Step 4: compose 에 백엔드를 더한다**

`docker-compose.yml` 의 `services` 아래, `db` **다음**에 더한다:

```yaml
  backend:
    build: ./backend
    depends_on:
      db:
        condition: service_healthy
    environment:
      SECUAGENT_DSN: postgresql://secuagent:secuagent@db:5432/secuagent
      BACKEND_SHARED_SECRET: 로컬개발용시크릿
      GOOGLE_API_KEY: ${GOOGLE_API_KEY}
    ports:
      - "8080:8080"
```

컨테이너 안에서는 DB 호스트가 `db` 이고 포트가 `5432` 다 — `5433` 은 호스트 쪽 매핑이다. 이걸 틀리면 연결이 조용히 실패한다.

- [ ] **Step 5: 띄우고 `/healthz` 를 확인한다**

```bash
cd /Users/ryujun/Documents/secu-agent
docker compose up -d --build backend
sleep 40   # 모델 로드
curl -s localhost:8080/healthz
```
Expected: `{"status":"ok","db":true,"model":"ready"}`

- [ ] **Step 6: 👤 사람이 하는 단계 — Gemini 키를 넣는다**

이 환경에는 `GOOGLE_API_KEY` 가 없다(실측). `/ask` 를 실제로 부르려면 키가 필요하다.

`https://aistudio.google.com/apikey` 에서 키를 발급해 저장소 루트에 `.env` 를 만든다(`.gitignore` 에 이미 `.env` 가 있다):

```
GOOGLE_API_KEY=...
```

키가 없으면 이 태스크의 Step 7 만 건너뛰고 나머지는 진행한다.

- [ ] **Step 7: 실제 질의를 한 번 던진다**

```bash
cd /Users/ryujun/Documents/secu-agent
docker compose up -d backend
curl -s -X POST localhost:8080/ask \
  -H "Content-Type: application/json" \
  -H "X-Backend-Secret: 로컬개발용시크릿" \
  -d '{"query":"네트워크 접근 통제는 어떻게 해야 하나","persona":"김개발"}' | python3 -m json.tool
```

Expected: `answer` 에 한국어 답변, `hits` 에 조항 코드, `persona.clearance` 가 1, `tool_calls` 가 1 이상.

**`persona` 를 `최임원` 으로 바꿔 다시 던진다.** 두 응답의 `hits` 조항 코드가 달라야 한다 — 같으면 권한 필터가 이 경로에 안 걸린 것이다. 그 경우 멈추고 보고한다.

- [ ] **Step 8: 시크릿 없이 불러 401 을 확인한다**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"질문","persona":"김개발"}'
```
Expected: `401`

- [ ] **Step 9: 커밋한다**

```bash
cd /Users/ryujun/Documents/secu-agent
git add backend/Dockerfile backend/.dockerignore docker-compose.yml
git commit -m "백엔드 컨테이너를 만들고 로컬에서 띄웠다

CPU 전용 torch 를 쓴다. 기본 wheel 은 CUDA 를 끌고 와 이미지가 몇 GB
더 커진다.

임베딩 모델을 빌드 시점에 굽는다. 런타임에 받으면 첫 요청이 다운로드까지
기다리고, 네트워크가 막힌 환경에서는 아예 뜨지 못한다.

배포 전에 같은 이미지를 로컬에서 띄워 환경변수·DB 연결·모델 로드를
확인했다. 상위 spec 9 장이 첫 배포에서 나오는 문제는 예측이 안 된다고
한 것들이다."
```

---

# 국면 B — 배포

여기서부터 외부 자원이 섞인다. **`👤` 로 표시한 단계는 사람만 할 수 있다** — 계정 생성, 결제, 시크릿 발급. 에이전트는 그 앞에서 멈추고 결과를 받아 이어간다.

### Task 5: Next.js 프론트와 구글 로그인

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/next.config.ts`, `frontend/.env.example`, `frontend/.gitignore`
- Create: `frontend/auth.ts`, `frontend/app/layout.tsx`, `frontend/app/page.tsx`
- Create: `frontend/app/api/auth/[...nextauth]/route.ts`, `frontend/app/api/ask/route.ts`
- Create: `frontend/components/AskForm.tsx`, `frontend/components/PersonaPicker.tsx`, `frontend/components/Answer.tsx`

**Interfaces:**
- Consumes: 백엔드 `POST /ask` (Task 3) — 헤더 `X-Backend-Secret`
- Produces: `POST /api/ask` (같은 오리진), 구글 로그인

**브라우저는 백엔드를 모른다.** Route Handler 가 세션을 확인한 뒤 시크릿을 달아 호출한다. CORS 도, 크로스도메인 쿠키도, 공개된 백엔드도 없다.

- [ ] **Step 1: 스캐폴딩한다**

```bash
cd /Users/ryujun/Documents/secu-agent/frontend
npm init -y
npm i next@16 react@19 react-dom@19 next-auth@5.0.0-beta.32
npm i -D typescript @types/node @types/react @types/react-dom
```

`next-auth` 를 정확한 버전으로 고정한다. App Router 용 v5 는 아직 beta 이고 `@beta` 태그는 떠다닌다 — 배포가 어느 날 조용히 달라지면 안 된다.

`frontend/package.json` 의 `scripts` 를 아래로 바꾼다:

```json
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  }
```

`frontend/.gitignore`:

```
node_modules/
.next/
.env.local
```

`frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

`frontend/next.config.ts`:

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {};

export default nextConfig;
```

`frontend/.env.example`:

```
AUTH_SECRET=            # openssl rand -base64 32
AUTH_GOOGLE_ID=         # 구글 OAuth 클라이언트 ID
AUTH_GOOGLE_SECRET=     # 구글 OAuth 클라이언트 시크릿
BACKEND_URL=http://localhost:8080
BACKEND_SHARED_SECRET=로컬개발용시크릿
```

- [ ] **Step 2: Auth.js 를 설정한다**

`frontend/auth.ts`:

```ts
import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
});
```

`frontend/app/api/auth/[...nextauth]/route.ts`:

```ts
import { handlers } from "@/auth";

export const { GET, POST } = handlers;
```

- [ ] **Step 3: BFF 라우트를 쓴다**

`frontend/app/api/ask/route.ts`:

```ts
import { auth } from "@/auth";

// 브라우저가 닿는 유일한 엔드포인트다. 백엔드 주소도 시크릿도
// 브라우저에 내려가지 않는다.
export async function POST(req: Request) {
  const session = await auth();
  if (!session) {
    return Response.json({ error: "로그인이 필요합니다" }, { status: 401 });
  }

  const { query, persona } = await req.json();

  const upstream = await fetch(`${process.env.BACKEND_URL}/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Backend-Secret": process.env.BACKEND_SHARED_SECRET ?? "",
    },
    // 백엔드가 받는 것은 이 둘뿐이다. 세션에서 온 어떤 값도 등급으로
    // 번역되지 않는다 — 등급은 페르소나 이름으로만 정해진다.
    body: JSON.stringify({ query, persona }),
  });

  if (!upstream.ok) {
    return Response.json(
      { error: "백엔드 오류", status: upstream.status },
      { status: upstream.status }
    );
  }
  return Response.json(await upstream.json());
}
```

- [ ] **Step 4: 화면을 쓴다**

`frontend/app/layout.tsx`:

```tsx
export const metadata = { title: "Secu-Agent" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body style={{ fontFamily: "system-ui, sans-serif", maxWidth: 760, margin: "0 auto", padding: 24 }}>
        {children}
      </body>
    </html>
  );
}
```

`frontend/app/page.tsx`:

```tsx
import { auth, signIn, signOut } from "@/auth";
import AskForm from "@/components/AskForm";

export default async function Home() {
  const session = await auth();

  if (!session) {
    return (
      <main>
        <h1>Secu-Agent</h1>
        <p>부서·등급에 따라 검색 범위가 달라지는 사내보안 규정 에이전트입니다.</p>
        <form action={async () => { "use server"; await signIn("google"); }}>
          <button type="submit">구글로 로그인</button>
        </form>
      </main>
    );
  }

  return (
    <main>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Secu-Agent</h1>
        <form action={async () => { "use server"; await signOut(); }}>
          <button type="submit">로그아웃</button>
        </form>
      </header>
      <AskForm />
    </main>
  );
}
```

`frontend/components/PersonaPicker.tsx`:

```tsx
"use client";

export const PERSONAS = [
  { name: "김개발", label: "김개발 · 개발팀 · 등급 1" },
  { name: "박인사", label: "박인사 · 인사팀 · 등급 2" },
  { name: "최임원", label: "최임원 · 경영지원팀 · 등급 3" },
];

export default function PersonaPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <fieldset style={{ border: "1px solid #ddd", padding: 12, marginTop: 12 }}>
      <legend>페르소나</legend>
      {PERSONAS.map((p) => (
        <label key={p.name} style={{ display: "block", marginBottom: 4 }}>
          <input
            type="radio"
            name="persona"
            value={p.name}
            checked={value === p.name}
            onChange={() => onChange(p.name)}
          />{" "}
          {p.label}
        </label>
      ))}
      <p style={{ fontSize: 13, color: "#555", marginTop: 8, marginBottom: 0 }}>
        인증은 실제 구글 OAuth 입니다. 부서·등급은 시연을 위해 고르는 값이고,
        고른 값이 실제 권한 필터를 그대로 탑니다. 문서와 계정은 합성이며
        ISMS-P 안내서만 실제 공개 표준입니다.
      </p>
    </fieldset>
  );
}
```

> 이 안내 문구를 지우지 않는다. spec §3.2 가 요구하는 것이고, 없으면 화면이 실제보다 강한 주장을 하게 된다.

`frontend/components/Answer.tsx`:

```tsx
type Hit = { chunk_id: number; clause_code: string | null; doc_title: string; text: string };
export type AskResult = {
  answer: string;
  hits: Hit[];
  persona: { name: string; department: string; clearance: number };
  tool_calls: number;
};

export default function Answer({ result }: { result: AskResult }) {
  return (
    <section style={{ marginTop: 24 }}>
      <h2>답변</h2>
      <p style={{ whiteSpace: "pre-wrap" }}>{result.answer}</p>
      <p style={{ fontSize: 13, color: "#666" }}>
        {result.persona.name} · {result.persona.department} · 등급{" "}
        {result.persona.clearance} · 도구 {result.tool_calls}회
      </p>
      <h3>근거 {result.hits.length}건</h3>
      {result.hits.map((h) => (
        <div key={h.chunk_id} style={{ borderLeft: "3px solid #ddd", paddingLeft: 10, marginBottom: 10 }}>
          <strong>{h.clause_code ? `[${h.clause_code}]` : "[조항 밖]"} {h.doc_title}</strong>
          <p style={{ margin: "4px 0", fontSize: 14 }}>{h.text.slice(0, 300)}</p>
        </div>
      ))}
    </section>
  );
}
```

`frontend/components/AskForm.tsx`:

```tsx
"use client";

import { useState } from "react";
import Answer, { type AskResult } from "./Answer";
import PersonaPicker from "./PersonaPicker";

export default function AskForm() {
  const [query, setQuery] = useState("");
  const [persona, setPersona] = useState("김개발");
  const [result, setResult] = useState<AskResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, persona }),
      });
      if (!r.ok) throw new Error(`요청이 실패했습니다 (${r.status})`);
      setResult(await r.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <form onSubmit={submit}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="예: 비밀번호는 얼마나 자주 바꿔야 하나"
          required
          maxLength={500}
          style={{ width: "100%", padding: 8, fontSize: 16 }}
        />
        <PersonaPicker value={persona} onChange={setPersona} />
        <button type="submit" disabled={loading} style={{ marginTop: 12, padding: "8px 16px" }}>
          {loading ? "찾는 중…" : "묻기"}
        </button>
      </form>
      {loading && (
        <p style={{ color: "#666", fontSize: 14 }}>
          처음 요청은 백엔드가 잠들어 있었다면 모델을 올리느라 수십 초 걸릴 수 있습니다.
        </p>
      )}
      {error && <p style={{ color: "#b00" }}>{error}</p>}
      {result && <Answer result={result} />}
    </>
  );
}
```

- [ ] **Step 5: 👤 사람이 하는 단계 — 구글 OAuth 리디렉션 URI 를 등록한다**

이미 발급받은 OAuth 클라이언트에 **승인된 리디렉션 URI** 를 더한다. Google Cloud Console → API 및 서비스 → 사용자 인증 정보 → 해당 OAuth 2.0 클라이언트 ID:

```
http://localhost:3000/api/auth/callback/google
```

배포 도메인용 URI 는 Task 8 에서 더한다(그때 도메인을 알게 된다).

그리고 `frontend/.env.local` 을 만든다(`.gitignore` 에 있다):

```
AUTH_SECRET=<openssl rand -base64 32 의 출력>
AUTH_GOOGLE_ID=<클라이언트 ID>
AUTH_GOOGLE_SECRET=<클라이언트 시크릿>
BACKEND_URL=http://localhost:8080
BACKEND_SHARED_SECRET=로컬개발용시크릿
```

`BACKEND_SHARED_SECRET` 은 `docker-compose.yml` 에 쓴 값과 **정확히 같아야 한다.**

- [ ] **Step 6: 로컬에서 끝까지 돌린다**

```bash
cd /Users/ryujun/Documents/secu-agent
docker compose up -d
cd frontend && npm run dev
```

브라우저에서 `http://localhost:3000` 을 연다.

Expected:
1. 로그인 화면이 뜬다
2. 구글로 로그인하면 질의 화면이 나온다
3. "비밀번호는 얼마나 자주 바꿔야 하나" 를 김개발로 물으면 답변과 근거가 나온다
4. **페르소나를 최임원으로 바꿔 "임원 성과급은 어떤 기준으로 정해지나" 를 물으면 `6.1.1` 이 근거에 뜬다. 김개발로 같은 질문을 하면 뜨지 않는다.**

4번이 이 프로젝트의 핵심 장면이다. 안 되면 멈추고 보고한다.

- [ ] **Step 7: 로그인 없이 API 가 막히는지 확인한다**

시크릿 창(로그아웃 상태)에서:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:3000/api/ask \
  -H "Content-Type: application/json" -d '{"query":"질문","persona":"최임원"}'
```
Expected: `401`

- [ ] **Step 8: 커밋한다**

```bash
cd /Users/ryujun/Documents/secu-agent
git add frontend/
git commit -m "Next.js 프론트와 구글 로그인을 더했다

브라우저는 Vercel 하고만 통신한다. Route Handler 가 세션을 확인한 뒤
공유 시크릿으로 백엔드를 부른다 — CORS 도, 크로스도메인 쿠키도, 공개된
백엔드도 없다. 백엔드 주소와 시크릿이 브라우저에 내려가지 않는다.

로그인의 일차 목적은 권한이 아니라 요금 게이트다. /ask 뒤에는 LLM 이
있어서 열어두면 아무나 요금을 태울 수 있다.

페르소나 선택기 옆에 무엇이 진짜이고 무엇이 시연 장치인지 적었다 —
인증은 실제 OAuth, 부서·등급은 고르는 값, 권한 강제는 진짜다.

next-auth 를 5.0.0-beta.32 로 고정했다. App Router 용 v5 는 아직 beta 이고
@beta 태그는 떠다녀서 배포가 어느 날 조용히 달라질 수 있다."
```

---

### Task 6: 👤 외부 자원 준비

**Files:** 없음 (계정과 설정)

이 태스크는 **전부 사람이 한다.** 에이전트는 여기서 멈추고, 아래 값들을 받은 뒤 Task 7 로 넘어간다.

- [ ] **Step 1: Neon 에 Postgres 를 만든다**

`https://neon.tech` 에서 프로젝트를 만들고 **Postgres 16** 을 고른다. 연결 문자열을 받아둔다:

```
postgresql://<user>:<password>@<host>/<db>?sslmode=require
```

- [ ] **Step 2: pgvector 확장을 켜고 스키마를 올린다**

Neon 콘솔의 SQL Editor 또는 로컬에서:

```bash
cd /Users/ryujun/Documents/secu-agent/backend
SECUAGENT_DSN='<neon 연결 문자열>' .venv/bin/python -c "
from adapters.db.connection import connect, apply_schema
import os
c = connect(os.environ['SECUAGENT_DSN'])
apply_schema(c)
print('스키마 적용 완료')
c.close()"
```

`db/schema.sql` 첫 줄이 `CREATE EXTENSION IF NOT EXISTS vector` 라 확장도 함께 켜진다. 실패하면 Neon 콘솔에서 `CREATE EXTENSION vector;` 를 먼저 실행한다.

- [ ] **Step 3: 코퍼스를 적재한다**

```bash
cd /Users/ryujun/Documents/secu-agent/backend
export SECUAGENT_DSN='<neon 연결 문자열>'
.venv/bin/python -m pipeline.cli ingest ../data/raw/ismsp.pdf --title "ISMS-P 인증기준 안내서"
.venv/bin/python -m pipeline.cli ingest-dir ../data/policies
.venv/bin/python -m pipeline.cli seed-principals
unset SECUAGENT_DSN
```

Expected: 9문서 · 126조항 · 338청크, 계정 3개. 로컬 컨테이너와 같은 수여야 한다.

- [ ] **Step 4: Cloudflare Workers Paid 를 활성화한다**

Containers 는 Workers Paid($5/월)를 요구한다. `https://dash.cloudflare.com` → Workers & Pages → 요금제.

- [ ] **Step 5: 값을 모아둔다**

Task 7·8 이 이 값들을 쓴다.

| 이름 | 어디서 | 어디에 쓰나 |
|---|---|---|
| `SECUAGENT_DSN` | Neon | Cloudflare 시크릿 |
| `GOOGLE_CLOUD_PROJECT` | Cloud Console | Cloudflare 시크릿 |
| `GCP_SA_JSON` | 서비스 계정 JSON 파일 **내용 전체** | Cloudflare 시크릿 |
| `BACKEND_SHARED_SECRET` | `openssl rand -base64 32` 로 새로 만든다 | Cloudflare 시크릿 + Vercel 환경변수 (**같은 값**) |
| `AUTH_SECRET` | `openssl rand -base64 32` | Vercel 환경변수 |
| `AUTH_GOOGLE_ID` / `AUTH_GOOGLE_SECRET` | 기존 OAuth 클라이언트 | Vercel 환경변수 |

**로컬 개발용 시크릿을 배포에 재사용하지 않는다.** `BACKEND_SHARED_SECRET` 은 새로 만든다.

---

### Task 7: Cloudflare 배포

**Files:**
- Create: `infra/package.json`, `infra/wrangler.jsonc`, `infra/worker.ts`, `infra/tsconfig.json`
- Modify: `backend/Dockerfile` (없으면 그대로)

**Interfaces:**
- Consumes: `backend/Dockerfile` (Task 4), Task 6 의 값들
- Produces: 공개된 백엔드 URL — `https://<worker>.<subdomain>.workers.dev`

- [ ] **Step 1: infra 를 스캐폴딩한다**

```bash
mkdir -p infra && cd infra
npm init -y
npm i @cloudflare/containers
npm i -D wrangler@4 typescript @cloudflare/workers-types
```

`infra/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "es2022",
    "lib": ["es2022"],
    "module": "es2022",
    "moduleResolution": "bundler",
    "types": ["@cloudflare/workers-types"],
    "strict": true,
    "noEmit": true
  },
  "include": ["worker.ts"]
}
```

- [ ] **Step 2: Worker 를 쓴다**

`infra/worker.ts`:

```ts
import { Container } from "@cloudflare/containers";

export class BackendContainer extends Container {
  // Dockerfile 의 EXPOSE / uvicorn 포트와 같아야 한다.
  defaultPort = 8080;

  // 기본값(10초)은 이 백엔드에 너무 짧다. 깨어날 때마다 임베딩 모델을
  // 다시 올려야 해서 수십 초가 걸린다. 시연 한 세션 동안은 깨어 있게 둔다.
  sleepAfter = "10m";
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // 인스턴스를 하나만 쓴다. 여러 개로 늘리면 각각이 모델을 따로 올려
    // 메모리와 cold start 가 배로 든다.
    const container = env.BACKEND.getByName("singleton");
    return container.fetch(request);
  },
};

interface Env {
  BACKEND: DurableObjectNamespace<BackendContainer>;
}
```

- [ ] **Step 3: wrangler 설정을 쓴다**

`infra/wrangler.jsonc`:

```jsonc
{
  "$schema": "node_modules/wrangler/config-schema.json",
  "name": "secu-agent-backend",
  "main": "worker.ts",
  "compatibility_date": "2026-09-01",

  "containers": [
    {
      "class_name": "BackendContainer",
      // wrangler.jsonc 기준 상대 경로다.
      "image": "../backend/Dockerfile",
      "instance_type": "standard",
      // 하나만 띄운다. 모델을 올리는 컨테이너를 여러 개 두면
      // 메모리도 cold start 도 배로 든다.
      "max_instances": 1
    }
  ],

  "durable_objects": {
    "bindings": [{ "name": "BACKEND", "class_name": "BackendContainer" }]
  },

  // new_classes 가 아니라 new_sqlite_classes 다. 틀리면 배포가 거부된다.
  "migrations": [{ "tag": "v1", "new_sqlite_classes": ["BackendContainer"] }]
}
```

- [ ] **Step 4: 👤 사람이 하는 단계 — 로그인하고 시크릿을 넣는다**

```bash
cd /Users/ryujun/Documents/secu-agent/infra
npx wrangler login
npx wrangler secret put SECUAGENT_DSN
npx wrangler secret put GOOGLE_CLOUD_PROJECT
npx wrangler secret put GCP_SA_JSON   # JSON 파일 내용을 통째로 붙여넣는다
npx wrangler secret put BACKEND_SHARED_SECRET
```

각각 Task 6 Step 5 의 값을 붙여넣는다. **시크릿은 `wrangler.jsonc` 에 쓰지 않는다** — 그 파일은 커밋된다.

- [ ] **Step 5: 배포한다**

```bash
cd /Users/ryujun/Documents/secu-agent/infra
npx wrangler deploy
```

이미지 빌드와 푸시에 몇 분 걸린다. 출력의 URL 을 기록한다.

**흔한 실패와 대응:**

| 증상 | 원인 | 대응 |
|---|---|---|
| `new_classes` 관련 오류 | `new_sqlite_classes` 를 안 씀 | 설정을 고친다 |
| 컨테이너가 OOM 으로 죽는다 | `standard` 인스턴스가 모델에 모자람 | `instance_type` 을 더 큰 것으로 올린다. 상한은 4 vCPU · 12 GiB |
| Workers Paid 필요 오류 | Task 6 Step 4 미완 | 요금제를 켠다 |
| 이미지 푸시가 느림/실패 | 이미지가 큼 | Task 4 Step 3 에서 잰 크기를 확인한다. CPU 전용 torch 를 썼는지 본다 |

**서비스 계정 자격증명을 컨테이너에 넣는 법.** `wrangler secret` 은 문자열만 받고 파일을 못 넣는다. JSON 내용 전체를 `GCP_SA_JSON` 시크릿으로 넣은 뒤, 컨테이너가 시작할 때 그것을 파일로 써서 `GOOGLE_APPLICATION_CREDENTIALS` 가 가리키게 한다. Dockerfile 의 `CMD` 를 작은 엔트리포인트 스크립트로 바꿔 그 일을 시킨다 — 로컬 compose 는 파일을 직접 마운트하므로 스크립트가 `GCP_SA_JSON` 이 없으면 아무것도 하지 않고 넘어가야 한다.

- [ ] **Step 6: 스모크 테스트한다**

```bash
URL=https://<배포된 주소>
curl -s $URL/healthz
```
Expected: `{"status":"ok","db":true,"model":"ready"}` — 첫 호출은 컨테이너가 깨어나느라 수십 초 걸린다.

```bash
curl -s -X POST $URL/ask \
  -H "Content-Type: application/json" \
  -H "X-Backend-Secret: <BACKEND_SHARED_SECRET>" \
  -d '{"query":"임원 성과급은 어떤 기준으로 정해지나","persona":"최임원"}' | python3 -m json.tool
```
Expected: `hits` 에 `6.1.1` 이 있다.

**같은 질의를 `김개발` 로 던진다.** `6.1.1` 이 **없어야** 한다. 있으면 권한 필터가 배포 환경에서 안 걸린 것이다 — 멈추고 보고한다.

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST $URL/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"질문","persona":"김개발"}'
```
Expected: `401`

- [ ] **Step 7: 커밋한다**

```bash
cd /Users/ryujun/Documents/secu-agent
echo "node_modules/" > infra/.gitignore
git add infra/ && git commit -m "Cloudflare Container 로 백엔드를 배포했다

Workers 런타임은 torch 를 못 돌린다. Containers 는 Dockerfile 이면 무엇이든
받고 이미지 상한이 20GB 라 3GB 짜리 이 이미지에 여유가 크다.

sleepAfter 를 10분으로 뒀다. 기본값 10초는 이 백엔드에 너무 짧다 —
깨어날 때마다 임베딩 모델을 다시 올려 수십 초가 걸린다.

인스턴스를 하나만 띄운다. 여러 개면 각각이 모델을 따로 올려 메모리도
cold start 도 배로 든다.

migrations 는 new_sqlite_classes 다. new_classes 로 쓰면 배포가 거부된다."
```

---

### Task 8: Vercel 배포와 문서 갱신

**Files:**
- Modify: `README.md`, `jekyll/verification.markdown`
- Create: `frontend/vercel.json` (필요 시)

**Interfaces:**
- Consumes: Task 7 의 백엔드 URL
- Produces: 공개된 프론트 URL — 이력서에 거는 그것

- [ ] **Step 1: 👤 사람이 하는 단계 — Vercel 에 붙인다**

`https://vercel.com` → Add New Project → 이 저장소를 import.

| 설정 | 값 |
|---|---|
| Root Directory | `frontend` |
| Framework Preset | Next.js |

환경변수를 넣는다:

```
AUTH_SECRET=<openssl rand -base64 32>
AUTH_GOOGLE_ID=<클라이언트 ID>
AUTH_GOOGLE_SECRET=<클라이언트 시크릿>
BACKEND_URL=<Task 7 의 백엔드 URL>
BACKEND_SHARED_SECRET=<Task 6 에서 만든 값 — Cloudflare 에 넣은 것과 같아야 한다>
```

배포하고 도메인을 받는다.

- [ ] **Step 2: 👤 사람이 하는 단계 — 구글 리디렉션 URI 를 더한다**

Google Cloud Console 의 같은 OAuth 클라이언트에 배포 도메인을 더한다:

```
https://<vercel 도메인>/api/auth/callback/google
```

**이걸 빠뜨리면 배포된 사이트에서 로그인이 `redirect_uri_mismatch` 로 실패한다.** 로컬은 멀쩡하므로 발견이 늦다.

- [ ] **Step 3: 배포된 사이트를 끝까지 확인한다**

브라우저에서 Vercel 도메인을 연다.

1. 로그인 화면이 뜬다
2. 구글 로그인이 성공한다
3. `최임원` 으로 "임원 성과급은 어떤 기준으로 정해지나" → 근거에 `6.1.1`
4. `김개발` 로 같은 질문 → `6.1.1` 이 **없다**
5. 시크릿 창에서 `POST /api/ask` 를 직접 부르면 401

3·4번이 이 프로젝트의 핵심 장면이다. 스크린샷을 남긴다.

- [ ] **Step 4: README 를 갱신한다**

`README.md` 맨 위 `📄 **문서 사이트**` 줄 **아래**에 더한다. `<...>` 는 실제 값으로 채운다.

````markdown
🔗 **데모** — <Vercel URL> (구글 로그인 필요)

로그인은 요금 게이트입니다 — `/ask` 뒤에 LLM 이 있어 열어두면 누구나 API 요금을
태울 수 있습니다. 로그인한 뒤 세 페르소나를 바꿔가며 같은 질문을 던지면 결과가
달라집니다. **인증은 실제 구글 OAuth 이고, 부서·등급은 시연을 위해 고르는 값이며,
고른 값이 실제 권한 필터를 그대로 탑니다.**

백엔드는 유휴 시 잠듭니다. 첫 요청은 임베딩 모델을 올리느라 수십 초 걸립니다.
````

그리고 `## 구조` 절 **아래**에 배포 구성을 더한다:

````markdown
## 배포

```
Vercel (Next.js · 구글 로그인 · BFF)
   │  브라우저는 여기하고만 통신합니다
Cloudflare Container (FastAPI · e5 · LangGraph)
   │
Neon (PostgreSQL 16 + pgvector)
   │
Gemini API (gemini-3.7-flash)
```

브라우저는 백엔드 주소도 공유 시크릿도 받지 않습니다. Next.js Route Handler 가
세션을 확인한 뒤 대신 호출합니다 — CORS 도, 크로스도메인 쿠키도, 공개된 백엔드도
없습니다.
````

- [ ] **Step 5: 검증 페이지에 W3 기록을 남긴다**

`jekyll/verification.markdown` 의 **갖춘 장치** 표에 행을 하나 더한다:

```markdown
| **도구 스키마 검사** | `principal` 이 LLM 에게 노출되는 것 | 매 커밋 (CI) |
```

그리고 `### Access Control 누출 테스트` 절 **뒤에** 새 절을 더한다:

````markdown
### 도구 스키마 검사

에이전트가 도구를 부를 때, 그 도구가 어떤 인자를 받는지는 **LLM 이 봅니다.**
`principal` 이 그 목록에 있으면 LLM 이 `clearance: 3` 을 써넣을 수 있습니다.

```python
def test_principal_이_도구_스키마에_없다():
    스키마 = 도구.tool_call_schema.model_json_schema()
    assert 필드 == {"query", "k"}
```

**이 사고는 조용합니다.** `principal` 이 스키마에 새어 들어와도 에이전트는 멀쩡히
답하고, 권한 필터도 여전히 동작하며(LLM 이 준 값으로), 나머지 테스트는 전부
통과합니다. 스키마를 직접 들여다보는 테스트가 아니면 아무도 모릅니다.

#### 장치가 잡은 것 ⑥: 검사할 스키마가 두 개였다

LangChain 의 도구는 스키마를 두 개 갖습니다. `args_schema` 는 함수의 전체
시그니처이고, `tool_call_schema` 는 **모델에게 실제로 전달되는 것**입니다.
`args_schema` 에는 숨긴 인자가 그대로 남아 있습니다.

`args_schema` 를 검사했다면 이 테스트는 아무것도 지키지 못했을 것입니다.
게다가 `args_schema.model_json_schema()` 는 예외를 던집니다 — 런타임 객체가
직렬화할 수 없는 필드를 갖고 있기 때문입니다. 계획을 쓰기 전에 실제로
설치해 두 스키마를 출력해보고 알았습니다.

#### 장치가 잡은 것 ⑦: 기억으로 쓴 API 가 둘 다 틀렸다

설계 문서는 "LangChain 1.x API 를 기억으로 쓰면 막힌다"를 최상위 리스크로
적어두었습니다. 계획을 쓰기 전에 실제로 설치해 확인했고, 둘이 틀렸습니다.

| | 기억 | 실제 |
|---|---|---|
| 에이전트 생성 | `create_react_agent` | deprecated. `langchain.agents.create_agent` |
| 반복 상한 | `recursion_limit` 인자 | 그런 인자가 없음. `ToolCallLimitMiddleware` |

그리고 상한을 넘겼을 때의 동작이 세 가지였습니다. 설계 문서가 요구한
"중단하고 그때까지의 결과로 답한다"에 맞는 것은 그중 하나(`continue`)뿐이고,
이름만 보고 고르면 틀릴 자리였습니다.
````

- [ ] **Step 6: 커밋한다**

```bash
cd /Users/ryujun/Documents/secu-agent
git add README.md jekyll/verification.markdown
git commit -m "배포 URL 과 W3 검증 기록을 문서에 남겼다

README 에 데모 URL 과 배포 구성을 적었다. 로그인이 권한이 아니라 요금
게이트라는 것, 부서·등급은 고르는 값이라는 것, 백엔드가 잠들어 첫 요청이
느리다는 것을 감추지 않고 적었다.

검증 페이지에 도구 스키마 검사를 더했다. principal 이 스키마에 새어
들어와도 에이전트는 멀쩡히 답하고 나머지 테스트도 전부 통과한다 —
스키마를 직접 보는 테스트가 아니면 잡히지 않는다.

장치가 잡은 것 두 가지를 기록했다. 검사할 스키마가 두 개였다는 것과,
기억으로 쓴 LangChain API 가 둘 다 틀렸다는 것."
```

---

## 완료 조건

**국면 A (로컬)**

- [ ] `.venv/bin/python -m pytest -q` 가 DB·LLM 없이 전부 통과한다
- [ ] `.venv/bin/python -m pytest -m db -v` 가 통과한다 (돌린 뒤 코퍼스를 재적재했다)
- [ ] `ruff check .` · `ruff format --check .` 가 exit 0 이다
- [ ] `test_principal_이_도구_스키마에_없다` 가 **실제로 잡는다** — 인자를 하나 더해 실패를 보고 되돌렸다
- [ ] `test_권한_밖_항목이_섞이면_예외가_난다` 가 **실제로 잡는다** — `enforce` 를 빼고 실패를 보고 되돌렸다
- [ ] 경계 테스트가 `core/agent/tools.py` 의 `import langchain` 을 **실제로 잡는다** — 넣어보고 실패를 확인한 뒤 지웠다
- [ ] `docker compose up -d` 로 백엔드가 뜨고 `/healthz` 가 `{"status":"ok","db":true,"model":"ready"}` 를 낸다
- [ ] 로컬에서 `최임원` 과 `김개발` 의 `/ask` 결과가 다르다
- [ ] `pytest -m llm` 이 키가 있으면 통과하고, 없으면 skip 된다 (기본 스위트를 깨지 않는다)

**국면 B (배포)**

- [ ] Neon 에 9문서 · 126조항 · 338청크가 적재됐다
- [ ] 배포된 백엔드 `/healthz` 가 200 이다
- [ ] 배포된 백엔드에서 `최임원` 은 `6.1.1` 을 받고 `김개발` 은 못 받는다
- [ ] 시크릿 없는 백엔드 호출이 401 이다
- [ ] Vercel 도메인에서 구글 로그인이 성공한다 (리디렉션 URI 등록 완료)
- [ ] 로그인 없이 `/api/ask` 를 부르면 401 이다
- [ ] 배포된 사이트에서 페르소나를 바꾸면 근거가 달라진다
- [ ] `README.md` 에 실제 데모 URL 이 들어갔다 (`<...>` 자리표시자가 남아 있지 않다)
- [ ] `jekyll/verification.markdown` 에 도구 스키마 검사와 장치가 잡은 것 ⑥·⑦ 이 들어갔다

## 다음 계획으로 넘길 것

- **`query_logs` · `draft_report`** (W4) — 도구 등록·상한·컨텍스트 주입 구조가 이번에 다 들어가므로 꽂기만 하면 된다
- **`verify_clauses`** (W4) — 인용 실재 검증. `clauses` 테이블의 코드 집합이 정답이다. 리포트가 생겨야 검증할 대상이 있다
- **로그 파이프라인** (W4) — `log_events` 스키마는 W1 부터 있다. 부서별 허용 호스트 매핑이 아직 없다
- **cold start** — `sleepAfter=10m` 로 완화했을 뿐 없애지 못했다. 없애려면 임베딩을 외부로 빼야 하고 그러면 검색 품질을 다시 재야 한다
- **스트리밍 응답** — BFF 한 겹을 더 복잡하게 만들어 이번 주에 뺐다
- **DB 픽스처가 작업용 코퍼스를 파괴한다** (W2 이월) — 실행 순서로 회피 중이다. 별도 데이터베이스가 근본 해법이다
- **`demo` CLI 출력의 조항 중복** (W2 이월, Ruling R12) — `hybrid.search` 가 조항이 아니라 청크 단위로 상위 k 를 준다
- **진짜 부서·등급 매핑** — 이메일 알리스트로 등급을 부여하면 권한이 끝까지 진짜가 되지만, 방문자가 이 프로젝트의 핵심 장면을 볼 수 없게 된다 (spec §3.1)

# W3b 구현 계획 — 프론트엔드 전체 화면과 관리자 대시보드

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 디자인 핸드오프의 7개 화면을 Next.js 로 구현하되, **지어낸 데이터를 화면에 두지 않는다.** 목 데이터로 그려진 곳은 진짜 데이터를 만들어 채우거나, 아직 없다는 사실을 명시한다.

**Architecture:** 디자인 시스템(`frontend/app/_ds/industry.css`)의 토큰과 클래스를 그대로 쓴다. 브라우저는 Vercel 하고만 통신하고 Route Handler 가 세션 확인 후 백엔드를 부르는 BFF 구조를 유지한다. 문서·계정·열람 이력은 백엔드에 읽기 엔드포인트를 더해 **실제 DB** 를 보여준다. 감사 로그(W4)는 핸드오프 설계대로 "Planned + 빈 상태"로 둔다.

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript, Auth.js 5.0.0-beta.32, FastAPI, psycopg 3

**Handoff:** `docs/handoff/2026-09-01-frontend-handoff.md` · 프로토타입 `docs/handoff/prototype.dc.html`
**Spec:** `docs/superpowers/specs/2026-09-01-w3-deployment-design.md`
**상위 Spec:** `docs/superpowers/specs/2026-08-31-secu-agent-design.md`

**선행:** W3 국면 A 완료 (에이전트·API·컨테이너·최소 프론트). 브랜치 `feat/w3-agent-api-deploy` 위에 이어짐.

## Global Constraints

- Python 3.12+. 백엔드 명령은 `backend/` 에서 `.venv/bin/python`.
- 프론트 명령은 `frontend/` 에서 `npm`.
- **`core/` 는 바깥 계층·인프라·프레임워크를 import 하지 않는다.** `backend/tests/test_boundaries.py` 가 강제한다.
- 경계 인터페이스는 `core/ports.py` 가 소유한다. `adapters/` 가 구현한다.
- 테스트 함수 이름은 한국어. 커밋 메시지는 한국어 평서형(`~했다`).
- 마커 `db`·`model`·`llm` 은 기본 스위트에서 제외된다.
- **`pytest -m db` 는 적재된 코퍼스(9문서·126조항·338청크·계정3)를 파괴한다.** 돌린 뒤 재적재한다.
- **하드코딩 금지.** 색·간격·타이포는 `industry.css` 의 CSS 변수를 쓴다.
- **`.blueprint` 에는 코너 마크 4개(`<i class="corner tl|tr|bl|br">`)를 반드시 넣는다.**
- 브라우저에 백엔드 주소나 공유 시크릿이 내려가면 안 된다. `NEXT_PUBLIC_` 접두어를 쓰지 않는다.

---

## 이 계획이 핸드오프를 따르지 않는 지점과 그 이유

핸드오프는 high-fidelity 목업이고 대부분 그대로 구현한다. **네 곳에서 벗어난다.**

### ① 관리자 대시보드의 지어낸 숫자를 쓰지 않는다

프로토타입은 `이번 주 질의 342 · 열람된 서류 128 · 차단된 요청 17` 과 8행짜리 열람 이력, 3행짜리 권한 알림을 목 데이터로 갖고 있다. **그 사건들은 일어난 적이 없다.** `log_events` 는 비어 있고 열람을 기록하는 코드가 없다. 핸드오프도 그렇게 적었다.

이 프로젝트의 두 번째 산출물은 검증 체계다(상위 spec §1.2). 재현되지 않는 p95 를 README 에서 뺐고, 검증 페이지의 거짓 문장 하나를 최종 리뷰가 고쳤다. 그 옆에 지어낸 숫자를 두면 검증 페이지의 신뢰가 함께 깎인다.

**대신 실제로 기록한다.** `/ask` 가 처리한 질의를 남기고 관리자 화면이 그것을 읽는다. 시연하는 동안 화면이 채워진다.

### ② 기록에는 식별자만 담는다

`core/agent/policy.py` 의 `AccessViolation` 이 메시지에 `chunk_id` 만 담는 것과 같은 원칙이다. 열람 기록에 문서 본문을 담으면 그 테이블이 곧 우회 경로가 된다.

담는 것: 시각 · 페르소나 이름 · 부서 · 등급 · 질의문 · 조항 코드 · `chunk_id` · 성공 여부
담지 않는 것: 청크 본문 · 문서 제목

> 문서 제목을 빼는 이유: 제목만으로도 존재가 드러난다. "임원 성과급 산정 기준"이 로그에 있으면 그 문서의 존재가 확인된다.

### ③ 문서·계정 화면은 목이 아니라 실제 DB 를 읽는다

핸드오프는 `DOCS` 상수로 그렸지만 DB 에 실제 9문서가 등급·부서와 함께 있고 `principals` 에 3행이 있다. 진짜를 보여줄 수 있는데 목을 쓸 이유가 없다.

### ④ 관리자 역할 선택에 고지를 붙인다

핸드오프는 로그인 화면에서 `member`/`admin` 을 고르게 한다. 그러면 그것은 보안 경계가 아니라 화면 전환 스위치다. 페르소나에 붙인 고지와 같은 문장을 관리자 역할에도 붙인다 — 감추면 실제보다 강한 주장을 하게 된다.

## 핸드오프에 없어서 더하는 것

| 더하는 것 | 왜 |
|---|---|
| **남용 상한** | `/ask` 뒤에 LLM 이 있고 지금은 어떤 구글 계정이든 무제한이다. URL 공개 전 필수 |
| **cold start 안내** | 컨테이너가 잠들면 첫 요청이 수십 초. 핸드오프의 로딩 상태는 1.2초 가정이다 |
| **401 · 403 상태** | 502 만 정의돼 있다. 세션 만료와 상한 초과를 구분해 보여줘야 한다 |

---

## File Structure

```
backend/
  core/
    types.py                  (수정) AccessRecord 추가
    ports.py                  (수정) AccessLog · DocumentCatalog Protocol
  adapters/db/
    access_log.py             PgAccessLog — 열람 기록 쓰기·읽기
    catalog.py                PgDocumentCatalog — 문서 목록·계정 목록 읽기
  db/schema.sql               (수정) access_records 테이블
  api/
    schemas.py                (수정) 목록·이력 응답 타입
    main.py                   (수정) GET /documents · /principals · /access-log · 기록 삽입
  tests/
    test_access_log.py        기록이 본문을 담지 않는다 (db 마커)
    test_catalog.py           문서·계정 조회 (db 마커)
    test_api_readonly.py      새 엔드포인트 (스텁)
frontend/
  app/
    _ds/industry.css          (이미 있음) 디자인 시스템
    layout.tsx                (수정) 디자인 시스템 로드
    page.tsx                  (수정) 로그인 / 앱 셸 분기
    (app)/
      layout.tsx              앱 셸 — 사이드바 + 헤더
      ask/page.tsx            질의
      documents/page.tsx      문서 · 권한
      principals/page.tsx     계정
      logs/page.tsx           감사 로그 (Planned)
      admin/page.tsx          관리자 대시보드
    api/
      ask/route.ts            (수정) 남용 상한
      documents/route.ts      BFF
      principals/route.ts     BFF
      access-log/route.ts     BFF
  components/
    Blueprint.tsx             코너 마크 4개를 감싸는 래퍼
    SignIn.tsx                로그인 화면
    Sidebar.tsx  Header.tsx   앱 셸
    PersonaSegment.tsx        3분할 세그먼트
    AskPanel.tsx              질의 카드 + 상태
    Answer.tsx                (수정) 답변 + 근거 그리드
    RightRail.tsx             세 계정 요약 + 예시 질의
    DocumentTable.tsx  PrincipalTable.tsx
    AdminSummary.tsx  AlertTable.tsx  AccessTable.tsx  InquiryDialog.tsx
  lib/
    session.ts                역할 · 알리스트 판정
    rate-limit.ts             사용자당 일일 상한
    types.ts                  API 타입 (백엔드 계약 사본)
```

**책임 분리 근거:** `Blueprint.tsx` 를 따로 둔 것은 코너 마크 4개를 빠뜨리기 쉽기 때문이다 — 핸드오프가 "절대 빼지 마세요"라고 적은 것이 그 증거다. 한 곳에 가두면 빠뜨릴 수 없다. `lib/rate-limit.ts` 를 분리한 것은 상한 로직이 조용히 틀리기 쉬운 곳이고, 격리해야 그 테스트가 판별력을 갖기 때문이다.

---

### Task 1: 열람 기록 — 스키마 · 포트 · 어댑터 · `/ask` 기록

**Files:**
- Modify: `backend/db/schema.sql`, `backend/core/types.py`, `backend/core/ports.py`, `backend/api/main.py`, `backend/api/deps.py`, `backend/tests/test_types.py`
- Create: `backend/adapters/db/access_log.py`, `backend/tests/test_access_log.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Produces:
  - `core.types.AccessRecord(persona: str, department: str, clearance: int, query: str, clause_code: str | None, chunk_id: int, allowed: bool)`
  - `core.ports.AccessLog.record(rows: Sequence[AccessRecord]) -> int` · `.recent(limit: int) -> list[AccessRecord]` · `.violations(limit: int) -> list[AccessRecord]`
  - `adapters.db.access_log.PgAccessLog(conn)`

**관리자 대시보드가 지어낸 숫자를 쓰지 않으려면 진짜 기록이 있어야 한다.** 이 태스크가 그것을 만든다.

> **주의 — 이 프로젝트가 두 번 밟은 함정.** `core/ports.py` 의 Protocol 은 `@runtime_checkable` 이고 `tests/test_types.py::test_포트를_스텁이_만족한다` 가 로컬 스텁을 `isinstance` 로 검사한다. `AccessLog` 를 더하면 그 테스트에 스텁도 함께 더해야 한다.

- [ ] **Step 1: 스키마를 더한다**

`backend/db/schema.sql` 의 `principals` 테이블 **아래**에 넣는다:

```sql
-- 열람 기록. 관리자 대시보드가 이것을 읽는다.
--
-- **본문과 문서 제목을 담지 않는다.** core/agent/policy.py 의 AccessViolation 이
-- 메시지에 chunk_id 만 담는 것과 같은 원칙이다 — 기록이 우회 경로가 되면 안 된다.
-- 제목을 빼는 이유: 제목만으로도 존재가 드러난다. "임원 성과급 산정 기준" 이
-- 로그에 있으면 그 문서의 존재가 확인된다.
CREATE TABLE IF NOT EXISTS access_records (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    persona     TEXT NOT NULL,
    department  TEXT NOT NULL,
    clearance   INT  NOT NULL,
    query       TEXT NOT NULL,
    clause_code TEXT,
    chunk_id    BIGINT NOT NULL,
    allowed     BOOLEAN NOT NULL
);

CREATE INDEX IF NOT EXISTS access_records_ts_idx ON access_records (ts DESC);
CREATE INDEX IF NOT EXISTS access_records_allowed_idx ON access_records (allowed);
```

- [ ] **Step 2: 도메인 타입을 더한다**

`backend/core/types.py` 의 `PolicyHit` **아래**에 넣는다:

```python
@dataclass(frozen=True)
class AccessRecord:
    """열람 기록 한 줄. 관리자 대시보드가 읽는다.

    text 도 doc_title 도 없다. 기록이 문서 본문이나 제목을 담으면 그 테이블이
    곧 권한 우회 경로가 된다 — 제목만으로도 존재가 드러난다.
    """

    persona: str
    department: str
    clearance: int
    query: str
    clause_code: str | None
    chunk_id: int
    allowed: bool
```

- [ ] **Step 3: 포트를 더한다**

`backend/core/ports.py` 의 `PrincipalStore` **아래**에 넣고, 맨 위 import 에 `AccessRecord` 를 더한다:

```python
@runtime_checkable
class AccessLog(Protocol):
    def record(self, rows: Sequence[AccessRecord]) -> int:
        """열람 기록을 저장하고 저장한 수를 돌려준다.

        기록 실패가 요청을 실패시키면 안 된다 — 호출자가 예외를 삼킨다.
        """
        ...

    def recent(self, limit: int) -> list[AccessRecord]:
        """최근 열람 기록. 시각 내림차순."""
        ...

    def violations(self, limit: int) -> list[AccessRecord]:
        """allowed=False 인 기록만. 권한 밖 요청 알림에 쓴다."""
        ...
```

`backend/tests/test_types.py` 의 `test_포트를_스텁이_만족한다` 안, `주체저장소` 아래에 스텁을 더하고 단언도 더한다:

```python
    class 열람기록:
        def record(self, rows):
            return len(rows)

        def recent(self, limit):
            return []

        def violations(self, limit):
            return []
```

```python
    assert isinstance(열람기록(), AccessLog)
```

같은 파일 맨 위 import 에 `AccessLog` 를 더한다.

- [ ] **Step 4: 실패하는 어댑터 테스트를 쓴다**

`backend/tests/test_access_log.py`:

```python
"""열람 기록 어댑터.

docker compose up -d
.venv/bin/python -m pytest -m db tests/test_access_log.py -v
"""

import os

import pytest

from adapters.db.access_log import PgAccessLog
from adapters.db.connection import apply_schema, connect
from core.ports import AccessLog
from core.types import AccessRecord

pytestmark = pytest.mark.db

DSN = os.environ.get("SECUAGENT_DSN", "postgresql://secuagent:secuagent@localhost:5433/secuagent")


@pytest.fixture
def log():
    conn = connect(DSN)
    apply_schema(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE access_records RESTART IDENTITY")
    conn.commit()
    yield PgAccessLog(conn)
    conn.close()


def _rec(chunk_id=1, allowed=True, code="2.6.1", persona="김개발"):
    return AccessRecord(
        persona=persona,
        department="개발팀",
        clearance=1,
        query="네트워크 접근 통제",
        clause_code=code,
        chunk_id=chunk_id,
        allowed=allowed,
    )


def test_구현이_포트를_만족한다(log):
    assert isinstance(log, AccessLog)


def test_기록하고_다시_읽는다(log):
    assert log.record([_rec(1), _rec(2)]) == 2
    읽은 = log.recent(10)
    assert {r.chunk_id for r in 읽은} == {1, 2}


def test_빈_목록은_아무것도_하지_않는다(log):
    assert log.record([]) == 0
    assert log.recent(10) == []


def test_최근_것이_먼저_온다(log):
    log.record([_rec(1)])
    log.record([_rec(2)])
    assert log.recent(10)[0].chunk_id == 2


def test_위반만_따로_읽는다(log):
    log.record([_rec(1, allowed=True), _rec(2, allowed=False)])
    위반 = log.violations(10)
    assert [r.chunk_id for r in 위반] == [2]
    assert all(r.allowed is False for r in 위반)


def test_기록에_본문_컬럼이_없다(log):
    """스키마에 본문·제목 컬럼이 있으면 언젠가 채워진다.

    기록이 문서 본문이나 제목을 담으면 그 테이블이 곧 권한 우회 경로가 된다 —
    제목만으로도 존재가 드러난다.
    """
    with log.conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'access_records'"
        )
        컬럼 = {r[0] for r in cur.fetchall()}
    for 금지 in ("text", "doc_title", "title", "body", "content"):
        assert 금지 not in 컬럼, f"기록 스키마에 {금지} 컬럼이 있다"
```

- [ ] **Step 5: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest -m db tests/test_access_log.py -q`
Expected: `ModuleNotFoundError: No module named 'adapters.db.access_log'`

- [ ] **Step 6: 어댑터를 구현한다**

`backend/adapters/db/access_log.py`:

```python
"""AccessLog 의 psycopg 구현.

기록은 요청 처리의 곁가지다 — 실패해도 요청을 죽이면 안 된다. 예외를
삼키는 것은 호출자(api/main.py)의 몫이고, 여기서는 정직하게 던진다.
"""

from collections.abc import Sequence

import psycopg

from core.types import AccessRecord

_열 = "persona, department, clearance, query, clause_code, chunk_id, allowed"


def _행에서(row) -> AccessRecord:
    return AccessRecord(
        persona=row[0],
        department=row[1],
        clearance=row[2],
        query=row[3],
        clause_code=row[4],
        chunk_id=row[5],
        allowed=row[6],
    )


class PgAccessLog:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def record(self, rows: Sequence[AccessRecord]) -> int:
        if not rows:
            return 0
        try:
            with self.conn.cursor() as cur:
                cur.executemany(
                    f"INSERT INTO access_records ({_열}) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    [
                        (r.persona, r.department, r.clearance, r.query,
                         r.clause_code, r.chunk_id, r.allowed)
                        for r in rows
                    ],
                )
            self.conn.commit()
            return len(rows)
        except Exception:
            self.conn.rollback()
            raise

    def recent(self, limit: int) -> list[AccessRecord]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT {_열} FROM access_records ORDER BY ts DESC, id DESC LIMIT %s",
                (limit,),
            )
            return [_행에서(r) for r in cur.fetchall()]

    def violations(self, limit: int) -> list[AccessRecord]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT {_열} FROM access_records WHERE allowed = FALSE "
                "ORDER BY ts DESC, id DESC LIMIT %s",
                (limit,),
            )
            return [_행에서(r) for r in cur.fetchall()]
```

- [ ] **Step 7: 통과를 확인하고 코퍼스를 되살린다**

```bash
cd backend
.venv/bin/python -m pytest -m db tests/test_access_log.py -v
```
Expected: 6개 PASS

`-m db` 를 돌렸으므로 코퍼스를 되살린다:

```bash
.venv/bin/python -c "
from adapters.db.connection import connect
c=connect()
with c.cursor() as cur: cur.execute('TRUNCATE documents RESTART IDENTITY CASCADE')
c.commit(); c.close()"
.venv/bin/python -m pipeline.cli ingest ../data/raw/ismsp.pdf --title "ISMS-P 인증기준 안내서"
.venv/bin/python -m pipeline.cli ingest-dir ../data/policies
.venv/bin/python -m pipeline.cli seed-principals
```

- [ ] **Step 8: `/ask` 가 기록하게 한다**

`backend/api/main.py` 의 `build_app` 시그니처에 인자를 하나 더한다:

```python
def build_app(
    에이전트_공장: Callable[[], object],
    주체저장소: PrincipalStore,
    모델_준비됨: Callable[[], bool],
    열람기록: AccessLog | None = None,
) -> FastAPI:
```

`ask` 핸들러에서 응답을 만들기 **직전**에 넣는다:

```python
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
```

`AccessRecord` 와 `AccessLog` 를 import 에 더한다.

> `allowed=True` 로 고정하는 이유: 여기 도달한 hit 은 이미 `enforce` 를 통과했다. `allowed=False` 기록은 다음 스텝이 만든다.

- [ ] **Step 9: 위반도 기록한다**

같은 핸들러에서 에이전트 호출을 `try` 로 감싼다:

```python
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
```

그리고 같은 파일에 헬퍼를 더한다:

```python
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
```

- [ ] **Step 10: API 테스트를 더한다**

`backend/tests/test_api.py` 에 스텁과 테스트를 더한다. 파일 상단 스텁 옆에:

```python
class 스텁열람기록:
    def __init__(self):
        self.기록 = []

    def record(self, rows):
        self.기록.extend(rows)
        return len(rows)

    def recent(self, limit):
        return list(reversed(self.기록))[:limit]

    def violations(self, limit):
        return [r for r in reversed(self.기록) if not r.allowed][:limit]
```

그리고 테스트:

```python
def test_질의가_열람_기록을_남긴다(monkeypatch):
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)
    기록 = 스텁열람기록()
    검색기 = 스텁검색기([_hit(1, "2.6.1")])
    저장소 = 스텁주체저장소({"박인사": Principal("인사팀", 2)})

    def 공장():
        모델 = 대본모델(대본=[
            AIMessage(content="", tool_calls=[{"name":"search_policy","args":{"query":"질의"},"id":"c1","type":"tool_call"}]),
            AIMessage(content="답변"),
        ])
        return build_agent(고정임베더(), 검색기, 모델)

    c = TestClient(build_app(공장, 저장소, lambda: True, 기록))
    c.post("/ask", json={"query": "네트워크 접근", "persona": "박인사"}, headers=헤더)

    assert 기록.기록, "기록이 남지 않았다"
    r = 기록.기록[0]
    assert r.persona == "박인사" and r.clearance == 2
    assert r.clause_code == "2.6.1" and r.allowed is True


def test_기록에_본문이_담기지_않는다():
    """AccessRecord 에 본문 필드가 있으면 언젠가 채워진다."""
    import dataclasses

    from core.types import AccessRecord

    필드 = {f.name for f in dataclasses.fields(AccessRecord)}
    for 금지 in ("text", "doc_title", "title", "body"):
        assert 금지 not in 필드, f"AccessRecord 에 {금지} 가 있다"


def test_기록이_실패해도_응답은_정상이다(monkeypatch):
    """기록은 곁가지다. 그것 때문에 질의가 실패하면 안 된다."""
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)

    class 터지는기록:
        def record(self, rows):
            raise RuntimeError("DB 연결 끊김")
        def recent(self, limit): return []
        def violations(self, limit): return []

    검색기 = 스텁검색기([_hit(1)])
    저장소 = 스텁주체저장소({"박인사": Principal("인사팀", 2)})

    def 공장():
        모델 = 대본모델(대본=[AIMessage(content="답변")])
        return build_agent(고정임베더(), 검색기, 모델)

    c = TestClient(build_app(공장, 저장소, lambda: True, 터지는기록()))
    r = c.post("/ask", json={"query": "질의", "persona": "박인사"}, headers=헤더)
    assert r.status_code == 200
```

기존 `build_app(...)` 호출이 있는 테스트들은 인자가 하나 늘었으므로 **전부 세 번째 인자 뒤에 아무것도 넘기지 않아도 된다**(`열람기록` 은 기본값 `None`). 확인만 한다.

- [ ] **Step 11: 조립부를 잇는다**

`backend/api/deps.py` 의 `create_app` 에서 `PgAccessLog` 를 만들어 넘긴다. 자원이 지연 생성이므로 클로저 안에서 만든다 — `create_app` 이 DB 를 건드리면 안 된다(이전 태스크의 결정).

```python
    class _지연열람기록:
        def record(self, rows):
            conn, _ = _자원()
            return PgAccessLog(conn).record(rows)

        def recent(self, limit):
            conn, _ = _자원()
            return PgAccessLog(conn).recent(limit)

        def violations(self, limit):
            conn, _ = _자원()
            return PgAccessLog(conn).violations(limit)
```

그리고 `build_app(..., 열람기록=_지연열람기록())` 으로 넘긴다.

- [ ] **Step 12: 변이 검사 — 기록 실패가 정말 삼켜지는가**

`api/main.py` 의 기록 블록에서 `try`/`except Exception: pass` 를 없애고 `열람기록.record(...)` 만 남긴다.

Run: `cd backend && .venv/bin/python -m pytest tests/test_api.py -q`
Expected: **`test_기록이_실패해도_응답은_정상이다` 가 FAIL** (500)

되돌리고 통과를 본다.

- [ ] **Step 13: 린트하고 커밋한다**

```bash
cd backend
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format .
.venv/bin/python -m pytest -q
cd /Users/ryujun/Documents/secu-agent
git add backend/ && git commit -m "열람 기록을 남기게 했다

관리자 대시보드가 지어낸 숫자를 쓰지 않으려면 진짜 기록이 있어야 한다.
디자인 핸드오프의 프로토타입은 '이번 주 질의 342 · 차단된 요청 17' 을 목
데이터로 갖고 있었는데 그 사건들은 일어난 적이 없다.

기록에 본문도 문서 제목도 담지 않는다. core/agent/policy.py 의
AccessViolation 이 메시지에 chunk_id 만 담는 것과 같은 원칙이다 — 제목만으로도
존재가 드러난다. 스키마와 dataclass 양쪽에서 금지 컬럼을 검사한다.

기록은 곁가지라 실패해도 요청을 죽이지 않는다. try/except 를 빼면
test_기록이_실패해도_응답은_정상이다 가 실패하는 것을 확인하고 되돌렸다."
```

---

### Task 2: 읽기 엔드포인트 — 문서 · 계정 · 열람 이력

**Files:**
- Modify: `backend/core/ports.py`, `backend/api/schemas.py`, `backend/api/main.py`, `backend/api/deps.py`, `backend/tests/test_types.py`
- Create: `backend/adapters/db/catalog.py`, `backend/tests/test_catalog.py`, `backend/tests/test_api_readonly.py`

**Interfaces:**
- Produces:
  - `core.ports.DocumentCatalog.documents() -> list[DocumentRow]` · `.principals() -> list[Principal named]`
  - `core.types.DocumentRow(id, title, doc_type, required_clearance, allowed_departments, source_path, chunk_count)`
  - `core.types.PrincipalRow(name, department, clearance)`
  - `GET /documents` · `GET /principals` · `GET /access-log?limit=N` · `GET /access-log/violations?limit=N` — 전부 공유 시크릿 필요

**핸드오프는 이 화면들을 목 데이터로 그렸지만 DB 에 진짜가 있다.** 9문서가 등급·부서와 함께, 계정 3행이. 진짜를 보여줄 수 있는데 목을 쓸 이유가 없다.

- [ ] **Step 1: 타입과 포트를 더한다**

`core/types.py` 에 `DocumentRow` 와 `PrincipalRow` 를 더한다. 둘 다 `frozen=True` dataclass 다.

```python
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
```

`core/ports.py` 에 Protocol 을 더하고 **`tests/test_types.py` 의 스텁도 함께 더한다**(이 프로젝트가 세 번 밟은 함정):

```python
@runtime_checkable
class DocumentCatalog(Protocol):
    def documents(self) -> list[DocumentRow]:
        """전체 문서 목록. 권한 필터를 적용하지 않는다 —

        문서 화면은 "이 페르소나에게 무엇이 보이는가"를 클라이언트가 계산해
        보여주는 화면이고, 그 계산의 입력이 필요하다. 검색 경로가 아니므로
        여기서 필터링하지 않는 것이 맞다. 대신 이 엔드포인트는 공유 시크릿
        뒤에 있고 본문을 돌려주지 않는다.
        """
        ...

    def principals(self) -> list[PrincipalRow]: ...
```

> **이 결정을 리뷰어가 볼 수 있게 적어둔다.** 문서 목록이 권한 필터를 안 타는 것은 의도다. 목록에는 제목과 등급만 있고 본문이 없으며, 화면의 목적이 "권한 규칙이 어떻게 적용되는지 보여주는 것" 이기 때문이다. 검색 결과였다면 반드시 필터링해야 한다.

- [ ] **Step 2: 어댑터 테스트를 쓰고 실패를 본다**

`backend/tests/test_catalog.py` — `db` 마커. 픽스처는 `TRUNCATE` 하지 말고 **실제 코퍼스를 읽는다**(이 테스트만 예외적으로 읽기 전용이다):

```python
"""문서·계정 목록 어댑터. 읽기 전용이라 코퍼스를 파괴하지 않는다."""

import os

import pytest

from adapters.db.catalog import PgDocumentCatalog
from adapters.db.connection import connect
from core.ports import DocumentCatalog

pytestmark = pytest.mark.db

DSN = os.environ.get("SECUAGENT_DSN", "postgresql://secuagent:secuagent@localhost:5433/secuagent")


@pytest.fixture
def catalog():
    conn = connect(DSN)
    yield PgDocumentCatalog(conn)
    conn.close()


def test_구현이_포트를_만족한다(catalog):
    assert isinstance(catalog, DocumentCatalog)


def test_문서_목록이_등급과_부서를_담는다(catalog):
    docs = catalog.documents()
    assert docs, "코퍼스가 비어 있다 — 적재 후 다시 돌린다"
    개발팀문서 = [d for d in docs if "개발팀" in d.allowed_departments]
    assert 개발팀문서, "부서 제한 문서가 없다"
    assert all(isinstance(d.required_clearance, int) for d in docs)


def test_전사_공개는_빈_튜플이다(catalog):
    """NULL 을 빈 튜플로 정규화한다 — core 의 규칙이 빈 튜플을 전사 공개로 읽는다."""
    docs = catalog.documents()
    전사 = [d for d in docs if d.allowed_departments == ()]
    assert 전사, "전사 공개 문서가 없다"


def test_청크_수가_함께_온다(catalog):
    assert all(d.chunk_count >= 0 for d in catalog.documents())
    assert sum(d.chunk_count for d in catalog.documents()) > 0


def test_계정_목록을_읽는다(catalog):
    names = {p.name for p in catalog.principals()}
    assert {"김개발", "박인사", "최임원"} <= names


def test_목록에_본문이_없다(catalog):
    """목록 응답에 본문이 섞이면 이 엔드포인트가 우회 경로가 된다."""
    import dataclasses

    from core.types import DocumentRow

    필드 = {f.name for f in dataclasses.fields(DocumentRow)}
    for 금지 in ("text", "body", "content", "chunks"):
        assert 금지 not in 필드
```

- [ ] **Step 3: 어댑터를 구현한다**

`backend/adapters/db/catalog.py`:

```python
"""DocumentCatalog 의 psycopg 구현. 읽기 전용이다.

본문을 돌려주지 않는다 — 목록 화면은 어떤 문서가 있고 누구에게 보이는지만
보여준다. 본문이 섞이면 이 엔드포인트가 검색을 우회하는 경로가 된다.
"""

import psycopg

from core.types import DocumentRow, PrincipalRow


class PgDocumentCatalog:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def documents(self) -> list[DocumentRow]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.id, d.title, d.doc_type, d.required_clearance,
                       d.allowed_departments, d.source_path, count(c.id)
                FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.id
                GROUP BY d.id
                ORDER BY d.source_path
                """
            )
            return [
                DocumentRow(
                    id=r[0],
                    title=r[1],
                    doc_type=r[2],
                    required_clearance=r[3],
                    # NULL 을 빈 튜플로 정규화한다 — core 의 규칙이 빈 튜플을
                    # 전사 공개로 읽는다.
                    allowed_departments=tuple(r[4] or ()),
                    source_path=r[5],
                    chunk_count=r[6],
                )
                for r in cur.fetchall()
            ]

    def principals(self) -> list[PrincipalRow]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT name, department, clearance FROM principals ORDER BY clearance, name"
            )
            return [PrincipalRow(name=r[0], department=r[1], clearance=r[2]) for r in cur.fetchall()]
```

- [ ] **Step 4: HTTP 타입과 엔드포인트를 더한다**

`backend/api/schemas.py` 에 응답 모델을 더한다 — `DocumentView`(도메인 `DocumentRow` 와 같은 필드), `PrincipalView`, `AccessRecordView`(`ts` 없이 도메인 필드 그대로), 그리고 각각의 목록 래퍼.

`backend/api/main.py` 에 네 엔드포인트를 더한다. **전부 `Depends(시크릿_검사)` 를 단다** — `/healthz` 만 예외다.

```python
    @app.get("/documents", dependencies=[Depends(시크릿_검사)])
    def documents() -> list[DocumentView]: ...

    @app.get("/principals", dependencies=[Depends(시크릿_검사)])
    def principals() -> list[PrincipalView]: ...

    @app.get("/access-log", dependencies=[Depends(시크릿_검사)])
    def access_log(limit: int = 50) -> list[AccessRecordView]: ...

    @app.get("/access-log/violations", dependencies=[Depends(시크릿_검사)])
    def access_violations(limit: int = 20) -> list[AccessRecordView]: ...
```

`limit` 은 `Query(default=50, ge=1, le=200)` 으로 묶는다 — 클라이언트가 정하는 값에 상한이 없으면 한 요청이 테이블을 통째로 끌어온다.

`build_app` 이 `카탈로그: DocumentCatalog | None = None` 을 더 받는다. `None` 이면 해당 엔드포인트가 503 을 낸다.

- [ ] **Step 5: API 테스트를 쓴다**

`backend/tests/test_api_readonly.py` — 스텁 카탈로그·기록으로 DB 없이:

- 시크릿 없이 각 엔드포인트 → 401
- `/documents` 가 등급·부서를 담아 돌려준다
- `/access-log?limit=500` → 422 (상한 초과)
- `/access-log/violations` 가 `allowed=False` 만 돌려준다
- 응답 JSON 에 `text`·`doc_title` 키가 없다

마지막 항목은 도메인 타입 검사와 별개다 — **HTTP 응답에서 직접 확인한다.**

- [ ] **Step 6: 조립 · 검증 · 커밋**

`deps.py` 에서 지연 생성으로 잇는다(Task 1 의 `_지연열람기록` 과 같은 방식).

```bash
cd backend
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format .
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -m db tests/test_catalog.py -v   # 읽기 전용이라 코퍼스 안전
```

Expected: 전부 통과. `test_catalog.py` 는 `TRUNCATE` 하지 않으므로 코퍼스가 남는다.

커밋 메시지: `문서·계정·열람 이력 읽기 엔드포인트를 더했다` — 목록이 본문을 안 담는 이유와 `limit` 에 상한을 둔 이유를 본문에 적는다.

---

### Task 3: 프론트 기반 — 디자인 시스템 · Blueprint · 로그인 · 앱 셸

**Files:**
- Modify: `frontend/app/layout.tsx`, `frontend/app/page.tsx`, `frontend/auth.ts`
- Create: `frontend/components/Blueprint.tsx`, `SignIn.tsx`, `Sidebar.tsx`, `Header.tsx`, `frontend/lib/session.ts`, `frontend/lib/types.ts`, `frontend/app/(app)/layout.tsx`

**참조:** 마크업과 클래스는 `docs/handoff/prototype.dc.html` 을 직접 읽는다. 템플릿은 `<x-dc>` 안에, 상태는 하단 `class Component` 에 있다. 이 계획서는 마크업을 옮겨 적지 않는다 — 사본이 원본과 어긋나면 사본을 믿게 된다.

- [ ] **Step 1: 디자인 시스템을 로드한다**

`frontend/app/layout.tsx` 에서 `./_ds/industry.css` 를 import 하고, 기존 인라인 스타일(`fontFamily`, `maxWidth` 등)을 **전부 지운다** — 디자인 시스템이 소유한다.

- [ ] **Step 2: Blueprint 래퍼를 만든다**

핸드오프가 *"코너 마크 4개를 절대 빼지 마세요"* 라고 적었다. 한 곳에 가두면 빠뜨릴 수 없다.

```tsx
export default function Blueprint({
  as: Tag = "div",
  className = "",
  children,
  ...rest
}: {
  as?: React.ElementType;
  className?: string;
  children: React.ReactNode;
} & React.HTMLAttributes<HTMLElement>) {
  return (
    <Tag className={`blueprint ${className}`.trim()} {...rest}>
      <i className="corner tl" />
      <i className="corner tr" />
      <i className="corner bl" />
      <i className="corner br" />
      {children}
    </Tag>
  );
}
```

**테스트:** `frontend` 에 테스트 러너가 없으므로 `npx tsc --noEmit` 과 `npm run build` 가 게이트다. 코너 마크 누락은 시각 검사로 확인한다.

- [ ] **Step 3: 역할과 알리스트를 만든다**

`frontend/lib/session.ts`:

```ts
export type Role = "member" | "admin";

// 관리자 알리스트. 비어 있으면 아무도 관리자가 아니다 — 기본값이 "모두 관리자"
// 가 되면 안 된다.
const ADMIN_EMAILS = (process.env.ADMIN_EMAILS ?? "")
  .split(",").map(s => s.trim()).filter(Boolean);

export function roleFor(email: string | null | undefined): Role {
  return email && ADMIN_EMAILS.includes(email) ? "admin" : "member";
}
```

> **핸드오프에서 벗어나는 지점.** 프로토타입은 로그인 화면에서 역할을 **고르게** 한다. 그러면 보안 경계가 아니라 화면 전환 스위치다. 여기서는 **이메일 알리스트로 서버가 정한다.** 화면에서 고르는 UI 는 유지하되(디자인 유지), 알리스트 밖 사용자가 관리자를 골라도 `member` 로 강등되고 그 사실을 화면에 적는다.

- [ ] **Step 4: 로그인 화면을 만든다**

`components/SignIn.tsx` — 프로토타입의 로그인 화면을 그대로 재현하되 고지 문단에 **한 줄을 더한다**:

```
관리자 여부는 이메일 알리스트로 서버가 정합니다. 여기서 고르는 값은 화면 전환일 뿐입니다.
```

핸드오프가 삭제 금지라고 한 기존 고지는 그대로 둔다.

- [ ] **Step 5: 앱 셸을 만든다**

`app/(app)/layout.tsx` + `Sidebar.tsx` + `Header.tsx`. 사이드바 메뉴는 프로토타입과 같되 **관리자 항목은 `role === "admin"` 일 때만 배열에 넣는다**(숨김이 아니라 미포함 — 핸드오프의 요구).

사이드바 하단 `/healthz` 블록은 **실제로 부른다** — `GET /api/healthz` BFF 를 하나 더 만들어 백엔드 `/healthz` 를 중계한다. 지어낸 "db true · model ready" 를 적지 않는다.

- [ ] **Step 6: 검증하고 커밋한다**

```bash
cd frontend && npx tsc --noEmit && npm run build
```

브라우저에서 로그인 → 앱 셸이 뜨는지 확인한다. 커밋.

---

### Task 4: 질의 화면

**Files:**
- Create: `frontend/app/(app)/ask/page.tsx`, `components/PersonaSegment.tsx`, `AskPanel.tsx`, `RightRail.tsx`
- Modify: `frontend/components/Answer.tsx`

**참조:** `docs/handoff/prototype.dc.html` 의 Ask 화면. 레이아웃 `minmax(0,1fr) 320px`, gap 32px, max-width 1240px.

- [ ] **Step 1: 페르소나 세그먼트**

`.seg` / `.seg-opt` 클래스를 쓴다. 세 페르소나는 **하드코딩하지 않고** `GET /api/principals` 에서 받는다 — 백엔드가 `principals` 테이블을 읽으므로 계정을 늘리면 화면이 따라온다.

- [ ] **Step 2: 질의 카드와 세 상태**

`idle` · `loading` · `done` · `error`. 로딩은 프로토타입의 펄스 바 3개(62% / 88% / 40%, 지연 0 / .15s / .3s).

**핸드오프에 없어서 더하는 것 — cold start 안내.** 프로토타입의 로딩 상태는 1.2초를 가정한다. 실제로는 컨테이너가 잠들어 있었으면 임베딩 모델을 올리느라 수십 초 걸린다. 로딩이 **8초를 넘으면** 아래 문구를 로딩 카드에 덧붙인다:

```
백엔드가 잠들어 있었다면 모델을 올리는 중입니다. 첫 요청만 수십 초 걸립니다.
```

- [ ] **Step 3: 에러 상태 세 가지**

핸드오프는 502 만 정의했다. 셋으로 나눈다 — 원인이 다르면 사용자가 할 일이 다르다.

| 상태 | 태그 | 문구 | 행동 |
|---|---|---|---|
| 401 | `.tag-outline` 401 | 세션이 만료되었습니다 | 다시 로그인 |
| 429 | `.tag-outline` 429 | 오늘 사용 가능한 질의를 모두 썼습니다 | 재시도 버튼 없음 |
| 그 외 | `.tag-outline` 502 | 백엔드에 닿지 못했습니다 / Upstream unavailable | 재시도 |

프로토타입의 502 카드 스타일(테두리 `var(--color-accent-700)`)을 셋 다 쓴다.

- [ ] **Step 4: 답변과 근거**

프로토타입 그대로. 태그 행(페르소나 `.tag-accent`, 부서·등급 `.tag-neutral`), 우측 메타 `tool_calls N · hits N · NNNms`. 근거는 `repeat(auto-fill, minmax(280px,1fr))` 그리드, 카드마다 순위 kicker · 조항 코드 `.tag-outline` · 문서명 `.card-title` · 발췌 · `chunk_id`.

**소요 시간은 클라이언트가 잰다** — 백엔드가 돌려주지 않으므로 `performance.now()` 차이를 쓴다. 지어낸 값을 넣지 않는다.

- [ ] **Step 5: 사전 필터링 설명 카드**

`background: var(--color-accent-100)`, 본문 `var(--color-accent-900)`. 문구는 프로토타입 그대로:

```
숨겨진 문서는 결과 개수에도 순위의 빈자리에도 드러나지 않습니다.
```

- [ ] **Step 6: 우측 레일**

**① "같은 질문 · 세 계정" 카드 — 핸드오프에서 벗어난다.** 프로토타입은 페르소나별 요약을 목 데이터로 미리 그려뒀다(`"5건 · 6.1.x 포함"`). 질의를 세 번 던지지 않고는 알 수 없는 값이다.

대신 **실제로 세 번 던진다.** 카드에 "세 계정으로 비교" 버튼을 두고, 누르면 현재 질의를 세 페르소나로 순차 호출해 각각의 `hits` 개수와 조항 코드 집합을 보여준다. 누르기 전에는 안내만 있고 숫자가 없다.

> LLM 호출이 3배가 되므로 **버튼을 눌러야만** 돈다. 자동 실행하지 않는다. 버튼 옆에 "질의 3회를 사용합니다" 를 적는다.

**② 예시 질의 카드** — 프로토타입 그대로. 클릭 시 입력창 교체. 예시는 실제 코퍼스에 답이 있는 것으로 한다:

```
임원 성과급은 어떤 기준으로 정해지나
운영 서버에 접속하려면 어떤 승인이 필요한가
비밀번호는 얼마나 자주 바꿔야 하나
```

- [ ] **Step 7: 검증하고 커밋한다**

`npx tsc --noEmit`, `npm run build`, 브라우저에서 세 페르소나 전환 확인. 커밋.

---

### Task 5: 문서 · 계정 화면

**Files:**
- Create: `frontend/app/(app)/documents/page.tsx`, `principals/page.tsx`, `components/DocumentTable.tsx`, `PrincipalTable.tsx`, `frontend/app/api/documents/route.ts`, `api/principals/route.ts`

- [ ] **Step 1: BFF 라우트 둘**

`/api/documents` 와 `/api/principals`. 세션 확인 후 공유 시크릿으로 백엔드 호출. `/api/ask` 와 같은 형태다.

- [ ] **Step 2: 문서 화면**

프로토타입 그대로. 상단 안내 + 페르소나 칩 3개 + `.tag-neutral` 청크 총계. **청크 총계는 응답의 `chunk_count` 합으로 계산한다** — "338" 을 적어두지 않는다. 코퍼스가 바뀌면 숫자도 바뀐다.

가시성 계산은 클라이언트가 한다:

```ts
const visible = d.required_clearance <= p.clearance
  && (d.allowed_departments.length === 0 || d.allowed_departments.includes(p.department));
```

> 이 식이 `backend/core/access/visibility.py` 의 규칙과 같아야 한다. **세 벌째 사본이다**(SQL · 파이썬 · TypeScript). 화면 하단 주석에 그 사실과 함께 "이 화면의 계산은 표시용이고, 실제 강제는 서버의 SQL 이 한다"를 적는다.

- [ ] **Step 3: 계정 화면**

`.table` — 이름 / 부서 / 등급 / 현재 선택. 카드 2개는 프로토타입 그대로(seed 명령, "사칭 경로가 없는 이유").

**"직급" 컬럼은 뺀다** — `principals` 테이블에 그런 컬럼이 없다. 없는 값을 지어내지 않는다.

- [ ] **Step 4: 검증하고 커밋한다**

브라우저에서 페르소나 칩을 바꿔가며 가시성 배지가 즉시 바뀌는지 확인. 커밋.

---

### Task 6: 감사 로그 · 관리자 대시보드

**Files:**
- Create: `frontend/app/(app)/logs/page.tsx`, `admin/page.tsx`, `components/AdminSummary.tsx`, `AlertTable.tsx`, `AccessTable.tsx`, `InquiryDialog.tsx`, `frontend/app/api/access-log/route.ts`

- [ ] **Step 1: 감사 로그 화면 — 프로토타입 그대로**

`.tag-outline` "W4 계획 / Planned" + 비활성 필터 행(`opacity:.5; pointer-events:none`) + 빈 상태 테이블 + `log_events` 스키마 카드.

**이 화면은 이미 정답 형태다.** 아직 없는 기능을 "없다"고 말하면서 설계는 보여준다. 손대지 않는다.

- [ ] **Step 2: 관리자 요약 4칸 — 진짜 숫자만**

프로토타입은 `342 / 128 / 17 / N` 을 목으로 갖고 있다. **실제 기록에서 계산한다:**

| 칸 | 계산 |
|---|---|
| 질의 수 | `/api/access-log` 응답의 고유 `(query, persona, 시각)` 조합 수 |
| 열람된 서류 | 고유 `chunk_id` 수 |
| 차단된 요청 | `/api/access-log/violations` 의 길이 |
| 확인 필요 | 차단된 요청과 같다(확인 상태를 저장하지 않으므로) |

**"이번 주" 라고 쓰지 않는다** — 기간 필터가 없으므로 "기록 전체" 라고 적는다. 기록이 비어 있으면 0 이 뜨고, 그 아래에 안내를 둔다:

```
아직 기록이 없습니다. 질의를 하면 여기에 쌓입니다.
```

- [ ] **Step 3: 권한 밖 열람 알림 — 진짜 위반만**

`/api/access-log/violations` 를 읽는다. `AccessViolation` 이 실제로 발생했을 때만 행이 생긴다.

**"처리 상태"(미확인/확인 완료) 컬럼은 뺀다** — 확인 상태를 저장하는 곳이 없다. 컬럼을 두고 전부 "미확인"으로 채우면 그것도 지어낸 값이다.

프로토타입의 주석은 유지한다: `알림에는 식별자만 담고 문서 본문·제목은 담지 않습니다.` — 실제로 그렇게 구현돼 있으므로 참인 문장이다.

- [ ] **Step 4: 열람 이력 테이블**

`/api/access-log` 를 읽는다. 컬럼 — 시각 / 페르소나 / 부서·등급 / 질의 / 조항 / 결과.

**"열람 문서" 컬럼은 뺀다** — 기록이 문서 제목을 담지 않는다(Task 1 의 결정). 대신 `chunk_id` 를 보여준다.

필터 칩은 프로토타입 그대로(전체 / 차단만 / 페르소나별), 클라이언트 필터.

- [ ] **Step 5: 문의 다이얼로그 — 정직하게**

프로토타입은 전송 후 "티켓 번호 · 담당 메일" 을 보여준다. **티켓 시스템이 없다.**

다이얼로그와 폼은 그대로 만들되, 전송 버튼을 누르면 `mailto:` 링크를 연다. 접수 배너 문구는 이렇게 바꾼다:

```
메일 앱이 열립니다. 티켓 시스템은 아직 없습니다.
```

고지 문구는 프로토타입 그대로 유지하되 사실에 맞게 고친다 — 실제로 첨부하는 것만 적는다.

- [ ] **Step 6: 관리자 화면 상단 배너**

핸드오프에 없는 것을 하나 더한다. 화면 최상단에:

```
이 화면은 이 배포에서 실제로 일어난 요청만 보여줍니다. 표본이 적은 것은
아직 적게 썼기 때문이며, 시연용으로 채운 데이터가 아닙니다.
```

숫자가 작을 때 "덜 만든 것"으로 보이는 것을 막고, 동시에 그 숫자가 진짜라는 것을 말한다.

- [ ] **Step 7: 검증하고 커밋한다**

질의를 몇 번 던진 뒤 관리자 화면에 그것이 나타나는지 확인. 커밋.

---

### Task 7: 남용 상한과 마무리

**Files:**
- Create: `frontend/lib/rate-limit.ts`
- Modify: `frontend/app/api/ask/route.ts`, `frontend/.env.example`, `README.md`, `jekyll/verification.markdown`

**판정 R9 를 여기서 처리한다.** `/ask` 뒤에 LLM 이 있고 지금은 어떤 구글 계정이든 무제한이다. URL 을 공개하기 전에 반드시 있어야 한다.

- [ ] **Step 1: 상한 규칙**

`frontend/lib/rate-limit.ts`:

```ts
// 알리스트에 있으면 무제한, 밖이면 하루 N회.
//
// 프로세스 메모리에 센다. Vercel 은 인스턴스가 여러 개일 수 있어 완벽하지
// 않지만, 이 상한의 목적은 악의적 공격 차단이 아니라 **요금 폭주 방지**다.
// 인스턴스당 상한이 걸리는 것만으로 그 목적은 달성된다. 정확한 전역 상한이
// 필요해지면 Upstash 같은 외부 저장소가 필요하고, 그것은 이 범위 밖이다.
const ALLOWLIST = (process.env.ASK_ALLOWLIST ?? "").split(",").map(s => s.trim()).filter(Boolean);
const DAILY_LIMIT = Number(process.env.ASK_DAILY_LIMIT ?? "10");
```

`check(email)` 이 `{ allowed: boolean; remaining: number | null }` 을 돌려준다 — 알리스트면 `remaining: null`(무제한).

**날짜 경계는 UTC 로 자른다.** 로컬 시간대를 쓰면 서버 지역에 따라 달라진다.

- [ ] **Step 2: 상한 테스트**

`frontend` 에 테스트 러너가 없다. **여기서는 하나 들인다** — 상한 로직은 조용히 틀리기 쉽고, 틀리면 요금으로 나타난다.

`node --test` 를 쓴다(별도 의존성 없음). `frontend/lib/rate-limit.test.ts` 를 만들고 `package.json` 에 `"test": "node --test --experimental-strip-types lib/*.test.ts"` 를 더한다.

검사할 것:
- 알리스트 안은 무제한(`remaining === null`)
- 알리스트 밖은 `DAILY_LIMIT` 회까지 통과하고 그다음 차단
- 날짜가 바뀌면 리셋
- 이메일이 다르면 카운터가 섞이지 않는다
- 알리스트가 비어 있어도 밖의 사용자가 무제한이 되지 않는다 ← **기본값이 열리는 방향이면 안 된다**

- [ ] **Step 3: BFF 에 연결한다**

`app/api/ask/route.ts` 에서 세션 확인 **직후**, 백엔드 호출 **전에** 상한을 검사한다. 초과 시 429 와 함께 `{ error, remaining: 0 }` 을 돌려준다.

성공 응답에도 `remaining` 을 실어 화면이 남은 횟수를 보여줄 수 있게 한다. `null` 이면 표시하지 않는다.

- [ ] **Step 4: 화면에 남은 횟수를 표시한다**

질의 카드 우측 kicker 옆에 `남은 질의 N회`. 알리스트 사용자에게는 표시하지 않는다.

- [ ] **Step 5: 환경변수를 문서화한다**

`frontend/.env.example` 에 더한다:

```
# 관리자 알리스트(쉼표 구분). 비우면 아무도 관리자가 아니다.
ADMIN_EMAILS=
# 질의 무제한 알리스트(쉼표 구분). 보통 본인 이메일.
ASK_ALLOWLIST=
# 알리스트 밖 사용자의 하루 질의 상한.
ASK_DAILY_LIMIT=10
```

- [ ] **Step 6: 문서를 갱신한다**

`README.md` 의 데모 절에 한 줄 더한다 — 로그인이 요금 게이트이고 알리스트 밖은 하루 N회라는 사실.

`jekyll/verification.markdown` 에 **장치가 잡은 것**을 하나 더한다:

```markdown
#### 장치가 잡은 것 ⑧: 디자인 목업의 숫자는 일어난 적 없는 사건이었다

프론트엔드 디자인 핸드오프의 관리자 대시보드는 `이번 주 질의 342 · 열람된
서류 128 · 차단된 요청 17` 과 8행짜리 열람 이력을 갖고 있었습니다. 고품질
목업이었고 그대로 구현하면 화면이 완성돼 보였을 것입니다.

**그 사건들은 일어난 적이 없습니다.** 열람을 기록하는 코드가 없었고
`log_events` 는 비어 있었습니다.

목 데이터를 그대로 렌더하는 대신 **실제로 기록하게 만들었습니다.** 관리자
화면의 숫자는 이 배포에서 실제로 일어난 요청에서 나옵니다. 기록에는 조항
코드와 `chunk_id` 만 담고 본문과 문서 제목은 담지 않습니다 — 제목만으로도
문서의 존재가 드러나기 때문이며, `AccessViolation` 이 메시지에 `chunk_id` 만
담는 것과 같은 원칙입니다.

같은 이유로 "처리 상태" 컬럼과 문의 티켓 번호를 뺐습니다. 저장하는 곳이
없는 값을 화면에 두면 그것도 지어낸 숫자입니다.
```

- [ ] **Step 7: 전부 검증하고 커밋한다**

```bash
cd backend && .venv/bin/python -m pytest -q && .venv/bin/python -m ruff check .
cd ../frontend && npm test && npx tsc --noEmit && npm run build
```

브라우저에서 알리스트 밖 계정으로 상한을 실제로 넘겨본다(`ASK_DAILY_LIMIT=2` 로 임시 조정). 429 화면이 뜨는지 확인하고 되돌린다.

---

## 완료 조건

- [ ] `pytest -q` · `ruff check` 통과, `pytest -m db` 통과 후 코퍼스 재적재
- [ ] `npm test` · `npx tsc --noEmit` · `npm run build` 통과
- [ ] 7개 화면이 전부 뜨고 사이드바 이동이 된다
- [ ] **관리자 메뉴가 `member` 세션에서 DOM 에 아예 없다** (숨김이 아니라 미포함)
- [ ] 문서 화면이 실제 DB 의 9문서를 보여주고, 페르소나 칩을 바꾸면 가시성이 바뀐다
- [ ] 계정 화면이 실제 `principals` 3행을 보여준다
- [ ] 질의 후 관리자 화면의 열람 이력에 **그 질의가 나타난다**
- [ ] **화면 어디에도 지어낸 숫자가 없다** — 목 데이터 상수가 코드에 남아 있지 않다
- [ ] 상한을 넘기면 429 화면이 뜬다
- [ ] `.blueprint` 를 쓴 모든 곳에 코너 마크 4개가 있다
- [ ] 색·간격·타이포가 전부 CSS 변수를 통한다 (하드코딩된 hex 가 없다)

## 다음 계획으로 넘길 것

- **감사 로그 실데이터** (W4) — `log_events` 파이프라인이 채워지면 화면은 이미 있다
- **알림 확인 상태** — "미확인/확인 완료" 를 저장하려면 테이블에 컬럼과 API 가 필요하다
- **문의 티켓** — 지금은 `mailto:`. 진짜 티켓 시스템은 범위 밖
- **전역 정확한 상한** — 지금은 인스턴스별 메모리. 정확하려면 외부 저장소가 필요하다
- **반응형** — 핸드오프가 데스크톱 전용(1240px)이라고 명시했다

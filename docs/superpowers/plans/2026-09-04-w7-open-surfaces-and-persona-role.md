# W7 구현 계획 — 로그인 벽 걷기 · 페르소나 역할 · 열람 이력 마스킹

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 로그인 게이트를 `/ask` 제출 순간 하나로 좁히고, 관리자 판정을 이메일 알리스트에서 페르소나 역할로 옮기며, 열람 이력에서 다른 방문자의 질문 원문만 백엔드가 가린다.

**Architecture:** `principals` 에 `role` 컬럼을 더해 쿠키의 이름을 서버가 역할로 번역한다(등급·부서와 같은 경로). 프론트 레이아웃 넷에서 세션 리다이렉트를 걷고, `guard()` 의 `role` 출처를 이메일에서 페르소나로 바꾼다. 익명 세션 id 쿠키를 심어 `access_records` 에 저장하고, `/access-log` 가 내 세션이 아닌 행의 `query` 를 마스킹해 돌려준다.

**Tech Stack:** Python 3.12 · FastAPI · psycopg3 · PostgreSQL(pgvector) · Next.js 16 App Router · React 19 · TypeScript 7 · Auth.js v5

**Spec:** `docs/superpowers/specs/2026-09-04-w7-open-surfaces-and-persona-role-design.md`

## Global Constraints

- **모든 파이썬 명령은 `backend/` 에서 실행한다.** 인터프리터는 `.venv/bin/python`.
- **기본 스위트는 `-m db`·`-m corpus`·`-m model`·`-m llm` 을 제외한다.** DB 가 필요한 테스트에는 `pytestmark = pytest.mark.db` 를 붙이고 `pytest -m db` 로 돌린다.
- **`-m llm` 은 절대 실행하지 않는다.** Gemini 실호출이라 요금이 든다.
- **DB 테스트는 `secuagent_test` 를 쓴다.** `conftest.py` 의 `db연결` 픽스처가 그것을 보장하고, 작업 DB(`secuagent`)에 대고 돌면 `RuntimeError` 로 막는다.
- **역할은 권한과 직교한다.** `core/access/visibility.py` 와 `adapters/db/permission_sql.py` 는 이 계획에서 **한 줄도 바뀌지 않는다.**
- **프론트에 이름→역할 상수 맵을 두지 않는다.** 역할은 서버가 `/principals` 로 내려준 값만 쓴다. Task 9 가 이것을 테스트로 고정한다.
- 커밋 메시지는 한국어 평서문 제목 + 왜 그렇게 했는지의 본문. 끝에 다음 두 줄:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_011SmnzAkjRj2L2x6CKetLGB
  ```
- 각 태스크 끝에서 `cd backend && .venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check .` 가 통과해야 한다. 프론트를 건드린 태스크는 `cd frontend && npx tsc --noEmit && npm test && npm run build` 도 통과해야 한다.

---

## File Structure

**백엔드 — 역할**
- `backend/db/schema.sql` (수정) — `principals.role`, `access_records.session_id` 인라인 마이그레이션
- `backend/core/types.py` (수정) — `Principal.role`, `PrincipalRow.role`, `AccessRecord.session_id`
- `backend/adapters/db/principal_store.py` (수정) — `SELECT` 에 `role`
- `backend/adapters/db/catalog.py` (수정) — `principals()` 가 `role` 을 싣는다
- `backend/api/schemas.py` (수정) — `PrincipalView.role`, `AskRequest.session_id`, `AccessRecordView` 는 그대로
- `backend/pipeline/cli.py` (수정) — `seed-principals` 가 역할을 심는다
- `data/principals.json` (수정) — 열 계정에 `role`

**백엔드 — 마스킹**
- `backend/core/access/masking.py` (신규) — 순수 함수 `내_것이_아니면_가린다`
- `backend/adapters/db/access_log.py` (수정) — `session_id` 저장·조회
- `backend/api/main.py` (수정) — `/ask` 가 `session_id` 를 받아 기록에 넣고, `/access-log` 가 `session_id` 로 마스킹

**프론트**
- `frontend/lib/surface.ts` (수정) — `Role` 을 자체 정의, `guard()` 규칙
- `frontend/lib/session.ts` (삭제) · `frontend/lib/session.test.ts` (삭제)
- `frontend/lib/visitor.ts` (신규) — 익명 세션 id 쿠키 이름 상수와 생성
- `frontend/app/(explain|admin|employee)/layout.tsx` (수정) — 세션 리다이렉트 제거, 역할 조회
- `frontend/app/page.tsx` (수정) — 비로그인도 허브
- `frontend/components/Header.tsx` (수정) — 이메일 없으면 로그인
- `frontend/components/AskPanel.tsx` (수정) — 401 카드를 로그인 유도로
- `frontend/app/api/ask/route.ts` · `access-log/route.ts` (수정)
- `frontend/app/(explain)/how/page.tsx` (수정) — `access_records` 컬럼 목록
- `frontend/app/(admin)/admin/page.tsx` (수정) — 마스킹 규칙 문장

**테스트**
- `backend/tests/test_masking.py` (신규)
- `backend/tests/test_access_log.py` (수정) — `session_id` 저장 · **화면 컬럼 목록을 스키마에 묶는 새 그물**
- `backend/tests/test_api.py` (수정) — `/access-log` 마스킹, `/ask` 의 `session_id`
- `backend/tests/test_persona_role.py` (신규) — 프론트에 역할 맵이 없다
- `backend/tests/test_bff_admin_gate.py` (수정) — 전제 교체
- `frontend/lib/surface.test.ts` (수정) — 새 guard 규칙

---

## Task 1: 스키마에 `role` 과 `session_id` 를 더한다

**Files:**
- Modify: `backend/db/schema.sql`
- Test: `backend/tests/test_schema.py`

**Interfaces:**
- Produces: `principals.role TEXT NOT NULL CHECK (role IN ('member','auditor','developer'))`, `access_records.session_id TEXT NULL`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_schema.py` 끝에 추가:

```python
@pytest.mark.db
def test_principals_에_role_컬럼이_있다(db연결):
    """역할을 서버가 정한다는 불변식이 이 컬럼에 걸려 있다.

    프론트에 이름→역할 맵을 두면 권한 판정의 네 번째 사본이 된다(스펙 §2.1).
    """
    with db연결.cursor() as cur:
        cur.execute(
            "SELECT data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'principals' AND column_name = 'role'"
        )
        row = cur.fetchone()
    assert row is not None, "principals.role 이 없다"
    assert row == ("text", "NO")


@pytest.mark.db
def test_role_은_정해진_셋만_받는다(db연결):
    """오타 하나가 조용히 새 역할을 만들면 guard 가 그 값을 모른 채 통과시킨다."""
    with db연결.cursor() as cur:
        cur.execute("TRUNCATE principals RESTART IDENTITY CASCADE")
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO principals (name, department, clearance, role) "
                "VALUES ('x', '개발팀', 1, 'superuser')"
            )
    db연결.rollback()


@pytest.mark.db
def test_access_records_에_session_id_가_있다(db연결):
    """내 브라우저의 질의와 남의 것을 가르는 유일한 값이다(스펙 §2.4).

    NULL 을 허용한다 — 이 컬럼이 생기기 전의 행이 이미 있다.
    """
    with db연결.cursor() as cur:
        cur.execute(
            "SELECT data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'access_records' AND column_name = 'session_id'"
        )
        row = cur.fetchone()
    assert row == ("text", "YES")
```

`backend/tests/test_schema.py` 상단 import 에 `psycopg` 가 없으면 추가한다.

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest -q -m db tests/test_schema.py -k "role or session_id"`
Expected: FAIL — `principals.role 이 없다`

- [ ] **Step 3: 스키마를 고친다**

`backend/db/schema.sql` 의 `CREATE TABLE principals (...)` 정의에 컬럼을 더하고(새 DB용), 그 아래에 기존 DB용 마이그레이션을 붙인다. `access_records` 의 기존 마이그레이션 블록(`resource_kind` 근처) 아래에도 한 줄 더한다:

```sql
-- 역할은 등급·부서와 같은 자리에 둔다 — 쿠키에는 이름만 담기고 서버가
-- 번역한다는 불변식(W6 §2.2)이 역할에도 그대로 적용된다. 프론트 상수 맵은
-- 권한 판정의 네 번째 사본이 된다.
--
-- 기본값 'member' 는 기존 행의 백필을 위해서만 필요하다. resource_kind 와
-- 달리 DEFAULT 를 떼지 않는다 — 새 페르소나를 넣을 때 역할을 빠뜨리는 것이
-- "일반 사용자" 로 떨어지는 것은 닫히는 방향이라 안전하다.
ALTER TABLE principals
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'member'
    CHECK (role IN ('member', 'auditor', 'developer'));

-- 어느 브라우저가 남긴 기록인지. 난수이고 이메일·이름과 잇지 않는다.
-- NULL 을 허용하는 이유: 이 컬럼이 생기기 전의 행이 이미 있고, 그 행들은
-- 어느 세션의 것도 아니다 — 그래서 아무에게도 원문이 보이지 않는다.
ALTER TABLE access_records
    ADD COLUMN IF NOT EXISTS session_id TEXT;

CREATE INDEX IF NOT EXISTS access_records_session_idx ON access_records (session_id);
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest -q -m db tests/test_schema.py`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/db/schema.sql backend/tests/test_schema.py
git commit
```

---

## Task 2: 타입과 저장소가 `role` 을 나른다

**Files:**
- Modify: `backend/core/types.py`, `backend/adapters/db/principal_store.py`, `backend/adapters/db/catalog.py`, `backend/api/schemas.py`
- Test: `backend/tests/test_types.py`, `backend/tests/test_catalog.py`

**Interfaces:**
- Consumes: Task 1 의 `principals.role`
- Produces: `Principal(department: str, clearance: int, role: str = "member")` · `PrincipalRow(name, department, clearance, role)` · `PrincipalView.role: str`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_types.py` 끝에:

```python
def test_principal_의_기본_역할은_일반_사용자다():
    """역할을 빠뜨린 생성이 조용히 감사가 되면 안 된다 — 닫히는 방향이 기본값이다.

    기존 호출부(pipeline/cli.py · api/demo.py)가 role 없이 Principal 을
    만들므로 기본값이 필요하다.
    """
    p = Principal(department="개발팀", clearance=1)
    assert p.role == "member"


def test_역할은_권한_판정에_쓰이지_않는다():
    """역할이 다르다고 보이는 문서가 달라지면 안 된다(스펙 §2.1).

    가시성은 등급·부서만 본다. 이 테스트가 실패하면 visible() 이 role 을
    보기 시작한 것이고, 그건 이 설계가 명시적으로 금지한 일이다.
    """
    from core.access.visibility import visible

    사원 = Principal(department="개발팀", clearance=1, role="member")
    감사 = Principal(department="개발팀", clearance=1, role="auditor")
    for 등급 in (1, 2, 3):
        for 부서 in ((), ("개발팀",), ("인사팀",)):
            assert visible(등급, 부서, 사원) == visible(등급, 부서, 감사)
```

`backend/tests/test_catalog.py` 끝에:

```python
@pytest.mark.corpus
def test_계정_목록이_역할을_싣는다(catalog):
    """프론트가 역할을 서버에서만 얻도록 하려면 이 응답에 있어야 한다."""
    이름별 = {p.name: p for p in catalog.principals()}
    assert 이름별["남감사"].role == "auditor"
    assert 이름별["정개발"].role == "developer"
    assert 이름별["김개발"].role == "member"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_types.py -k 역할`
Expected: FAIL — `Principal` 에 `role` 이 없어 `TypeError` 또는 `AttributeError`

- [ ] **Step 3: 타입과 저장소를 고친다**

`backend/core/types.py` 의 `Principal` 에 필드를 더한다(독스트링 끝에 설명 추가):

```python
    department: str
    clearance: int
    # 어느 면에 들어갈 수 있는지만 정한다. **가시성에는 쓰이지 않는다** —
    # visible() 도 권한_WHERE 도 이 값을 보지 않는다. 기본값이 "member" 인
    # 이유는 닫히는 방향이기 때문이다: 역할을 빠뜨린 생성이 조용히 감사가
    # 되면 안 된다.
    role: str = "member"
```

`PrincipalRow` 에도 `role: str = "member"` 를 더한다.

`backend/adapters/db/principal_store.py`:

```python
    def find(self, name: str) -> Principal | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT department, clearance, role FROM principals WHERE name = %s", (name,)
            )
            row = cur.fetchone()
        if row is None:
            return None
        return Principal(department=row[0], clearance=row[1], role=row[2])
```

`backend/adapters/db/catalog.py` 의 `principals()` SELECT 에 `role` 을 더하고 `PrincipalRow(..., role=row[3])` 로 채운다. 정확한 열 순서는 파일을 열어 확인한다.

`backend/api/schemas.py` 의 `PrincipalView` 에 `role: str` 을 더한다.

`backend/api/main.py` 의 `/principals` 핸들러가 `PrincipalView(...)` 를 만드는 자리에 `role=p.role` 을 더한다.

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest -q && .venv/bin/python -m pytest -q -m db`
Expected: PASS (corpus 테스트는 Task 3 뒤에 통과한다 — 지금은 시드가 없어 실패할 수 있다)

- [ ] **Step 5: 커밋**

```bash
git add backend/core/types.py backend/adapters/db/principal_store.py \
        backend/adapters/db/catalog.py backend/api/schemas.py backend/api/main.py \
        backend/tests/test_types.py backend/tests/test_catalog.py
git commit
```

---

## Task 3: 시드가 역할을 심는다

**Files:**
- Modify: `data/principals.json`, `backend/pipeline/cli.py`
- Test: `backend/tests/test_catalog.py` (Task 2 에서 이미 씀)

**Interfaces:**
- Consumes: Task 2 의 `PrincipalRow.role`
- Produces: 작업 DB 의 `남감사 → auditor`, `정개발 → developer`, 나머지 여덟 `member`

- [ ] **Step 1: 시드 데이터에 역할을 더한다**

`data/principals.json` 의 열 항목에 `"role"` 을 더한다. `남감사` 만 `"auditor"`, `정개발` 만 `"developer"`, 나머지 여덟은 `"member"`:

```json
  {"name": "김개발", "department": "개발팀",     "clearance": 1, "role": "member"},
  {"name": "정개발", "department": "개발팀",     "clearance": 2, "role": "developer"},
```

`남감사` 를 감사로 고른 이유는 이름이 이미 그 역할이고 경영지원팀·등급 2 라 관리자 면을 보는 것이 자연스럽기 때문이다. `정개발` 은 이 시스템을 만든 사람 자리이고 후속 작업(문의 도착지)의 수신자가 된다.

- [ ] **Step 2: CLI 가 역할을 넣게 한다**

`backend/pipeline/cli.py` 의 `seed-principals` 블록:

```python
                cur.execute(
                    """
                    INSERT INTO principals (name, department, clearance, role)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        department = EXCLUDED.department,
                        clearance = EXCLUDED.clearance,
                        role = EXCLUDED.role
                    """,
                    (p["name"], p["department"], p["clearance"], p.get("role", "member")),
                )
        conn.commit()
        for p in 계정들:
            역할 = p.get("role", "member")
            꼬리 = "" if 역할 == "member" else f" · {역할}"
            print(f"  {p['name']} · {p['department']} · 등급 {p['clearance']}{꼬리}")
```

- [ ] **Step 3: 작업 DB 에 반영한다**

Run: `cd backend && .venv/bin/python -m pipeline.cli seed-principals`
Expected: 열 줄이 찍히고 `남감사 … · auditor`, `정개발 … · developer` 가 보인다

- [ ] **Step 4: corpus 테스트가 통과한다**

Run: `cd backend && .venv/bin/python -m pytest -q -m corpus`
Expected: PASS — Task 2 의 `test_계정_목록이_역할을_싣는다` 포함

- [ ] **Step 5: 커밋**

```bash
git add data/principals.json backend/pipeline/cli.py
git commit
```

---

## Task 4: 마스킹 순수 함수

**Files:**
- Create: `backend/core/access/masking.py`
- Test: `backend/tests/test_masking.py`

**Interfaces:**
- Produces: `가린_질의(원문: str, 행_세션: str | None, 내_세션: str | None) -> str` · 상수 `가림_문구 = "(다른 방문자의 질의)"`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_masking.py` (신규):

```python
"""열람 이력에서 남의 질문 원문만 가린다.

**거르지 않고 가리는 이유**(스펙 §2.4). 내 세션 기록만 보이게 하면 화면이
백지가 된다 — 방문자는 로그인하지 않아 질의를 못 하므로 자기 기록이 0건이다.
행은 전부 보이고 본문만 가리면, 화면이 실제 트래픽으로 채워지면서
`admin/page.tsx` 의 "시연용으로 채운 데이터가 아닙니다" 도 참으로 남는다.

**마스킹이 백엔드에 있는 이유.** 프론트에서 가리면 원문이 이미 브라우저에
도착한 뒤라 누출이다.
"""

from core.access.masking import 가린_질의, 가림_문구


def test_내_세션의_질의는_그대로다():
    assert 가린_질의("임원 성과급 기준", "sess-a", "sess-a") == "임원 성과급 기준"


def test_남의_세션의_질의는_가려진다():
    assert 가린_질의("임원 성과급 기준", "sess-b", "sess-a") == 가림_문구


def test_세션이_없는_옛_행은_가려진다():
    """session_id 컬럼이 생기기 전의 행이다. 어느 세션의 것도 아니므로
    아무에게도 원문을 보이지 않는다 — 닫히는 방향으로 답한다."""
    assert 가린_질의("옛 질의", None, "sess-a") == 가림_문구


def test_내_세션을_모르면_전부_가린다():
    """쿠키가 없는 요청. 자기 것이라고 주장할 근거가 없으므로 전부 가린다.

    None == None 으로 옛 행이 열리면 안 된다 — 쿠키를 지운 브라우저가
    옛 행 전부의 원문을 보게 된다.
    """
    assert 가린_질의("옛 질의", None, None) == 가림_문구
    assert 가린_질의("남의 질의", "sess-b", None) == 가림_문구


def test_빈_문자열_세션을_같다고_보지_않는다():
    """빈 문자열이 두 곳에 들어오면 모르는 것끼리 같아진다."""
    assert 가린_질의("질의", "", "") == 가림_문구
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_masking.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.access.masking'`

- [ ] **Step 3: 구현한다**

`backend/core/access/masking.py` (신규):

```python
"""열람 이력에서 남의 질문 원문을 가린다.

`access_records.query` 는 방문자가 직접 친 자유 입력이다. 관리자 면이
페르소나로 열리면(스펙 §2.2) 아무나 그 표를 보게 되므로, 남의 자유 입력이
브라우저에 도착하지 않아야 한다.

**거르지 않고 가린다.** 내 세션 기록만 보이게 하면 화면이 백지가 된다 —
방문자는 로그인하지 않아 질의를 못 하므로 자기 기록이 0건이다. 행은 전부
보이고 본문만 가리면 화면이 실제 트래픽으로 채워지면서, 그 화면이 하는
주장("시연용으로 채운 데이터가 아니다")도 그대로 참으로 남는다.

이 모듈은 DB 도 HTTP 도 모른다. 가리는 규칙이 한 줄이라도 두 벌이 되면
어긋나고, 어긋나는 쪽이 원문을 흘린다.
"""

가림_문구 = "(다른 방문자의 질의)"


def 가린_질의(원문: str, 행_세션: str | None, 내_세션: str | None) -> str:
    """내 세션의 행이면 원문을, 아니면 가림 문구를 준다.

    **모르는 것끼리 같다고 보지 않는다.** `내_세션` 이 없으면(쿠키가 없거나
    지워졌다) 전부 가린다. `None == None` 으로 열어두면 쿠키를 지운
    브라우저가 세션 없이 쌓인 옛 행 전부의 원문을 보게 된다. 빈 문자열도
    같은 이유로 "모름" 으로 다룬다.
    """
    if not 내_세션 or not 행_세션:
        return 가림_문구
    return 원문 if 행_세션 == 내_세션 else 가림_문구
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_masking.py`
Expected: PASS (5개)

- [ ] **Step 5: 커밋**

```bash
git add backend/core/access/masking.py backend/tests/test_masking.py
git commit
```

---

## Task 5: 열람 기록이 `session_id` 를 나른다

**Files:**
- Modify: `backend/core/types.py`, `backend/adapters/db/access_log.py`
- Test: `backend/tests/test_access_log.py`

**Interfaces:**
- Consumes: Task 1 의 `access_records.session_id`
- Produces: `AccessRecord(..., session_id: str | None = None)` · `PgAccessLog.recent()` 와 `violations()` 가 `session_id` 를 채워 돌려준다

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_access_log.py` 끝에:

```python
@pytest.mark.db
def test_세션_id_가_저장되고_되돌아온다(db연결):
    """어느 브라우저가 남긴 기록인지가 마스킹의 유일한 근거다."""
    로그 = PgAccessLog(db연결)
    with db연결.cursor() as cur:
        cur.execute("TRUNCATE access_records RESTART IDENTITY")
    db연결.commit()

    로그.record([
        AccessRecord(
            persona="김개발", department="개발팀", clearance=1, query="질의",
            clause_code="2.6.1", resource_kind="chunk", resource_id=1, allowed=True,
            session_id="sess-a",
        )
    ])

    행 = 로그.recent(10)
    assert len(행) == 1
    assert 행[0].session_id == "sess-a"


@pytest.mark.db
def test_세션_없이_기록해도_터지지_않는다(db연결):
    """이 컬럼이 생기기 전의 경로가 남아 있을 수 있다. NULL 로 들어간다."""
    로그 = PgAccessLog(db연결)
    with db연결.cursor() as cur:
        cur.execute("TRUNCATE access_records RESTART IDENTITY")
    db연결.commit()

    로그.record([
        AccessRecord(
            persona="김개발", department="개발팀", clearance=1, query="질의",
            clause_code=None, resource_kind="chunk", resource_id=1, allowed=True,
        )
    ])

    assert 로그.recent(10)[0].session_id is None
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest -q -m db tests/test_access_log.py -k 세션`
Expected: FAIL — `AccessRecord` 에 `session_id` 가 없어 `TypeError`

- [ ] **Step 3: 구현한다**

`backend/core/types.py` 의 `AccessRecord` 에 필드를 더한다(`ts` 앞, 기본값이 있는 필드끼리 모아둔다):

```python
    allowed: bool
    # 어느 브라우저가 남긴 기록인지. 난수이고 이메일·이름과 잇지 않는다.
    # 관리자 면이 페르소나로 열리므로(스펙 §2.2) 이 값이 "내 질의" 와
    # "남의 질의" 를 가르는 유일한 근거가 된다.
    session_id: str | None = None
    ts: datetime | None = None
```

`backend/adapters/db/access_log.py`:

```python
_삽입_열 = (
    "persona, department, clearance, query, clause_code, "
    "resource_kind, resource_id, allowed, session_id"
)
_조회_열 = _삽입_열 + ", ts"
```

`_행에서` 에 `session_id=row[8], ts=row[9]` 를 넣고, `record` 의 `executemany` 자리표시자를 아홉 개(`%s,` ×9)로 늘리며 튜플에 `r.session_id` 를 더한다.

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest -q -m db tests/test_access_log.py`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/core/types.py backend/adapters/db/access_log.py backend/tests/test_access_log.py
git commit
```

---

## Task 6: API 가 세션을 받고 남의 질의를 가린다

**Files:**
- Modify: `backend/api/schemas.py`, `backend/api/main.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: Task 4 의 `가린_질의`, Task 5 의 `AccessRecord.session_id`
- Produces: `AskRequest(query, persona, session_id: str | None = None)` · `GET /access-log?session_id=...` 가 마스킹된 `query` 를 돌려준다

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_api.py` 끝에:

```python
def test_access_log_이_남의_질의를_가린다(monkeypatch):
    """**마스킹은 백엔드가 한다.** 프론트에서 가리면 원문이 이미 브라우저에
    도착한 뒤라 누출이다 — 응답 JSON 수준에서 확인한다.
    """
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)

    class _기록:
        def recent(self, limit):
            return [
                AccessRecord(
                    persona="김개발", department="개발팀", clearance=1,
                    query="내가 친 질문", clause_code=None, resource_kind="chunk",
                    resource_id=1, allowed=True, session_id="sess-a",
                ),
                AccessRecord(
                    persona="한보안", department="정보보안팀", clearance=2,
                    query="남이 친 질문", clause_code=None, resource_kind="chunk",
                    resource_id=2, allowed=True, session_id="sess-b",
                ),
            ]

        def violations(self, limit):
            return []

        def record(self, rows):
            return 0

    c = TestClient(build_app(lambda: None, 스텁주체저장소({}), 열람기록=_기록()))
    몸 = c.get("/access-log?session_id=sess-a", headers=헤더).json()

    assert 몸[0]["query"] == "내가 친 질문"
    assert 몸[1]["query"] == "(다른 방문자의 질의)"
    assert "남이 친 질문" not in c.get(
        "/access-log?session_id=sess-a", headers=헤더
    ).text, "남의 원문이 응답 본문에 남아 있으면 안 된다"


def test_세션을_모르면_전부_가린다(monkeypatch):
    """쿠키 없는 요청이 옛 행 전부를 여는 일이 없어야 한다."""
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)

    class _기록:
        def recent(self, limit):
            return [
                AccessRecord(
                    persona="김개발", department="개발팀", clearance=1,
                    query="어떤 질문", clause_code=None, resource_kind="chunk",
                    resource_id=1, allowed=True, session_id=None,
                )
            ]

        def violations(self, limit):
            return []

        def record(self, rows):
            return 0

    c = TestClient(build_app(lambda: None, 스텁주체저장소({}), 열람기록=_기록()))
    몸 = c.get("/access-log", headers=헤더).json()
    assert 몸[0]["query"] == "(다른 방문자의 질의)"
```

`backend/tests/test_api.py` 상단에 `from core.types import AccessRecord` 가 없으면 추가한다.

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_api.py -k 가린`
Expected: FAIL — 원문이 그대로 돌아온다

- [ ] **Step 3: 구현한다**

`backend/api/schemas.py` 의 `AskRequest` 에 더한다:

```python
class AskRequest(BaseModel):
    query: str
    persona: str
    # 어느 브라우저가 던진 질의인지. 권한과 무관하다 — 열람 이력에서
    # 자기 질의를 알아보게 하는 데만 쓴다(스펙 §2.4). 클라이언트가 정하는
    # 값이지만, 위조해도 얻는 것은 "그 세션의 질의 원문" 뿐이고 세션 id 는
    # 난수라 남의 것을 알 방법이 없다.
    session_id: str | None = None
```

`backend/api/main.py`:

- 상단에 `from core.access.masking import 가린_질의` 를 더한다.
- `/ask` 핸들러가 `AccessRecord(...)` 를 만드는 **두 자리**(위반 기록과 정상 기록)에 `session_id=req.session_id` 를 더한다.
- `_기록으로(r)` 를 세션을 받도록 바꾼다:

```python
def _기록으로(r: AccessRecord, 내_세션: str | None) -> AccessRecordView:
    # query 만 가린다. 누가·언제·어떤 조항에 닿았는지는 그대로다 —
    # 가리는 것은 자유 입력뿐이라는 것이 이 화면의 계약이다.
    ...
    query=가린_질의(r.query, r.session_id, 내_세션),
```

- `/access-log` 와 `/access-log/violations` 핸들러에 쿼리 인자를 더하고 넘긴다:

```python
    def access_log(
        limit: int = Query(default=50, ge=1, le=200),
        session_id: str | None = None,
    ) -> list[AccessRecordView]:
        if 열람기록 is None:
            raise HTTPException(status_code=503, detail="열람 기록 준비되지 않음")
        return [_기록으로(r, session_id) for r in 열람기록.recent(limit)]
```

`violations` 도 같은 모양으로 고친다.

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && .venv/bin/python -m pytest -q && .venv/bin/python -m pytest -q -m db`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/api/schemas.py backend/api/main.py backend/tests/test_api.py
git commit
```

---

## Task 7: 익명 세션 쿠키

**Files:**
- Create: `frontend/lib/visitor.ts`, `frontend/lib/visitor.test.ts`
- Modify: `frontend/app/api/ask/route.ts`, `frontend/app/api/access-log/route.ts`

**Interfaces:**
- Produces: `VISITOR_COOKIE = "sa_vid"` · `newVisitorId(): string` · 두 라우트가 쿠키를 읽어 백엔드로 넘긴다

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/lib/visitor.test.ts` (신규):

```ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { VISITOR_COOKIE, newVisitorId } from "./visitor.ts";

test("쿠키 이름이 고정돼 있다", () => {
  // 이름이 갈리면 심는 쪽과 읽는 쪽이 조용히 어긋나고, 그러면 모든 방문자가
  // 자기 질의를 못 알아본다 — 화면은 멀쩡해 보인다.
  assert.equal(VISITOR_COOKIE, "sa_vid");
});

test("매번 다른 값이 나온다", () => {
  const 값 = new Set(Array.from({ length: 200 }, () => newVisitorId()));
  assert.equal(값.size, 200);
});

test("추측할 수 없을 만큼 길다", () => {
  // 남의 세션 id 를 맞히면 그 사람의 질의 원문이 보인다. 인증은 아니지만
  // 우연히 맞는 일은 없어야 한다.
  assert.ok(newVisitorId().length >= 32, newVisitorId());
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd frontend && node --test --experimental-strip-types lib/visitor.test.ts`
Expected: FAIL — 모듈이 없다

- [ ] **Step 3: 구현한다**

`frontend/lib/visitor.ts` (신규):

```ts
// 어느 브라우저가 남긴 열람 기록인지를 가르는 값.
//
// **권한이 아니다.** 이 값으로 열리는 것은 "그 세션이 던진 질의의 원문"
// 하나뿐이고, 문서·로그 가시성은 여전히 페르소나의 등급·부서가 정한다.
// 위조해도 얻는 것이 없다시피 하지만, 난수라 남의 값을 알 방법도 없다.
//
// 이메일·이름과 잇지 않는다. 서버는 이 값이 누구인지 모른다.
export const VISITOR_COOKIE = "sa_vid";

export function newVisitorId(): string {
  return crypto.randomUUID().replaceAll("-", "");
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd frontend && node --test --experimental-strip-types lib/visitor.test.ts`
Expected: PASS (3개)

- [ ] **Step 5: 라우트 둘이 쿠키를 나른다**

`frontend/app/api/ask/route.ts` — 페르소나 쿠키를 읽는 자리 근처에서 방문자 id 도 읽고, 없으면 만들어 응답에 심는다. 백엔드 본문에 더한다:

```ts
  const 방문자 = jar.get(VISITOR_COOKIE)?.value ?? newVisitorId();
  ...
    body: JSON.stringify({ query, persona, session_id: 방문자 }),
```

응답을 만들 때 쿠키를 심는다(이미 있으면 같은 값이라 무해하다):

```ts
  const res = Response.json(data);
  res.headers.append(
    "set-cookie",
    `${VISITOR_COOKIE}=${방문자}; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000` +
      (process.env.NODE_ENV === "production" ? "; Secure" : "")
  );
  return res;
```

`frontend/app/api/access-log/route.ts` — 관리자 검사를 걷고(Task 8 에서 면 자체가 역할로 막힌다) 방문자 id 를 상류에 넘긴다:

```ts
  const jar = await cookies();
  const 방문자 = jar.get(VISITOR_COOKIE)?.value ?? "";
  const qs = new URLSearchParams();
  if (limit) qs.set("limit", limit);
  if (violations) qs.set("violations", "1");
  if (방문자) qs.set("session_id", 방문자);
```

경로 조립은 기존 코드의 모양을 따른다(`/access-log` vs `/access-log/violations` 분기 유지).

- [ ] **Step 6: 검증하고 커밋**

Run: `cd frontend && npx tsc --noEmit && npm test && npm run build`
Expected: PASS

```bash
git add frontend/lib/visitor.ts frontend/lib/visitor.test.ts \
        "frontend/app/api/ask/route.ts" "frontend/app/api/access-log/route.ts"
git commit
```

---

## Task 8: 면 접근 규칙을 역할로 바꾼다

**Files:**
- Modify: `frontend/lib/surface.ts`, `frontend/lib/surface.test.ts`
- Delete: `frontend/lib/session.ts`, `frontend/lib/session.test.ts`
- Modify: `frontend/app/(explain)/layout.tsx`, `frontend/app/(admin)/layout.tsx`, `frontend/app/(employee)/layout.tsx`, `frontend/app/page.tsx`, `frontend/components/Header.tsx`
- Modify: `.env.example`, `frontend/.env.example`

**Interfaces:**
- Consumes: Task 2 의 `PrincipalView.role`
- Produces: `Role = "member" | "auditor" | "developer"` (in `lib/surface.ts`) · `guard({surface, hasPersona, role})` 새 규칙

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/lib/surface.test.ts` 의 기존 guard 테스트를 새 규칙으로 바꾸고 추가한다:

```ts
test("관리자 면은 감사 역할만 통과한다", () => {
  assert.equal(guard({ surface: "admin", hasPersona: true, role: "auditor" }), "ok");
  assert.equal(guard({ surface: "admin", hasPersona: true, role: "member" }), "to-hub");
  assert.equal(guard({ surface: "admin", hasPersona: true, role: "developer" }), "to-hub");
});

test("관리자 면은 페르소나가 없으면 허브로 보낸다", () => {
  // 역할은 페르소나에서 온다. 페르소나가 없으면 역할도 없다.
  assert.equal(guard({ surface: "admin", hasPersona: false, role: "member" }), "to-hub");
});

test("설명 면은 로그인도 페르소나도 요구하지 않는다", () => {
  assert.equal(guard({ surface: "explain", hasPersona: false, role: "member" }), "ok");
});

test("직원 면은 페르소나만 요구한다", () => {
  assert.equal(guard({ surface: "employee", hasPersona: true, role: "member" }), "ok");
  assert.equal(guard({ surface: "employee", hasPersona: false, role: "member" }), "to-hub");
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd frontend && node --test --experimental-strip-types lib/surface.test.ts`
Expected: FAIL — `role: "auditor"` 가 타입에 없다

- [ ] **Step 3: `surface.ts` 를 고친다**

`frontend/lib/surface.ts` 상단의 `import type { Role } from "./session.ts";` 를 지우고 자체 정의로 바꾼다:

```ts
// 역할은 서버가 준다 — GET /principals 응답의 role 이다. 여기에 이름→역할
// 맵을 두지 않는다: 그러면 권한 판정의 네 번째 사본이 되고, 이 프로젝트가
// 스스로 경고한 함정이다(스펙 §2.1).
export type Role = "member" | "auditor" | "developer";
```

`guard()` 를 고친다:

```ts
export function guard(input: {
  surface: Surface;
  hasPersona: boolean;
  role: Role;
}): "ok" | "to-hub" | "to-login" {
  // 관리자 면은 감사 역할만. 역할은 페르소나에서 오므로 페르소나가 없으면
  // 판정할 근거 자체가 없다.
  if (input.surface === "admin" && (!input.hasPersona || input.role !== "auditor")) {
    return "to-hub";
  }
  if (input.surface === "employee" && !input.hasPersona) return "to-hub";
  return "ok";
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd frontend && node --test --experimental-strip-types lib/surface.test.ts`
Expected: PASS

- [ ] **Step 5: 레이아웃 셋에서 세션 리다이렉트를 걷는다**

세 레이아웃에서 공통으로:
- `if (!session?.user?.email) redirect("/")` 를 지운다
- `const role = roleFor(session.user.email)` 을 지우고, 대신 서버에서 가져온 계정 목록에서 현재 페르소나의 `role` 을 읽는다
- `<Header email={...} />` 를 `<Header email={session?.user?.email ?? null} />` 로 바꾼다

`(admin)/layout.tsx` 는 페르소나 쿠키를 읽어야 하므로 `(employee)/layout.tsx` 가 페르소나를 확정하는 방식(`personaFrom` → `계정.find`)을 그대로 따른다. 역할을 못 찾으면 `"member"` 로 본다 — 닫히는 방향이다.

`app/page.tsx` 에서 `if (!session?.user?.email) { return <SignIn .../> }` 를 지우고, 세션이 없어도 허브를 그린다. `SignIn` 컴포넌트는 남긴다 — `/ask` 의 로그인 유도(Task 10)가 그 서버 액션을 쓴다.

`components/Header.tsx` 의 `email` prop 을 `string | null` 로 바꾸고, `null` 이면 이메일 줄과 로그아웃 대신 로그인 폼을 그린다:

```tsx
{email ? (
  <>…기존 이메일·로그아웃…</>
) : (
  <form action={signInAction}>
    <button className="btn btn-secondary" type="submit">로그인 / Sign in</button>
  </form>
)}
```

`Header` 가 `signInAction` 을 받도록 prop 을 더하고, 세 레이아웃이 `auth.ts` 의 `signInAction` 을 넘긴다.

- [ ] **Step 6: `session.ts` 를 지우고 설정을 걷는다**

```bash
git rm frontend/lib/session.ts frontend/lib/session.test.ts
```

`.env.example` 과 `frontend/.env.example` 에서 `ADMIN_EMAILS` 줄과 그 주석을 지운다.

`roleFor` 를 import 하는 곳이 남아 있지 않은지 확인한다:

Run: `cd frontend && grep -rn "roleFor\|lib/session" app components lib | grep -v node_modules`
Expected: 출력 없음

- [ ] **Step 7: 검증하고 커밋**

Run: `cd frontend && npx tsc --noEmit && npm test && npm run build`
Expected: PASS

```bash
git add -A frontend .env.example
git commit
```

---

## Task 9: 프론트에 역할 맵이 없다는 것을 고정한다

**Files:**
- Create: `backend/tests/test_persona_role.py`
- Modify: `backend/tests/test_bff_admin_gate.py`

**Interfaces:**
- Consumes: Task 8 의 `lib/surface.ts`

- [ ] **Step 1: 실패할 수 있는 테스트를 쓴다**

`backend/tests/test_persona_role.py` (신규):

```python
"""역할은 서버가 정한다 — 프론트에 이름→역할 맵이 없다.

W6 §2.2 가 못박은 불변식을 역할로 확장한 것이다:

    쿠키에 담기는 것은 **이름뿐**이고 등급·부서는 백엔드가 principals
    테이블에서 번역한다.

프론트에 `{ 남감사: "auditor" }` 같은 상수를 두면 권한 판정의 네 번째
사본이 되고, `(explain)/documents` 화면이 *"이 화면의 계산은 표시용이고
실제 강제는 서버의 SQL"* 이라고 경고한 그 함정을 새로 파는 일이다.

이 스펙(§2.1)이 지켜지는지를 코드로 보는 유일한 그물이다.
"""

import re
from pathlib import Path

_저장소 = Path(__file__).resolve().parents[2]
_프론트 = _저장소 / "frontend"
_역할 = ("auditor", "developer")


def _소스들() -> list[Path]:
    나온다: list[Path] = []
    for 뿌리 in ("app", "components", "lib"):
        d = _프론트 / 뿌리
        나온다 += sorted(d.rglob("*.tsx")) + sorted(d.rglob("*.ts"))
    return [p for p in 나온다 if not p.name.endswith(".test.ts")]


def test_검사할_파일이_있다():
    """0개면 아래 테스트가 공허하게 통과한다."""
    assert len(_소스들()) > 20


def test_페르소나_이름과_역할이_같은_줄에_없다():
    """맵을 만들면 `"남감사": "auditor"` 처럼 한 줄에 붙는다.

    문자열 검사라 거칠지만, 이 파일이 막으려는 편집은 정확히 이 모양으로
    나타난다. 우회하려면 일부러 갈라 써야 하고, 그건 리뷰에서 눈에 띈다.
    """
    이름 = ["김개발", "정개발", "서인사", "박인사", "이보안", "한보안", "오보안", "윤총무", "남감사", "최임원"]
    걸린_것 = []
    for p in _소스들():
        for i, 줄 in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if any(n in 줄 for n in 이름) and any(r in 줄 for r in _역할):
                걸린_것.append(f"{p.relative_to(_저장소)}:{i}")
    assert 걸린_것 == [], (
        f"프론트가 페르소나 이름을 역할에 잇고 있다: {걸린_것}. "
        "역할은 GET /principals 응답에서만 온다(스펙 §2.1)."
    )


def test_역할_문자열이_surface_에만_산다():
    """`auditor` 를 여러 파일이 리터럴로 쓰면 오타 하나가 조용히 게이트를 연다."""
    쓰는_파일 = {
        str(p.relative_to(_프론트))
        for p in _소스들()
        if any(r in p.read_text(encoding="utf-8") for r in _역할)
    }
    assert 쓰는_파일 == {"lib/surface.ts"}, (
        f"역할 리터럴을 쓰는 파일이 늘었다: {sorted(쓰는_파일)}. "
        "판정은 guard() 한 곳에서만 한다."
    )
```

- [ ] **Step 2: 돌려서 현재 상태를 본다**

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_persona_role.py -v`
Expected: PASS (Task 8 이 규율을 지켰다면). FAIL 이면 그 파일에서 역할 리터럴을 걷고 `guard()` 로 옮긴다.

- [ ] **Step 3: 변이로 그물을 확인한다**

`frontend/lib/persona-role.ts` 를 임시로 만든다:

```ts
export const 역할 = { 남감사: "auditor" };
```

Run: `cd backend && .venv/bin/python -m pytest -q tests/test_persona_role.py`
Expected: FAIL (두 테스트)

파일을 지운다: `rm frontend/lib/persona-role.ts`

- [ ] **Step 4: `test_bff_admin_gate.py` 의 전제를 바꾼다**

`roleFor` 가 사라졌으므로 그 파일의 `_관리자_검사`·`관리자_라우트`·두 관련 테스트를 지우고, 남은 것만 다시 쓴다. 파일 독스트링도 새 전제로 고친다:

```python
"""BFF 라우트 핸들러의 문지기를 고정한다. DB 도 Node 도 필요 없다.

**전제가 W7 에서 바뀌었다.** 예전에는 `/access-log` 와 `/log-events` 가
`roleFor(email) !== "admin"` 으로 막았고 그것이 유일한 강제 지점이었다.
지금은 관리자 **면**이 페르소나 역할로 막히고(lib/surface.ts 의 guard),
라우트는 방문자 세션 id 를 상류로 나른다. 라우트에서 확인할 것은 둘이다:

- 백엔드로 나가는 통로에 세션 검사가 필요한 곳(/ask)에는 그것이 있다
- /ask 의 요금 상한이 본문 파싱 뒤·백엔드 호출 앞이다
"""
```

`test_백엔드로_나가는_라우트는_먼저_세션을_본다` 를 `/ask` 만 보도록 좁힌다 — 나머지 라우트는 이제 세션 없이도 동작해야 한다:

```python
def test_ask_는_세션_없이_백엔드를_부르지_않는다():
    """/ask 뒤에는 LLM 이 있다. 로그인은 권한이 아니라 요금 게이트이고,
    W7 이 다른 면의 로그인을 걷은 뒤로 이 라우트가 그 게이트의 유일한 자리다.
    """
    본문 = (_라우트 / "ask" / "route.ts").read_text(encoding="utf-8")
    세션 = 본문.index("await auth()")
    호출 = _백엔드_호출.search(본문)
    assert 호출 is not None
    assert 세션 < 호출.start(), "세션 검사가 백엔드 호출보다 뒤에 있다"
```

`test_ask_의_요금_상한이_본문_파싱_뒤_백엔드_호출_앞이다` 와 `test_검사할_라우트가_있다` 는 그대로 둔다.

- [ ] **Step 5: 통과를 확인하고 커밋**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: PASS

```bash
git add backend/tests/test_persona_role.py backend/tests/test_bff_admin_gate.py
git commit
```

---

## Task 10: `/ask` 를 로그인 유도로 바꾸고 화면 문장을 고친다

**Files:**
- Modify: `frontend/components/AskPanel.tsx`, `frontend/app/(admin)/admin/page.tsx`, `frontend/app/(explain)/how/page.tsx`
- Modify: `backend/tests/test_access_log.py`

**Interfaces:**
- Consumes: Task 8 의 `signInAction` prop 경로

- [ ] **Step 1: 아무 테스트도 실패하지 않는다는 것을 확인한다 — 그것이 문제다**

Run: `cd backend && .venv/bin/python -m pytest -q && .venv/bin/python -m pytest -q -m db`
Expected: **PASS**

`/how` 화면은 `access_records` 의 *"컬럼 전부입니다"* 라고 적고 열 개를
인쇄한다. 그런데 그 목록을 실제 스키마와 대조하는 테스트가 없다 —
`test_access_log.py::test_기록에_본문_컬럼이_없다` 는 금지 컬럼(`text` ·
`doc_title` · `title` · `body` · `content`)의 **부재**만 보는 차단 목록이라,
`session_id` 를 더해도 통과한다.

즉 지금 상태로 두면 **화면의 전수 주장이 조용히 거짓이 된다.** 그물을
먼저 만든다.

- [ ] **Step 2: 화면의 컬럼 목록을 스키마에 묶는 테스트를 쓴다**

`backend/tests/test_access_log.py` 끝에:

```python
@pytest.mark.db
def test_화면이_인쇄한_컬럼_목록이_스키마와_같다(db연결):
    """`/how` 화면은 access_records 의 "컬럼 전부입니다" 라고 적고 목록을 인쇄한다.

    그런 전수 주장은 컬럼이 늘어나는 순간 조용히 거짓이 된다. 위의
    test_기록에_본문_컬럼이_없다 는 금지 목록이라 새 컬럼을 막지 못한다 —
    막아서도 안 된다(session_id 는 더해야 하는 컬럼이다). 여기서는 막는
    것이 아니라 **화면과 스키마가 같이 움직이도록** 묶는다.

    tests/test_how_screen_claims.py 가 /how 의 다른 전수 주장에 하는 일과
    같은 종류다.
    """
    import re
    from pathlib import Path

    화면 = Path(__file__).resolve().parents[2] / "frontend" / "app" / "(explain)" / "how" / "page.tsx"
    assert 화면.exists(), f"{화면} 가 없다 — 이 테스트가 공허해진다"

    블록 = re.search(r"\{\[\s*\n(.*?)\]\.map\(\(컬럼\)", 화면.read_text(encoding="utf-8"), re.DOTALL)
    assert 블록, "화면에서 컬럼 배열을 찾지 못했다"
    화면_컬럼 = set(re.findall(r'"([a-z_]+)"', 블록.group(1)))

    with db연결.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'access_records' AND column_name <> 'id'"
        )
        스키마_컬럼 = {r[0] for r in cur.fetchall()}

    assert 화면_컬럼 == 스키마_컬럼, (
        f"화면과 스키마가 어긋났다. 화면에만: {화면_컬럼 - 스키마_컬럼}, "
        f"스키마에만: {스키마_컬럼 - 화면_컬럼}. 화면 문장도 같이 고친다."
    )
```

정규식이 화면의 실제 배열 모양과 맞는지 확인한다 — 안 맞으면 `블록` 이
`None` 이고 테스트가 그 사실을 말한다. 화면을 열어 배열이 어떻게
시작·끝나는지 보고 정규식을 맞춘다.

- [ ] **Step 3: 실패를 확인하고 화면을 고친다**

Run: `cd backend && .venv/bin/python -m pytest -q -m db tests/test_access_log.py -k 화면이_인쇄한`
Expected: FAIL — `스키마에만: {'session_id'}`

`frontend/app/(explain)/how/page.tsx` 의 컬럼 배열에 `"session_id"` 를
더하고, 그 아래 문단에 한 문장을 더한다:

```tsx
          <code>session_id</code> 는 브라우저를 구분하는 난수입니다. 이메일·이름과 잇지 않으며,
          열람 이력 화면이 <strong>내 질의와 남의 질의를 가르는 데만</strong> 씁니다 — 이 표가
          본문도 제목도 담지 않는다는 주장은 그대로입니다.
```

Run: `cd backend && .venv/bin/python -m pytest -q -m db tests/test_access_log.py`
Expected: PASS

- [ ] **Step 4: 관리자 화면에 마스킹 규칙을 적는다**

`frontend/app/(admin)/admin/page.tsx:45` 근처의 고지 문단 뒤에 더한다:

```tsx
        다른 방문자의 질의 원문은 가려집니다. 이 화면이 보여주는 것은 실제로 일어난 요청이고,
        가려진 것은 그 요청의 <strong>본문뿐</strong>입니다 — 누가 · 언제 · 어떤 조항에
        닿았는지는 그대로입니다. 가리는 일은 서버가 합니다.
```

- [ ] **Step 5: `/ask` 의 401 카드를 로그인 유도로 바꾼다**

`frontend/components/AskPanel.tsx` 의 `errorKind === "401"` 카드 문구를 바꾼다:

```tsx
            <span className="tag tag-outline">401</span>
            <span style={{ fontFamily: "var(--font-heading)", fontSize: 19 }}>
              질의하려면 로그인이 필요합니다
            </span>
```

본문:

```tsx
            이 화면 말고는 로그인이 필요 없습니다. <code>/ask</code> 뒤에는 LLM 이 있어,
            열어두면 누구나 API 요금을 쓰게 됩니다 — 로그인은 권한이 아니라 요금 게이트입니다.
            로그인하면 하루 {"{"}일일 한도{"}"} 회까지 질의할 수 있습니다.
```

(중괄호 자리는 실제 문구로 다듬는다 — 상수를 노출할 필요는 없다. "하루 정해진 횟수까지" 로 충분하다.)

기존 `<a className="btn btn-secondary" href="/">다시 로그인</a>` 를 `signInAction` 을 쓰는 폼으로 바꾼다. `AskPanel` 이 서버 액션을 prop 으로 받도록 시그니처를 넓히고, `(employee)/ask/page.tsx` 가 `auth.ts` 의 `signInAction` 을 넘긴다.

- [ ] **Step 6: 검증하고 커밋**

Run: `cd frontend && npx tsc --noEmit && npm test && npm run build`
Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: PASS

```bash
git add "frontend/components/AskPanel.tsx" "frontend/app/(admin)/admin/page.tsx" \
        "frontend/app/(explain)/how/page.tsx" "frontend/app/(employee)/ask/page.tsx" \
        backend/tests/test_access_log.py
git commit
```

---

## Task 11: 배포와 실측 검증

**Files:** 없음 (운영 작업)

**Interfaces:**
- Consumes: Task 1~10 전부

- [ ] **Step 1: 마이그레이션을 먼저 반영한다**

**순서가 중요하다** — 새 코드가 없는 컬럼을 읽으면 전 요청이 실패한다.

Run: `cd backend && .venv/bin/python -m pipeline.cli seed-principals`
Expected: 열 줄, `남감사 … · auditor`

- [ ] **Step 2: 백엔드를 재빌드·재기동한다**

```bash
cd /Users/ryujun/Documents/secu-agent
SECU_BACKEND_PORT=18080 docker compose -f docker-compose.yml -f docker-compose.tunnel.yml build secu-backend
SECU_BACKEND_PORT=18080 docker compose -f docker-compose.yml -f docker-compose.tunnel.yml up -d secu-backend
```

`curl -s localhost:18080/healthz` 가 `{"status":"ok","db":true,...}` 를 줄 때까지 기다린다.

- [ ] **Step 3: 마스킹을 실측으로 확인한다**

```bash
SECRET=$(grep '^BACKEND_SHARED_SECRET' .env | cut -d= -f2-)
curl -s -m 20 "http://localhost:18080/access-log?limit=5&session_id=없는세션" \
  -H "X-Backend-Secret: $SECRET" | python3 -m json.tool | grep query
```

Expected: 모든 `query` 가 `"(다른 방문자의 질의)"` — 기존 270건은 `session_id` 가 NULL 이므로 아무에게도 원문이 보이지 않는다.

- [ ] **Step 4: 비로그인 흐름을 브라우저로 확인한다**

시크릿 창에서 `http://localhost:3000/` 을 연다.

Expected:
- 로그인 벽 없이 **허브가 바로 뜬다**
- 페르소나 카드에서 `남감사` 를 고르면 좌측 네비에 감사 로그·관리자 대시보드가 보인다
- `김개발` 로 고르면 그 둘이 보이지 않고, 주소로 `/admin` 에 직접 가면 허브로 돌아온다
- `/how`·`/documents`·`/principals` 가 로그인 없이 열린다
- `/ask` 화면이 열리고, 질의를 제출하면 **"질의하려면 로그인이 필요합니다"** 카드가 뜬다
- 관리자 대시보드가 **비어 있지 않다** — 270건이 그대로 보이고 `query` 만 가려져 있다

- [ ] **Step 5: 문서를 갱신하고 커밋**

`README.md` 의 데모 문단에서 "로그인은 권한이 아니라 요금 게이트입니다" 문장을 유지하되, **어디에 걸리는지**를 고친다:

```
로그인은 `/ask` 에만 걸립니다 — 허브·설명 면·직원 면은 로그인 없이 열립니다.
관리자 면은 페르소나의 역할이 정합니다(`남감사`).
```

스펙 문서의 상태를 바꾼다: `docs/superpowers/specs/2026-09-04-w7-open-surfaces-and-persona-role-design.md` 의 `**상태**: 검토 대기` → `**상태**: 구현됨 (2026-09-04)`.

```bash
git add README.md docs/superpowers/specs/2026-09-04-w7-open-surfaces-and-persona-role-design.md
git commit
git push origin main
```

- [ ] **Step 6: CI 를 확인한다**

Run: `gh run list --limit 2`
Expected: CI 와 Pages 둘 다 success. `image` 잡이 Dockerfile 을 실제로 빌드한다.

---

## 자체 검토 결과

**스펙 커버리지**

| 스펙 | 태스크 |
|---|---|
| §2.1 역할을 principals 에 · 서버가 번역 | 1 · 2 · 3 |
| §2.1 프론트에 역할 맵 금지 | 9 |
| §2.2 면 접근 조건 | 8 |
| §2.3 `/ask` 제출 시점 로그인 | 10 (화면) · 9 (라우트 고정) |
| §2.4 남의 질문만 마스킹 | 4 · 5 · 6 · 7 |
| §2.4 `/how` 컬럼 목록 갱신 | 10 (그물이 없어 새로 만든다) |
| §2.5 `ADMIN_EMAILS` 제거 | 8 |
| §5 배포 순서 | 11 |
| §6 검증 항목 여섯 | 1 · 6 · 8 · 9 · 11 |
| §7 한계를 화면에 적기 | 10 (관리자 화면 문장) |

**남는 것**: 스펙 §7 첫 항목("역할을 아무나 고른다 — 실제 배포라면 인사 시스템에서 온다")을 허브 화면에 적는 일은 Task 10 의 관리자 화면 문장에 포함시켰다. 별도 태스크로 두지 않는다.

**타입 일관성**: `Principal.role: str`(백엔드) ↔ `PrincipalView.role: str`(API) ↔ `Role = "member"|"auditor"|"developer"`(프론트). 백엔드가 `str` 인 이유는 DB CHECK 가 값을 강제하고, 파이썬 쪽에 Enum 을 더하면 `visible()` 이 그것을 보게 될 유혹이 생기기 때문이다 — 역할은 권한과 직교해야 한다.

`AccessRecord.session_id: str | None` ↔ `AskRequest.session_id: str | None` ↔ `VISITOR_COOKIE`/`newVisitorId()`(프론트) 일치.

# W3 설계 보충 — 배포 · 인증 · API · UI

- **작성일**: 2026-09-01
- **상태**: 확정 (구현 계획 수립 전)
- **상위 문서**: `docs/superpowers/specs/2026-08-31-secu-agent-design.md`

---

## 1. 이 문서의 범위

상위 설계 문서는 도메인·검색·권한 필터링·평가를 정한다. **배포 토폴로지·인증·HTTP 표면·UI 는 다루지 않는다.** 이 문서가 그 넷만 정한다. 나머지는 상위 문서를 따른다.

W1·W2 가 끝난 지금 상태에서 출발한다: 코퍼스 9문서·126조항·338청크, Recall@10 0.867, 누출 테스트 4채널 8건, `core/access/visibility.py` 와 `core/agent/policy.py` 존재, 프로덕션 호출자는 아직 없음.

### 1.1 상위 문서의 모순을 여기서 정정한다

상위 문서 §9 마일스톤 표는 W3 을 "에이전트(**도구 3개**)"라 하고, 같은 표의 W4 는 "**로그 조회 도구 · 리포트 생성**"을 자기 몫이라 한다. §12 는 W3 을 "에이전트 + API + UI + 배포", W4 를 "로그 파이프라인 + 리포트"로 나눈다.

`query_logs` 는 `log_events` 에 데이터가 있어야 하고 그 파이프라인은 W4 다. 지금 `log_events` 는 비어 있다.

**정정: W3 의 도구는 `search_policy` 하나다.** 도구 등록·실행 정책·호출 상한의 구조는 이번에 전부 들어가므로, W4 는 도구 둘을 그 구조에 꽂기만 하면 된다. §9 표의 "도구 3개"는 오기로 본다.

---

## 2. 배포 토폴로지

```
브라우저
   │ HTTPS  (브라우저는 Vercel 하고만 통신한다)
Vercel — Next.js
   │  · Auth.js 로 구글 로그인
   │  · Route Handler 가 BFF 역할: 세션 확인 후 백엔드 호출
   │ HTTPS + 공유 시크릿 헤더
Cloudflare Worker — 얇은 라우터
   │
Cloudflare Container — FastAPI + e5 + LangGraph 에이전트 (Dockerfile)
   │ psycopg (TCP)
Neon — PostgreSQL 16 + pgvector   (스키마는 W1 것 그대로)
   │
Anthropic API — claude-opus-5
```

**Container 를 쓰는 이유.** 백엔드 이미지는 torch 와 임베딩 모델을 포함해 약 3GB 다. Workers 런타임은 이것을 돌릴 수 없다. Cloudflare Containers 는 Dockerfile 이면 무엇이든 받고 이미지 상한이 20GB 라 여유가 크다(실측 확인). Container 는 정상 리눅스 샌드박스이므로 `psycopg` 가 외부 Postgres 에 그대로 붙는다 — Hyperdrive 는 Workers 용 가속기라 여기서는 쓰지 않는다.

**Postgres 가 외부인 이유.** Cloudflare 에는 1st-party Postgres 가 없다. 프로젝트의 핵심 논증이 SQL 사전 필터링(`WHERE` 가 `ORDER BY` 보다 먼저)이므로 pgvector 를 포기할 수 없고, 따라서 관리형 Postgres 를 외부에서 가져온다.

**비용.** Workers Paid $5/월(Containers 전제) · Neon 무료 티어 · Vercel Hobby 무료 · Anthropic 종량.

### 2.1 감수하는 것: cold start

Container 는 유휴 시 잠들고, 깨어날 때 임베딩 모델 로드에 수십 초가 걸린다. 첫 방문자가 그 시간을 기다린다.

대안은 임베딩을 외부 API 로 빼는 것이지만 그러면 상위 문서 §2.5 의 모델 결정이 뒤집히고, 차원이 바뀌어 코퍼스를 재적재해야 하며, **W2 가 측정한 Recall@10 0.867 이 무효가 되어 골든셋 30건을 다시 돌려야 한다.** 배포 주차에 검색 품질까지 다시 여는 것은 위험 대비 이득이 맞지 않는다. cold start 를 감수하고, README 에 그 사실을 적는다.

`intfloat/multilingual-e5-small` 은 Microsoft 모델이다(*Multilingual E5 Text Embeddings*, arXiv:2402.05672 — 저자 전원 Microsoft Research, 코드는 `microsoft/unilm`). 베이스는 multilingual MiniLM(Microsoft). 중국 기관 모델을 쓰지 않는다는 제약을 만족한다. 같은 이유로 Cloudflare Workers AI 의 `@cf/baai/bge-m3` 는 후보에서 제외한다 — BAAI(베이징 인공지능연구원) 모델이다.

---

## 3. 인증과 권한 모델

**여기서 무엇이 진짜이고 무엇이 시연 장치인지 분명히 한다.** 이 프로젝트가 검증 체계를 산출물로 내세우는 이상, 인증에 대해 애매하게 말하면 그 주장 전체가 약해진다.

| 층 | 진짜인가 | 내용 |
|---|---|---|
| **인증** | **진짜** | 구글 OAuth. 로그인하지 않으면 API 에 닿지 못한다 |
| **권한 부여** | **합성** | 로그인한 사용자가 세 페르소나(사원·팀장·임원) 중 하나를 고른다 |
| **권한 강제** | **진짜** | 고른 페르소나가 `Principal` 이 되어 SQL 사전 필터링을 탄다. W2 의 누출 테스트가 지키는 그 경로다 |

### 3.1 로그인이 하는 일은 요금 게이트다

`POST /ask` 뒤에는 LLM 이 있다. 열어두면 아무나 API 요금을 태울 수 있다. **로그인의 일차 목적은 권한이 아니라 남용 차단이다.**

구글 계정을 부서·등급에 매핑하지 않는 이유: 방문자의 구글 계정에는 "인사팀·등급 2" 라는 정보가 없다. 이메일 알리스트로 진짜 등급을 부여할 수는 있지만, 그러면 **방문자는 등급 1 화면 하나만 보고 나간다** — 이 프로젝트의 가장 강한 장면인 "같은 질문, 세 계정, 다른 결과"를 볼 수 없다. 이력서에 거는 URL 로서 그것은 치명적이다.

### 3.2 이 사실을 감추지 않는다

UI 의 페르소나 선택기 옆과 README 에 다음을 적는다: **인증은 실제 구글 OAuth 이고, 부서·등급은 시연을 위해 선택하는 값이며, 선택된 값이 실제 권한 필터를 그대로 탄다.**

감추면 그것이 거짓 주장이 된다. 적어두면 오히려 "무엇을 검증했고 무엇을 검증하지 않았는지 구분한다"는 이 프로젝트의 태도와 맞는다.

### 3.3 브라우저는 백엔드를 모른다 (BFF)

브라우저는 Vercel 하고만 통신한다. Next.js Route Handler 가 Auth.js 세션을 확인한 뒤 공유 시크릿 헤더로 Cloudflare 백엔드를 호출한다.

| 이득 | 내용 |
|---|---|
| CORS 없음 | 같은 오리진이다 |
| 크로스도메인 쿠키 없음 | 세션 쿠키가 Vercel 도메인에만 산다 |
| 백엔드가 공개되지 않음 | 시크릿 없는 호출은 401 |
| 요금 게이트가 한 곳 | 세션 확인이 Route Handler 한 군데다 |

백엔드는 시크릿을 **상수 시간 비교**로 검사한다. 시크릿이 없거나 틀리면 401 이고, 그 응답은 이유를 말하지 않는다.

---

## 4. API 표면

두 개뿐이다.

```
POST /ask       {query: str, persona: "김개발"|"박인사"|"최임원"} → AskResponse
GET  /healthz   → {status, db, model}
```

페르소나 식별자는 W2 가 `principals` 테이블에 시드한 세 계정의 `name` 이다. 서버가 그 테이블을 조회해 `Principal(department, clearance)` 를 만든다 — 목록을 코드에 다시 적지 않는다. 계정을 늘리려면 `seed-principals` 만 고치면 된다.

```python
@dataclass(frozen=True)
class AskResponse:
    answer: str                  # 에이전트의 최종 답변
    hits: list[PolicyHitView]    # 근거로 쓰인 청크 — 조항 코드 · 문서 제목 · 본문
    persona: PersonaView         # 부서 · 등급 (화면 표시용)
    tool_calls: int              # 도구를 몇 번 불렀나 — 상한 8 에 걸렸는지 보인다
```

**`persona` 문자열이 서버에서 `Principal` 로 번역된다.** 클라이언트가 `department` 나 `clearance` 를 직접 보내지 않는다 — 보내게 하면 그 값이 곧 사칭 경로다. `principals` 에 없는 이름은 400 이고, 그 응답은 어떤 이름이 존재하는지 알려주지 않는다.

`/healthz` 가 DB 연결과 모델 로드 여부를 각각 보고한다. cold start 중인지 배포가 깨졌는지 구분하려면 둘이 나뉘어야 한다.

**스트리밍은 하지 않는다.** SSE 는 BFF 를 한 겹 더 복잡하게 만들고, 이 주차의 목표는 배포다. 응답까지 수 초 걸리는 것을 UI 가 로딩 상태로 처리한다.

---

## 5. UI 범위

한 페이지다.

```
[구글로 로그인]                          ← 미로그인 시 이것만

────────────────────────────────────────
질의 입력 ______________________  [묻기]

페르소나  (○ 사원  ○ 팀장  ○ 임원)
  ⓘ 인증은 실제 구글 OAuth 입니다. 부서·등급은 시연을 위해 고르는
    값이고, 고른 값이 실제 권한 필터를 그대로 탑니다.
────────────────────────────────────────

답변
근거  [2.6.1] ISMS-P 인증기준 안내서 — 본문 …
      [5.1.1] 개발팀 서버 접근 절차 — 본문 …
```

**세 페르소나를 나란히 보여주는 비교 화면은 W3 범위 밖이다.** 한 번에 세 번 질의하면 LLM 호출이 3배가 되고, 그 장면은 이미 W2 의 `demo` CLI 가 증명했다. 페르소나를 바꿔 다시 물으면 차이가 보인다.

Next.js App Router. 상태는 서버 컴포넌트 + Route Handler 로 충분하고 클라이언트 상태 라이브러리를 쓰지 않는다.

---

## 6. 에이전트 계층의 보안 결정

상위 문서 §2.3 이 정한 격리(LangChain 은 `adapters/` 에만)를 지키되, **한 가지를 더한다.**

### 6.1 `principal` 을 LLM 에게 노출하지 않는다

```python
core/agent/tools.py       search_policy(query, principal, k) -> list[PolicyHit]
                          순수 파이썬. 포트만 안다. LangChain 을 모른다.
adapters/agent/runner.py  @tool 이 내보내는 스키마에서 principal 을 뺀다.
                          런너가 요청의 principal 을 클로저로 주입한다.
```

W2 의 최종 리뷰가 정확히 이 지점을 지적했다 — **`principal` 이 필수 인자인 것은 *누락*을 불가능하게 하지만 *사칭*은 막지 않는다.** 도구 스키마에 `principal` 이 보이면 LLM 이 `clearance: 3` 을 써넣을 수 있다. 스키마에서 빼면 LLM 에게는 그런 인자가 존재하지 않는다.

이것이 `core/agent/policy.py` 의 `enforce` 와 짝을 이룬다. 스키마 은닉이 사칭을 막고, `enforce` 가 출력에 권한 밖 항목이 섞였는지 검사한다.

### 6.2 호출 상한 — 둘이 필요하다

상위 문서 §7.2 의 `MAX_ITERATIONS = 8` 을 `ToolCallLimitMiddleware(run_limit=8, exit_behavior="continue")` 로 건다. `exit_behavior` 세 값 중 "넘으면 중단하고 그때까지의 결과로 답한다"에 맞는 것은 `continue` 뿐이다 — `error` 는 예외를 던지고, `end` 는 결과가 아니라 왜 멈췄는지를 답한다.

**그런데 `continue` 는 종료를 보장하지 않는다.** 초과한 도구를 차단할 뿐 그래프를 끝내지 않아서, 도구를 계속 요청하는 모델은 모델 호출만 반복한다. 상한을 두는 이유가 "비용과 지연이 무한정 늘어난다"인데 **비용은 모델 호출 쪽에서 난다** — 도구 상한만으로는 그것이 전혀 묶이지 않는다. 구현 중에 실측으로 확인했다: 재귀 상한 9999 에 걸려 `GraphRecursionError` 로 죽는다.

그래서 `ModelCallLimitMiddleware(run_limit=12, exit_behavior="end")` 를 함께 건다. 정상 경로는 도구 8회 + 최종 답변 1회 = 9회라 12 는 여유가 있으면서 폭주를 묶는다.

호출 횟수를 묶어도 **한 번의 작업량**이 안 묶이면 비용은 그쪽으로 샌다. `k` 는 모델이 정하는 값이고 `hybrid.search` 가 후보를 그 5배로 잡으므로, `core/agent/tools.py` 가 `MAX_K = 20` 으로 깎는다. 스키마 제약이 아니라 클램프인 이유: 스키마는 모델이 *선언하는* 값만 제약하고, 클램프는 무엇이 들어오든 모든 호출자를 보호한다.

---

## 7. 계획을 쓰기 전에 실물로 확인한 것

상위 문서 §10 이 "LangChain 1.x API 를 기억으로 쓰면 막힌다"를 최상위 리스크로 지목했으므로, 임시 환경에 실제로 설치해 시그니처를 읽었다. **둘이 기억과 달랐다.**

| | 기억으로 쓰면 | 실제 (langchain 1.3.18 · langgraph 1.2.11 · langchain-anthropic 1.7.0) |
|---|---|---|
| 에이전트 생성 | `create_react_agent` (`langgraph.prebuilt`) | **deprecated.** `from langchain.agents import create_agent` |
| 반복 상한 | `recursion_limit` 인자 | `create_agent` 에 그런 인자가 없다. `ToolCallLimitMiddleware` 가 도구 호출 상한이다 |

`create_agent` 의 실제 파라미터: `model` · `tools` · `system_prompt` · `middleware` · `response_format` · `state_schema` · `context_schema` · `checkpointer` · `store` · `interrupt_before` · `interrupt_after` · `debug` · `name` · `cache` · `transformers`.

`ToolCallLimitMiddleware(*, tool_name=None, thread_limit=None, run_limit=None, exit_behavior='continue')` 의 `exit_behavior` 는 셋이다.

| 값 | 동작 | §7.2 의 "중단하고 그때까지의 결과로 답한다" 에 맞나 |
|---|---|---|
| `error` | 예외를 던진다 | 아니다 |
| `end` | 즉시 멈추고 왜 멈췄는지 설명하는 메시지를 낸다 | 아니다 — "왜 멈췄는지"를 답하지 결과로 답하지 않는다 |
| **`continue`** | 초과한 도구만 막고 모델은 계속한다 | **맞다** — 모델이 이미 가진 것으로 답을 낸다 |

설치된 버전이 상위 문서 §2.5 의 "LangChain 1.3 / LangGraph 1.2" 와 일치했다.

**Cloudflare Containers 실측 확인:** 이미지 상한 20GB, 인스턴스 최대 4 vCPU · 12 GiB, Dockerfile 이면 언어 무관, Workers Paid $5/월 필요.

**Cloudflare Access 를 쓰지 않는 이유:** Access 는 `Cf-Access-Jwt-Assertion` 헤더로 JWT 를 넘기고 오리진이 서명을 검증해야 한다(헤더 존재만 확인하면 위조된다). 그러나 다른 도메인의 브라우저 앱이 Access 로 보호된 API 를 호출하려면 `CF_Authorization` 쿠키가 필요하고, 그 쿠키는 Cloudflare 도메인에 산다. BFF 가 이 문제를 통째로 없앤다.

---

## 8. 테스트 전략

| 계층 | 어떻게 | 마커 |
|---|---|---|
| `core/agent/tools.py` | 스텁 포트로 단위 테스트. LLM 도 DB 도 없다 | 없음(기본 스위트) |
| `principal` 이 도구 스키마에 없다 | 런너가 만든 도구의 스키마를 직접 검사한다 | 없음 |
| `adapters/agent/runner.py` | 실제 LLM 호출 | `llm` |
| API | FastAPI TestClient + 스텁 러너 | 없음 |
| 시크릿 검사 | 시크릿 없음·틀림·맞음 세 경우 | 없음 |
| 경계 | `core/` 가 `langchain`·`langgraph` 를 import 하지 않는다 | 없음 (이미 목록에 있다) |

**스키마 검사 테스트가 이 주차의 핵심 장치다.** `principal` 이 도구 스키마에 새어 들어오면 사칭이 가능해지는데, 그 사고는 조용하다 — 에이전트는 여전히 답을 내고 테스트는 초록이다. 스키마를 직접 들여다보는 테스트가 아니면 잡히지 않는다.

---

## 9. 결정 기록

되돌리기 어려운 순서로.

1. **`principal` 은 도구 스키마에 없다** — 필수 인자는 누락을 막지만 사칭을 막지 않는다 (6.1)
2. **인증은 진짜, 권한 부여는 합성, 강제는 진짜** — 셋을 구분해 명시한다. 감추면 거짓 주장이 된다 (3)
3. **BFF** — 브라우저는 Vercel 하고만 통신한다. CORS·크로스도메인 쿠키·백엔드 공개가 한꺼번에 사라진다 (3.3)
4. **Cloudflare Containers + 외부 Postgres** — Workers 는 torch 를 못 돌리고 Cloudflare 에는 Postgres 가 없다 (2)
5. **e5 를 컨테이너에 유지** — 바꾸면 W2 가 측정한 검색 품질이 무효가 된다. cold start 를 감수한다 (2.1)
6. **W3 의 도구는 하나** — `query_logs` 는 돌릴 데이터가 W4 에 있다 (1.1)
7. **`exit_behavior="continue"`** — 셋 중 §7.2 의 의도에 맞는 유일한 값이다 (7)
8. **스트리밍 없음** — BFF 를 복잡하게 만들고 이번 주 목표는 배포다 (4)
9. **세 페르소나 동시 비교 화면 없음** — LLM 호출이 3배가 되고 그 장면은 CLI 가 이미 증명했다 (5)

---

## 10. 범위에서 뺀 것

| 항목 | 어디로 |
|---|---|
| `query_logs` · `draft_report` · `verify_clauses` | W4 |
| 로그 파이프라인 | W4 |
| 멀티턴 대화 | P1 (상위 문서 §1.3) |
| 진짜 부서·등급 매핑 | 범위 밖 — 3.2 에 명시한다 |
| 스트리밍 응답 | 범위 밖 |
| 관리자 대시보드 | P1 |

## 11. 다음 단계

이 문서와 상위 설계 문서를 입력으로 W3 구현 계획을 작성한다.

# Secu-Agent 설계 문서

- **작성일**: 2026-08-31
- **상태**: 확정 (구현 계획 수립 전)
- **목적**: 취업 포트폴리오 — 배포된 URL 을 이력서에 건다
- **기간**: 3~4주 (W3 끝에 배포)

---

## 1. 개요

### 1.1 한 줄 정의

**부서·직급에 따라 검색 범위가 달라지는 사내보안 규정 RAG 와, 감사 로그를 함께 조회해 위반 사항을 규정 조항과 함께 리포트하는 AI 에이전트.**

### 1.2 이 프로젝트가 증명하려는 것 — 두 가지

**① 기술: 권한 없는 문서의 존재를 감추는 검색**

RAG 챗봇은 흔하다. 권한에 따라 결과가 달라지는 RAG 는 흔하지 않고, 제대로 하기 까다롭다.

```
질의: "임원 성과급 산정 기준이 뭔가요?"   ← 일반 사원이 물음

사후 필터링:  상위 10건 검색 → 권한 검사 → 3건 남음
              결과가 3건인 것 자체가 "숨겨진 문서가 있다"는 신호가 된다
              개수·순위·응답시간으로 존재가 새어나간다

사전 필터링:  권한 통과 문서 중 상위 10건 → 10건
              차이를 관측할 수 없다
```

**"검색은 됐지만 못 보는 문서"의 존재를 어떻게 감출 것인가** — 이것이 이 프로젝트의 기술적 핵심이다.

**② 방법론: AI 가 생성한 코드를 신뢰할 수 있게 만드는 검증 체계**

빠르게 만들고 여러 번 검증해 마무리하는 방식으로 일한다. 속도를 택하면 보통 안전성을 잃는다고 여겨진다. 그래서 **취약점이 치명적인 보안 도메인**을 주제로 잡았다.

개별 코드를 한 줄씩 읽어 검증하는 방식은 생성 속도를 따라가지 못한다. 대신 **결함이 스스로 드러나는 장치를 먼저 만든다**. 그 장치와 그것이 잡아낸 기록이 이 프로젝트의 두 번째 산출물이다(8장).

### 1.3 범위에서 뺀 것

3~4주 안에 다섯 서브시스템을 다 하면 실패한다.

**P0** — 문서 파이프라인 · 하이브리드 검색 · Access Control · 최소 에이전트(도구 3개) · 평가 · 배포
**P1** — 로그 이상탐지 모델 · 관리자 대시보드 · 멀티턴 대화 · RAGAS 전체 지표

**로그는 "조회·인용 가능한 상태"까지만 P0 다.** 이상탐지 모델까지 넣으면 그것만으로 프로젝트 하나다.

---

## 2. 아키텍처

### 2.1 저장소 구조

```
backend/     파이썬 — 도메인 · 파이프라인 · 평가 · API
frontend/    Next.js 대시보드
jekyll/      문서 사이트 (검증 체계 페이지 포함)
```

### 2.2 계층 — 의존성은 항상 안쪽을 향한다

```
backend/
  core/        안쪽. 프레임워크를 모른다 — 표준 라이브러리만 쓴다
    types.py     Document · Chunk · Clause · LogEvent · Principal
    ports.py     경계 Protocol (안쪽이 소유, 바깥이 구현)
    access/      가시성 규칙 — 순수 함수
    retrieve/    하이브리드 검색 + RRF 융합
    agent/       도구 로직 · 실행 정책 (LangChain 무관)
  adapters/    바깥. core 를 안다
    parsing/     PDF · DOCX · MD → Chunk
    db/          psycopg + pgvector
    embedding/   multilingual-e5-small
    llm/         Anthropic SDK
    agent/       LangChain / LangGraph 런너
  pipeline/    문서 · 로그 적재
  api/         FastAPI — 얇은 HTTP 계층
  eval/        평가 하네스 + 누출 테스트
```

### 2.3 LangChain 을 어댑터에 격리한다

**요구사항이 LangChain 활용을 명시하므로 쓰되, `adapters/` 에만 둔다.**

```
core/agent/tools.py       도구 3개의 실제 로직 — 순수 파이썬, LLM 도 프레임워크도 모른다
core/agent/policy.py      최대 반복 횟수 · 도구 출력 검증 규칙
adapters/agent/runner.py  LangGraph 로 AgentRunner 구현 — core 의 도구를 @tool 로 감싸기만 한다
```

| 이득 | 내용 |
|---|---|
| 도구 테스트 | LangChain 없이, LLM 호출 없이 단위 테스트 |
| **권한 강제** | `search_policy(query, principal)` 시그니처가 `core/` 에 있어 프레임워크가 우회할 수 없다 |
| 프레임워크 교체 | LangChain 1.x → 2.x 파손 시 `adapters/agent/` 한 파일만 |
| 검증 | `langchain` 을 경계 테스트 금지 목록에 넣어 CI 가 감시 |

**프레임워크가 도메인으로 스며들면 버전이 바뀔 때 도메인 로직까지 끌려간다.** LangChain 은 1.x 가 나오면서 0.x 의 LCEL 패턴이 크게 바뀌었다 — 이 격리가 그런 변화를 한 파일에 가둔다.

### 2.4 불변 규칙: `core/` 는 프레임워크를 import 하지 않는다

문서가 아니라 테스트로 강제한다. `backend/tests/test_boundaries.py` 가 `core/` 의 import 를 AST 로 검사한다.

```
바깥 계층        adapters · api · pipeline · eval
인프라·프레임워크  psycopg · sqlalchemy · anthropic · fastapi
                langchain · langgraph · sentence_transformers · torch
```

### 2.5 모델 스택

| 구분 | 선택 | 근거 |
|---|---|---|
| 임베딩 | `intfloat/multilingual-e5-small` (384차원, max_seq 512, 449MB) | **cross-lingual** — 한국어 질의로 한국어 규정과 영문 로그를 동시에 검색 |
| 생성 LLM | Claude (Anthropic API) | 도구 선택 · 리포트 생성 |
| 에이전트 런타임 | LangChain 1.3 / LangGraph 1.2 | 요구사항 명시. `adapters/` 에 격리 |
| DB | PostgreSQL 16 + pgvector | HNSW 인덱스 + GIN 전문검색 |

**cross-lingual 이 이 프로젝트에서 값을 하는 지점:**

```
질의(한국어)   "인증 실패가 반복된 계정"
규정(한국어)   "2.6.1 네트워크 접근 통제"
로그(영문)     "authentication failure; logname= uid=0 ..."
```

한국어 질의 하나로 한국어 규정과 영문 로그를 **번역 단계 없이** 검색한다.

---

## 3. 데이터 모델

### 3.1 권한 모델 — 단순해야 사전 필터링이 된다

```python
@dataclass(frozen=True)
class Principal:
    department: str        # "보안팀" · "인사팀" · "개발팀"
    clearance: int         # 1(사원) · 2(팀장) · 3(임원)
```

가시성 규칙은 두 줄이다.

```python
def visible(doc: Document, p: Principal) -> bool:
    return doc.required_clearance <= p.clearance and (
        not doc.allowed_departments or p.department in doc.allowed_departments
    )
```

**단순하게 유지한 이유가 있다.** 이 규칙이 SQL `WHERE` 로 그대로 번역되어야 사전 필터링이 된다. RBAC·ABAC 처럼 복잡해지면 애플리케이션 레이어로 밀려나고, 그 순간 사후 필터링이 된다.

### 3.2 스키마

```sql
documents (
    id, title, source_path, doc_type,          -- pdf | docx | md
    required_clearance  INT     NOT NULL,
    allowed_departments TEXT[],                 -- NULL = 전사 공개
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now()
)

clauses (                                       -- ISMS-P 의 조항 구조를 살린다
    id, document_id, code, title, text          -- code: "2.6.1"
)

chunks (
    id, document_id, clause_id, ordinal, text,
    embedding vector(384),                      -- HNSW
    text_tsv  tsvector                          -- GIN
)

log_events (
    id, ts, host, process, event_type,          -- auth_failure | session_open | ...
    principal_name, raw, severity
)

principals (id, name, department, clearance)
```

**`clauses` 를 따로 둔 이유:** ISMS-P 는 `2.6.1 네트워크 접근` 같은 조항 체계를 갖는다. 청크가 어느 조항에 속하는지 알면 리포트에서 **"규정 2.6.1 위반"** 이라고 정확히 인용할 수 있다. 청크 텍스트만 있으면 "어딘가에 이런 내용이 있다"까지밖에 못 쓴다.

---

## 4. 데이터 확보 — 실물 확인 완료

**설계 전에 실물을 받아 확인했다.** 앞선 프로젝트에서 데이터 확인을 늦게 해 계획이 두 번 뒤집힌 경험이 있다.

### 4.1 보안 규정 문서

| 항목 | 확인 결과 |
|---|---|
| **ISMS-P 인증기준 안내서** | 인증 없이 즉시 다운로드 · **10MB · 255쪽** |
| 텍스트 레이어 | **추출 정상** (스캔 이미지가 아님) |
| 언어 | 한국어 |

받는 곳: `https://www.isac.or.kr/upload/ISMS-P 인증기준 안내서(2022.4.22).pdf`
KISA 공식 자료실(`isms.kisa.or.kr`)에도 최신본이 있으나 직접 링크가 세션에 묶여 있어 브라우저로 받아야 한다.

**권한 메타데이터는 합성한다.** 공개 표준 문서에는 부서·등급 정보가 없다. 문서를 조항 단위로 쪼갠 뒤 `required_clearance` 와 `allowed_departments` 를 부여하며, **합성한 사실을 문서에 명시한다.** 본문은 진짜, 권한 구조는 설계 — 둘 다 얻는다.

### 4.2 감사 로그

| 항목 | 확인 결과 |
|---|---|
| **loghub Linux_2k.log** | HTTP 200 · **1,999줄** |
| 보안 이벤트 | **인증 실패 490건 · 세션 오픈 123건** |
| 추가 소스 | `OpenSSH_2k.log` · `Apache_2k.log` 접근 가능 |

받는 곳: `https://raw.githubusercontent.com/logpai/loghub/master/Linux/Linux_2k.log`
전체 데이터셋은 `github.com/logpai/loghub` 에서 받는다.

**호스트명·사용자명을 사내 시스템처럼 정규화한다.** 원본의 `combo sshd(pam_unix)` 를 그대로 노출하면 "사내 감사 로그"라는 설정과 어긋난다. `HR-SRV-01` 같은 형태로 매핑하고 `principals` 와 연결하되, **원본을 `raw` 컬럼에 보존하고 매핑 사실을 명시한다.**

---

## 5. Access Control — 사전 필터링

### 5.1 핵심 SQL

```sql
SELECT c.id, c.text, d.title, cl.code
FROM chunks c
JOIN documents d   ON d.id = c.document_id
LEFT JOIN clauses cl ON cl.id = c.clause_id
WHERE d.required_clearance <= %(clearance)s
  AND (d.allowed_departments IS NULL OR %(dept)s = ANY(d.allowed_departments))
ORDER BY c.embedding <=> %(qvec)s
LIMIT %(k)s
```

**`WHERE` 가 `ORDER BY` 보다 먼저 적용된다.** 권한 없는 문서는 후보에 들어오지도 않고, `LIMIT k` 가 항상 채워진다.

### 5.2 누출 경로 세 가지를 각각 막는다

| 경로 | 사후 필터링에서 무슨 일이 나는가 | 대응 |
|---|---|---|
| **개수** | 권한 없는 것을 제거해 결과가 줄어든다 | `WHERE` 를 먼저 적용해 항상 k 개 |
| **순위** | 상위권에서 빠진 자리가 비어 존재가 드러난다 | 후보 집합 자체가 다르므로 비교 불가 |
| **타이밍** | 걸러낼 것이 많을수록 느려진다 | 인덱스가 필터를 포함해 후보 수에 비례하지 않음 |

**타이밍 누출은 대부분의 구현이 놓친다.** 이걸 테스트로 갖고 있는 것 자체가 위협 모델을 이해했다는 증거다.

### 5.3 도구 시그니처로 권한을 강제한다

```python
def search_policy(query: str, principal: Principal, k: int) -> list[PolicyHit]:
```

`principal` 이 **필수 인자**다. 권한 없는 검색을 호출하는 방법이 없다 — 잊어버릴 수 없다. LangChain 이 이 함수를 감쌀 때도 시그니처가 그대로 유지된다.

### 5.4 도구 출력 검증

LangChain 은 도구가 돌려준 것을 그대로 LLM 에 넘긴다. **권한 없는 문서가 도구 출력에 섞이면 프레임워크는 막지 않는다.**

`core/agent/policy.py` 가 출력을 한 번 더 검사한다.

```python
def enforce(hits: list[PolicyHit], p: Principal) -> list[PolicyHit]:
    """도구 출력에 권한 밖 항목이 있으면 예외를 던진다.

    정상 경로에서는 절대 발동하지 않는다 — 발동했다는 것은 사전 필터링이
    깨졌다는 뜻이고, 조용히 걸러내면 그 사실이 묻힌다.
    """
```

**조용히 걸러내지 않고 예외를 던진다.** 걸러내면 사후 필터링이 되고, 버그가 숨는다.

---

## 6. 검색 파이프라인

### 6.1 하이브리드 검색 + RRF

```
V  벡터    chunks.embedding    질의 임베딩과 코사인        top 50
K  키워드  chunks.text_tsv     ts_rank                     top 50
```

**두 결과를 RRF 로 융합한다:** `score = Σ 1/(60 + rank_i)`

가중 합산이 아닌 이유는 두 점수의 스케일이 다르기 때문이다 — 코사인은 0~1, `ts_rank` 는 임의 스케일이다. 정규화하려면 분포를 조사하고 계수를 튜닝해야 하는데, 3~4주 일정에서 그럴 여유가 없다. RRF 는 순위만 쓰므로 튜닝할 파라미터가 사실상 없다.

**두 검색기 모두 같은 `WHERE` 절로 권한 필터를 적용한다.** 한쪽만 적용하면 그쪽으로 누출된다.

### 6.2 규정 검색과 로그 검색은 다른 경로다

| | 권한 필터 | 이유 |
|---|---|---|
| 규정 검색 | **적용** | 문서마다 열람 등급이 다르다 |
| 로그 검색 | **적용** | 부서별로 볼 수 있는 시스템이 다르다 |

로그도 권한을 받는다. `log_events` 에 `host` 가 있고, 부서별 접근 가능 호스트를 매핑한다.

---

## 7. 에이전트와 도구

### 7.1 도구 3개

```python
search_policy(query: str, principal: Principal, k: int) -> list[PolicyHit]
    # 권한 반영된 규정 청크 + 조항 코드

query_logs(event_type: str | None, since: str | None,
           principal: Principal, limit: int) -> list[LogEvent]
    # 구조화된 로그 이벤트. 부서별 호스트 필터 적용

draft_report(finding: str, clauses: list[ClauseRef],
             events: list[LogEvent]) -> Report
    # 위반 사항 + 근거 조항 + 조치 가이드
```

**세 도구 모두 `principal` 을 받거나(검색), 이미 권한이 적용된 결과만 받는다(리포트).**

### 7.2 실행 정책

```python
MAX_ITERATIONS = 8      # 도구 호출 상한. 넘으면 중단하고 그때까지의 결과로 답한다
```

상한이 없으면 에이전트가 도구를 반복 호출하며 비용과 지연이 무한정 늘어난다. 8회는 "규정 검색 → 로그 조회 → 재검색 → 리포트" 를 두 바퀴 돌 수 있는 여유다.

### 7.3 인용 실재 검증

리포트가 인용한 **조항 코드가 실제로 존재하는지** 프로그램이 검증한다.

```python
def verify_clauses(report: Report, known: set[str]) -> Report:
    """존재하지 않는 조항 인용을 제거한다.

    LLM 은 "2.9.4" 같은 그럴듯한 조항 번호를 지어낸다. 조항 코드는
    clauses 테이블에 있거나 없거나 둘 중 하나이므로, 판단이 필요 없다.
    """
```

**LLM 심판을 쓰지 않는다.** 문자열 매칭으로 확정되는 것에 판단을 끌어들이면 재현성만 잃는다.

---

## 8. 평가와 검증 체계

### 8.1 평가 지표

| 영역 | 지표 | 방식 |
|---|---|---|
| 검색 품질 | Recall@10 · MRR@10 · nDCG@10 | 골든셋 기준 |
| **Faithfulness** | 인용 조항 실재율 | **프로그램 검증** — LLM 심판 불필요 |
| **Access Control** | 개수·순위·타이밍 누출 | 권한별 비교 |
| 지연 | p50 / p95 | |

**RAGAS 라이브러리를 쓰지 않는다.** RAGAS 의 Faithfulness 는 LLM 심판을 쓴다. 우리는 조항 코드의 실재를 문자열로 확정할 수 있으므로 결정론적으로 잰다 — **개념은 차용하되 측정은 재현 가능하게** 한다.

### 8.2 누출 테스트

```python
def test_결과_개수가_권한에_따라_달라지지_않는다():
    """사후 필터링이면 반드시 실패한다."""
    임원 = search_policy(질의, Principal("인사팀", 3), k=10)
    사원 = search_policy(질의, Principal("인사팀", 1), k=10)
    assert len(사원) == len(임원) == 10


def test_동일_문서의_순위가_권한에_따라_흔들리지_않는다():
    """두 권한 모두에게 보이는 문서는 상대 순위가 같아야 한다."""


def test_응답시간_차이가_유의하지_않다():
    """후보를 많이 걸러낼수록 느려지면 그 지연이 신호가 된다."""


def test_도구_출력에_권한_밖_항목이_있으면_예외가_난다():
    """policy.enforce 가 조용히 걸러내지 않고 터지는지 확인한다."""
```

### 8.3 경계 강제 테스트

`core/` 의 import 를 AST 로 검사한다. 파일별로 parametrize 해서 어느 파일이 어겼는지 실패 메시지에 나온다.

**테스트가 실제로 위반을 잡는지 매번 확인한다** — 일부러 어겨보고 실패하는 것을 본 뒤 원복한다. 통과하는 테스트는 그 자체로는 아무것도 증명하지 않는다.

### 8.4 검증 기록을 1급 산출물로 남긴다

Jekyll `/verification/` 에 **장치가 실제로 잡아낸 것**을 쌓는다. 개발 로그 훅이 커밋마다 자동으로 채운다.

"검증 체계를 만들었다"가 아니라 **"그 체계가 이것들을 잡았다"** 를 보여주는 자리다.

한계도 함께 적는다 — 장치가 없는 영역은 검증되지 않고, 테스트가 옳다는 보장도 없으며, 자동화는 설계 결함을 못 잡는다. 그래서 서브에이전트 리뷰를 병행한다.

---

## 9. 마일스톤 (3~4주)

시작 2026-08-31.

| 주차 | 목표 | 완료 판정 |
|---|---|---|
| **W1** | 문서 파싱 · pgvector 적재 · 하이브리드 검색 · 경계 테스트 | ISMS-P 255쪽이 청크로 적재되고 검색이 된다 |
| **W2** | Access Control 사전 필터링 · 누출 테스트 · 평가 하네스 | **권한별로 결과가 다르고, 누출 테스트가 통과한다** |
| **W3** | 에이전트(도구 3개) · 최소 UI · **배포** | 도메인에서 돌아간다 |
| **W4** | 로그 조회 도구 · 리포트 생성 · 다듬기 | 이력서에 건다 |

**W3 끝에 배포한다.** 배포된 URL 이 이 프로젝트의 목적이므로 늦추지 않는다. 처음 배포에서 나오는 문제(환경변수·모델 파일 크기·DB 연결·메모리)는 예측이 안 되고, 마지막에 몰면 실패한다.

**시연 계정 3개를 심어둔다** — 사원·팀장·임원. 같은 질문을 세 계정으로 던지면 결과가 달라지는 것이 화면에서 보인다. 이 프로젝트에서 가장 강한 한 장면이다.

---

## 10. 리스크

| 리스크 | 대응 |
|---|---|
| **LangChain 1.x API 를 기억으로 쓰면 막힌다** | 0.x 의 LCEL 패턴이 크게 바뀌었다. 계획을 쓸 때 공식 문서를 확인하며 쓴다 |
| **도구 출력 누출** | 프레임워크는 도구 결과를 그대로 LLM 에 넘긴다. `policy.enforce` 가 예외를 던져 막고, 누출 테스트가 이 경로를 검사한다 |
| PDF 파싱 품질 | 255쪽 안내서는 표·목록이 많다. 청킹이 조항 경계를 깨면 인용이 부정확해진다 → 조항 코드 패턴(`\d+\.\d+\.\d+`)으로 먼저 분할한 뒤 청킹 |
| 권한 메타데이터가 합성 | 공개 표준에는 등급 정보가 없다. 합성한 사실을 명시하고, **본문은 진짜**임을 함께 밝힌다 |
| 로그가 영문 시스템 로그 | 호스트·사용자명을 사내 형태로 매핑하되 원본을 보존하고 매핑 사실을 명시한다 |
| 3~4주 일정 | P1 을 미리 정해두고 밀리면 아래에서 위로 자른다 (1.3) |

---

## 11. 결정 기록

되돌리기 어려운 순서로.

1. **권한 필터링은 사전(pre-filter)** — 사후 필터링은 개수·순위·타이밍으로 존재를 누출한다. `WHERE` 를 `ORDER BY` 앞에 둔다 (5.1)
2. **권한 모델을 단순하게 유지** — SQL `WHERE` 로 번역되지 않으면 애플리케이션 레이어로 밀려나고, 그 순간 사후 필터링이 된다 (3.1)
3. **LangChain 은 `adapters/` 에만** — 프레임워크가 도메인에 스며들면 버전 변화가 도메인을 끌고 간다. 경계 테스트가 강제한다 (2.3, 2.4)
4. **도구 시그니처가 권한을 강제** — `principal` 이 필수 인자라 권한 없는 검색을 호출할 방법이 없다 (5.3)
5. **도구 출력 검증은 예외를 던진다** — 조용히 걸러내면 사후 필터링이 되고 버그가 숨는다 (5.4)
6. **Faithfulness 를 LLM 심판으로 재지 않는다** — 조항 코드의 실재는 문자열로 확정된다 (7.3, 8.1)
7. **cross-lingual 임베딩** — 한국어 질의로 한국어 규정과 영문 로그를 번역 없이 검색 (2.5)
8. **RRF 융합** — 스케일이 다른 점수의 가중 합산을 피한다 (6.1)
9. **검증 기록을 1급 산출물로** — 장치가 무엇을 잡았는지가 방법론의 증거다 (8.4)
10. **W3 끝 배포** — 배포된 URL 이 목적이므로 마지막으로 미루지 않는다 (9)
11. **로그 이상탐지는 P1** — 조회·인용까지만 P0. 모델까지 넣으면 그것만으로 프로젝트 하나다 (1.3)

---

## 12. 다음 단계

이 문서를 입력으로 구현 계획을 작성한다. 서브시스템별로 나눈다.

```
①  문서 파이프라인 + 하이브리드 검색      (W1)
②  Access Control + 누출 테스트 + 평가    (W2)
③  에이전트 + API + UI + 배포             (W3)
④  로그 파이프라인 + 리포트               (W4)
```

각 계획은 그 자체로 동작하고 검증 가능한 소프트웨어를 남긴다.

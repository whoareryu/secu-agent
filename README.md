# Secu-Agent

기업 사내보안 규정 및 감사 로그 분석 AI 에이전트.

📄 **문서 사이트** — https://whoareryu.github.io/secu-agent/

---

## 무엇이 다른가

RAG 챗봇은 흔합니다. **권한에 따라 검색 결과가 달라지는 RAG는 흔하지 않고, 제대로 하기 까다롭습니다.**

```
질의: "임원 성과급 산정 기준이 뭔가요?"   ← 일반 사원이 물음

사후 필터링:  상위 10건 검색 → 권한 검사 → 3건 남음
              결과가 3건인 것 자체가 "숨겨진 문서가 있다"는 신호가 된다

사전 필터링:  권한 통과 문서 중 상위 10건 → 10건
              차이를 관측할 수 없다
```

**"검색은 됐지만 못 보는 문서"의 존재를 감추는 것** — 이것이 이 프로젝트의 기술적 핵심입니다.

## 구조

```
backend/
  core/        안쪽. 프레임워크를 모른다 — 표준 라이브러리만
    types.py     엔티티 · 값 객체
    ports.py     경계 Protocol (안쪽이 소유, 바깥이 구현)
    access/      가시성 규칙 — 순수 함수
    retrieve/    하이브리드 검색 + RRF
    agent/       도구 로직 · 실행 정책
  adapters/    바깥. core 를 안다
    parsing/     PDF · MD · syslog → Chunk
    db/          psycopg + pgvector
    embedding/   multilingual-e5-small
    llm/         Gemini SDK
    agent/       LangChain / LangGraph 런너
  pipeline/    문서 · 로그 적재
  api/         FastAPI
  eval/        평가 하네스 + 누출 테스트
frontend/      Next.js
jekyll/        문서 사이트
```

**LangChain 은 `adapters/` 에만 삽니다.** 도구 로직과 권한 검증은 프레임워크를 모르는 `core/` 에 있어, 버전 변화가 도메인을 오염시키지 못합니다. `backend/tests/test_boundaries.py` 가 이를 강제합니다.

## 데모

`frontend/` 는 구글 로그인 뒤에서 `/ask` 를 제공합니다. 로그인은 권한이
아니라 **요금 게이트**입니다 — `/ask` 뒤에 LLM 이 있어 로그인 없이 열어두면
누구나 API 요금을 쓸 수 있습니다. 알리스트(`ASK_ALLOWLIST`) 밖 계정은 하루
`ASK_DAILY_LIMIT`(기본 10)회로 질의가 제한되고, 넘기면 429 를 받습니다.

`/how` 화면은 이 설계를 말이 아니라 실행으로 보여줍니다. 사전 필터링과
순진한 사후 필터링을 같은 코퍼스에 나란히 돌려 개수 차이를 실시간으로
보여주고, 2단계 누출 · 접근 기록이 담지 않는 컬럼 · 문서와 로그가 같은
권한 판정 함수를 공유한다는 사실까지 네 패널로 정리합니다. 사후 필터링
경로(`backend/demo/naive_search.py`)는 저장소에 실제로 존재하고 의도적으로
샙니다 — 그러나 **답변 경로(`/ask`)** 에는 닿지 않습니다.
`backend/tests/test_demo_isolation.py` 의
`test_api_에서_demo_에_닿는_파일은_정확히_둘이다` 가 `demo` 에 한 홉으로 닿는
`api/` 아래 파일이 `api/demo.py`(비교 라우터)와 `api/deps.py`(그 라우터를
조립하는 지점) 둘뿐임을 부분집합이 아니라 집합 동일성으로 강제하고,
`core`·`adapters`·`pipeline`·`eval` 은 아예 닿지 못합니다. 라우터 자체는
프로덕션 앱에 마운트돼 있고 `demo/` 모듈도 프로덕션 이미지에 들어갑니다 —
막는 것은 배포가 아니라 답변 경로와의 연결입니다.

## 권한에 따라 결과가 달라진다

같은 질문을 세 계정으로 던집니다. 시연 계정은 열 명이라 `--persona` 로
셋만 봅니다 — 붙여둔 출력이 명령의 전부여야 하기 때문입니다.

```
$ python -m pipeline.cli demo "임원 성과급은 어떤 기준으로 정해지나" \
    --persona 김개발 --persona 박인사 --persona 최임원

질의: "임원 성과급은 어떤 기준으로 정해지나"

── 김개발 (개발팀 · 등급 1) — 5건
   1. [1.1.2] ISMS-P 인증기준 안내서
   2. [1.1.2] ISMS-P 인증기준 안내서
   3. [1.1.2] ISMS-P 인증기준 안내서
   4. [2.2.4] ISMS-P 인증기준 안내서
   5. [2.2.6] ISMS-P 인증기준 안내서

── 박인사 (인사팀 · 등급 2) — 5건
   1. [1.1.2] ISMS-P 인증기준 안내서
   2. [1.1.2] ISMS-P 인증기준 안내서
   3. [1.1.2] ISMS-P 인증기준 안내서
   4. [2.2.4] ISMS-P 인증기준 안내서
   5. [2.2.6] ISMS-P 인증기준 안내서

── 최임원 (경영지원팀 · 등급 3) — 5건
   1. [6.1.2] 임원 성과급 산정 기준
   2. [1.1.2] ISMS-P 인증기준 안내서
   3. [1.1.2] ISMS-P 인증기준 안내서
   4. [6.1.1] 임원 성과급 산정 기준
   5. [6.1.3] 임원 성과급 산정 기준
```

**세 계정의 결과 개수가 같습니다.** 최임원만 `6.1.1` 을 받고, 나머지 둘은 다른 문서로 채워진 같은 개수의 결과를 받습니다 — 숨겨진 문서가 있다는 신호가 개수에도 순위에도 남지 않습니다.

두 번째 질의는 부서 축을 보여줍니다.

```
$ python -m pipeline.cli demo "운영 서버에 접속하려면 어떤 승인이 필요한가" -k 10 \
    --persona 김개발 --persona 박인사 --persona 최임원

질의: "운영 서버에 접속하려면 어떤 승인이 필요한가"

── 김개발 (개발팀 · 등급 1) — 10건
   1. [2.8.4] ISMS-P 인증기준 안내서
   2. [2.8.6] ISMS-P 인증기준 안내서
   3. [2.6.2] ISMS-P 인증기준 안내서
   4. [5.1.1] 개발팀 서버 접근 절차
   5. [2.6.2] ISMS-P 인증기준 안내서
   6. [2.6.1] ISMS-P 인증기준 안내서
   7. [1.3.2] ISMS-P 인증기준 안내서
   8. [2.4.4] ISMS-P 인증기준 안내서
   9. [2.6.4] ISMS-P 인증기준 안내서
   10. [2.8.6] ISMS-P 인증기준 안내서

── 박인사 (인사팀 · 등급 2) — 10건
   1. [2.8.4] ISMS-P 인증기준 안내서
   2. [2.8.6] ISMS-P 인증기준 안내서
   3. [2.6.2] ISMS-P 인증기준 안내서
   4. [2.6.1] ISMS-P 인증기준 안내서
   5. [1.3.2] ISMS-P 인증기준 안내서
   6. [2.6.2] ISMS-P 인증기준 안내서
   7. [2.4.4] ISMS-P 인증기준 안내서
   8. [2.8.6] ISMS-P 인증기준 안내서
   9. [2.6.4] ISMS-P 인증기준 안내서
   10. [2.10.3] ISMS-P 인증기준 안내서

── 최임원 (경영지원팀 · 등급 3) — 10건
   1. [2.8.4] ISMS-P 인증기준 안내서
   2. [2.8.6] ISMS-P 인증기준 안내서
   3. [2.6.2] ISMS-P 인증기준 안내서
   4. [2.6.1] ISMS-P 인증기준 안내서
   5. [1.3.2] ISMS-P 인증기준 안내서
   6. [2.6.2] ISMS-P 인증기준 안내서
   7. [2.4.4] ISMS-P 인증기준 안내서
   8. [2.8.6] ISMS-P 인증기준 안내서
   9. [2.6.4] ISMS-P 인증기준 안내서
   10. [2.10.3] ISMS-P 인증기준 안내서
```

여기서는 등급이 아니라 부서가 갈립니다. `5.1.1 개발팀 서버 접근 절차` 는 개발팀 전용 문서라 김개발에게만 4위로 뜨고, 박인사와 최임원에게는 그 자리부터 한 칸씩 밀린 ISMS-P 조항이 채워집니다. 최임원은 등급이 가장 높은데도 이 문서를 못 보는데, 등급이 부서를 덮어쓰지 않는다는 뜻입니다. 세 계정 모두 정확히 10건을 받아, 숨겨진 문서의 자리가 비지 않고 다른 조항으로 채워진다는 것이 말이 아니라 출력으로 드러납니다.

시연 계정과 사내 규정 문서는 합성입니다. ISMS-P 안내서는 본문이 실제 공개 표준이고 권한 등급만 부여했습니다.

## 검색 품질

골든셋 30건(ISMS-P 25 · 사내 규정 5), k=10, 코퍼스 338청크 기준.

| 지표 | 값 |
|---|---|
| Recall@10 | 0.867 |
| MRR@10 | 0.543 |
| nDCG@10 | 0.620 |
| 지연 p50 / p95 | 18ms / 38ms |

```bash
cd backend && .venv/bin/python -m eval.run --per-query
```

지연은 로컬 컨테이너 기준입니다. 한 번 p95 70ms 가 관측되었으나 이후 재실행에서 재현되지 않았습니다(21~33ms).

**MRR·nDCG 가 이전 값(0.577 · 0.644)보다 낮습니다 — 코퍼스를 고쳤기 때문입니다.**
ISMS-P 안내서의 불릿은 심볼 폰트로 찍혀 있어 pypdf 가 유니코드 사설 사용
영역(PUA) 코드포인트로 뽑아냈고, 그것이 청크 본문에 그대로 남아 있었습니다 —
338청크 중 310개, 2,062자. 화면에는 tofu 박스로 보이고 LLM 프롬프트에는
의미 없는 토큰으로 들어갔습니다. `adapters/parsing/pdf.py` 가 이제 이것을
정리합니다.

정리하면 순위 지표가 내려갑니다. 네 가지를 실측하고 골랐습니다:

| 처리 | 청크 | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---|---|---|
| 유지(이전) | 338 | 0.867 | 0.577 | 0.644 |
| **가운뎃점(현재)** | 338 | 0.867 | **0.526** | **0.607** |
| 공백 | 338 | 0.833 | 0.553 | 0.619 |
| 제거 | 337 | 0.867 | 0.531 | 0.612 |

이 표의 네 값은 의존성을 고정하기 **전**에 잰 것이라 위 표(0.543 · 0.620)와
어긋난다. 서로 비교하는 용도로만 읽는다.

길이가 1:1 이라 청크 경계가 움직이지 않는 변형에서도 내려가므로, 원인은
경계 이동이 아니라 토크나이제이션입니다 — PUA 는 e5 토크나이저에서 미지
토큰이고, 그 자리에 실제 토큰이 들어가면 문서 벡터가 움직입니다.
**Recall@10 은 그대로입니다** — 정답 조항을 못 찾게 된 것이 아니라 같은
문서들의 순서가 바뀐 것입니다. 골든셋은 청크 id 가 아니라 조항 코드로
정답을 적으므로 재적재가 정답 자체를 흔들지는 않습니다.

낮은 수치를 그대로 싣는 이유는, 읽을 수 없는 글자가 섞인 코퍼스에서 나온
높은 수치보다 고친 코퍼스에서 나온 낮은 수치가 재현 가능하기 때문입니다.

**같은 코퍼스에서 수치가 한 번 더 움직였습니다** — 0.526 → 0.543. 재적재하지
않았고(청크 338개 · PUA 0자로 동일), 검색 코드도 인자 검증 한 줄 외에는
그대로입니다. 그 사이에 바뀐 것은 의존성 스택뿐입니다: `uv.lock` 이 1,403줄
빠진 채였고, 다시 만들어 `uv sync --frozen` 으로 갈아끼웠습니다. 즉 **잠금
파일을 고치기 전에는 어느 숫자도 재현할 수 없었습니다** — 같은 커밋을 다른
날 받아도 다른 스택에서 돌았기 때문입니다. 위 표의 값은 잠긴 스택에서 잰
것이고, 이제 `uv sync --frozen` 을 쓰면 같은 값이 나옵니다(3회 반복 확인).

Faithfulness 는 아직 붙이지 않았습니다. LLM 심판이 아니라 답변에 인용된 조항
코드가 실제 `hits` 에 있는지로 재려 했으나, 그 대조를 하는 코드가 아직
없습니다 — `eval/` 은 현재 검색 품질(recall · MRR · nDCG)만 잽니다.

## 실행

빈 머신에서 이 순서를 그대로 따르면 섭니다. **`docker compose up -d` 만으로는
안 됩니다** — compose 는 스키마를 적용하지 않고, 적재도 하지 않습니다.
API 는 `apply_schema()` 를 부르지 않으므로 빈 DB 위에서도 뜨고 `/healthz` 는
`ok` 를 돌려줍니다(빈 테이블 조회도 성공하므로). 그 상태에서 `/ask` 만 깨집니다.

**1. 코퍼스의 대부분인 ISMS-P 안내서는 저장소에 없습니다.** 공개 PDF 라
받아옵니다(약 10MB).

```bash
mkdir -p data/raw
curl -L -o data/raw/ismsp.pdf \
  "https://www.isac.or.kr/upload/ISMS-P%20%EC%9D%B8%EC%A6%9D%EA%B8%B0%EC%A4%80%20%EC%95%88%EB%82%B4%EC%84%9C(2022.4.22).pdf"
```

사내 규정 8건(`data/policies/`)·계정·호스트·로그는 저장소에 있습니다.

**2. 환경 변수와 컨테이너.**

```bash
cp .env.example .env      # BACKEND_SHARED_SECRET 는 반드시 새로 만든다
docker compose up -d      # db(5433) + secu-backend(8080)
```

`BACKEND_SHARED_SECRET` 이 비어 있으면 compose 가 기동을 거부합니다 —
의도된 fail-closed 입니다. `.env.example` 의 예시 값은 저장소 히스토리에
공개돼 있으니 그대로 쓰지 마세요.

**3. 스키마와 적재.** 적재 서브커맨드가 `apply_schema()` 를 부르므로
스키마는 첫 명령이 만듭니다.

```bash
cd backend
.venv/bin/python -m pipeline.cli ingest ../data/raw/ismsp.pdf --title "ISMS-P 인증기준 안내서"
.venv/bin/python -m pipeline.cli ingest-dir ../data/policies
.venv/bin/python -m pipeline.cli seed-principals
.venv/bin/python -m pipeline.cli seed-hosts
.venv/bin/python -m pipeline.cli ingest-logs ../data/logs/2026-08-31.log --year 2026
.venv/bin/python -m pipeline.cli ingest-logs ../data/logs/2026-09-01.log --year 2026
```

**4. 확인.** 여기까지 오면 아래가 그대로 나와야 합니다.

```bash
curl -s localhost:8080/healthz     # {"status":"ok","db":true,"model":"ready"}
cd backend && .venv/bin/python -m pytest -m corpus -v   # 코퍼스가 우리가 아는 그것인지
```

적재 명령이 마지막에 찍는 `DB 총 청크` 가 **338** 이어야 합니다. 아니면
1번이 빠졌거나 다른 개정판을 받은 것입니다(문서 9 · 조항 102 · 청크 338).

프론트엔드는 `frontend/README.md` 를 보세요.

## 개발

```bash
cd backend
uv sync                       # 또는: pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest
```

모든 파이썬 명령은 `backend/` 에서 실행합니다.

DB·임베딩 모델이 필요한 테스트는 기본 스위트에서 제외됩니다:

```bash
# DB 테스트 — 작업 데이터베이스(secuagent)가 아니라 별도의 secuagent_test 를
# 씁니다. db 테스트는 TRUNCATE 로 시작하므로 작업 코퍼스에 대고 돌리면
# 안 됩니다. SECUAGENT_TEST_DSN 으로 위치를 바꿀 수 있고, 없으면
# secuagent_test 를 자동으로 만들어 씁니다.
docker compose up -d
cd backend && .venv/bin/python -m pytest -m db -v

# 코퍼스 테스트 — 작업 데이터베이스(secuagent)를 읽기 전용 연결로 검사합니다.
# 실제 문서·계정 코퍼스가 우리가 아는 그것인지 확인하는 용도라 별도
# 데이터베이스로 옮길 수 없습니다. 읽기 전용은 Postgres 세션 특성으로
# 강제되어 이 연결로는 쓰기가 애초에 실행되지 않습니다.
cd backend && .venv/bin/python -m pytest -m corpus -v

# 임베딩 모델 테스트 (첫 로드에 ~30초)
cd backend && .venv/bin/python -m pytest -m model -v
```

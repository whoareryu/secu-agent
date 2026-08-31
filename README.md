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
    parsing/     PDF · DOCX · MD → Chunk
    db/          psycopg + pgvector
    embedding/   multilingual-e5-small
    llm/         Anthropic SDK
    agent/       LangChain / LangGraph 런너
  pipeline/    문서 · 로그 적재
  api/         FastAPI
  eval/        평가 하네스 + 누출 테스트
frontend/      Next.js
jekyll/        문서 사이트
```

**LangChain 은 `adapters/` 에만 삽니다.** 도구 로직과 권한 검증은 프레임워크를 모르는 `core/` 에 있어, 버전 변화가 도메인을 오염시키지 못합니다. `backend/tests/test_boundaries.py` 가 이를 강제합니다.

## 개발

```bash
cd backend
uv sync                       # 또는: pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest
```

모든 파이썬 명령은 `backend/` 에서 실행합니다.

DB·임베딩 모델이 필요한 테스트는 기본 스위트에서 제외됩니다:

```bash
# DB 테스트
docker compose up -d
cd backend && .venv/bin/python -m pytest -m db -v

# 임베딩 모델 테스트 (첫 로드에 ~30초)
cd backend && .venv/bin/python -m pytest -m model -v
```

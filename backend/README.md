# backend

파이썬 백엔드 — 도메인 로직 · 데이터 파이프라인 · 평가 하네스 · API.

```bash
cd backend
uv sync --group finetune      # 또는: pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest
```

**모든 파이썬 명령은 `backend/` 에서 실행한다.** `pyproject.toml` 의 `testpaths`
와 `db/schema.sql` 을 읽는 테스트가 이 디렉토리를 기준으로 한다.

## 계층

```
core/        안쪽. 바깥을 모른다 — 표준 라이브러리만 쓴다
  types.py     엔티티 · 값 객체
  ports.py     경계 Protocol (안쪽이 소유, 바깥이 구현)
  ontology/    도메인 서비스 (LLM·DB 무관)
  retrieve/    유스케이스 — ports 에만 의존
adapters/    바깥. core 를 안다
  db/          psycopg
  source/      원천 데이터셋 파서
  embedding/   sentence-transformers
  llm/         Gemini SDK
pipeline/    오프라인 배치 — adapters 를 조립해 실행
api/         FastAPI — 얇은 HTTP 계층
eval/        평가 하네스 — ports 스텁으로 테스트
db/          schema.sql
```

의존성은 **항상 안쪽을 향한다**. `backend/tests/test_boundaries.py` 가 이를 강제한다.

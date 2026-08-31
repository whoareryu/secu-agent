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

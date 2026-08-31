"""DocumentStore 의 psycopg 구현.

core/ports 의 Protocol 을 만족한다. 도메인은 이 파일을 모른다 — 의존성은
adapters → core 한 방향이다.
"""

from collections.abc import Sequence

import psycopg

from core.types import Chunk, Clause, Document

Vector = list[float]


class PgDocumentStore:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def upsert_document(self, doc: Document) -> int:
        """UNIQUE(source_path) 충돌 시 갱신한다.

        DO NOTHING 이 아니라 DO UPDATE 인 이유: 권한 등급을 바꾼 뒤 재적재로
        반영할 수 있어야 한다. RETURNING 은 삽입이든 갱신이든 id 를 돌려준다.

        allowed_departments 는 비어 있으면 NULL 로 넣는다 — 빈 배열과 NULL 을
        섞으면 SQL 필터에 조건이 하나 더 붙는다.
        """
        depts = list(doc.allowed_departments) or None
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents
                        (title, source_path, doc_type, required_clearance, allowed_departments)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (source_path) DO UPDATE SET
                        title = EXCLUDED.title,
                        doc_type = EXCLUDED.doc_type,
                        required_clearance = EXCLUDED.required_clearance,
                        allowed_departments = EXCLUDED.allowed_departments
                    RETURNING id
                    """,
                    (doc.title, doc.source_path, doc.doc_type, doc.required_clearance, depts),
                )
                doc_id = cur.fetchone()[0]
            self.conn.commit()
            return doc_id
        except Exception:
            self.conn.rollback()
            raise

    def insert_clauses(self, document_id: int, clauses: Sequence[Clause]) -> dict[str, int]:
        out: dict[str, int] = {}
        try:
            with self.conn.cursor() as cur:
                for c in clauses:
                    cur.execute(
                        """
                        INSERT INTO clauses (document_id, code, title, text)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (document_id, code) DO UPDATE SET
                            title = EXCLUDED.title, text = EXCLUDED.text
                        RETURNING id, code
                        """,
                        (document_id, c.code, c.title, c.text),
                    )
                    cid, code = cur.fetchone()
                    out[code] = cid
            self.conn.commit()
            return out
        except Exception:
            self.conn.rollback()
            raise

    def insert_chunks(
        self,
        document_id: int,
        clause_ids: dict[str, int],
        chunks: Sequence[Chunk],
        vectors: Sequence[Vector],
    ) -> int:
        """청크를 저장한다.

        text_tsv 를 to_tsvector 로 여기서 채운다. 비워두면 키워드 검색이
        조용히 0건을 낸다 — 에러가 아니라 빈 결과라 발견이 늦다.

        실패하면 롤백한다. 실패한 statement 는 커넥션을 aborted 상태로
        남기고, 그 상태에서 나온 다음 문서의 에러 메시지는 진짜 원인이 아니라
        "current transaction is aborted" 라 배치 적재에서 원인 추적이 막힌다.
        """
        if len(chunks) != len(vectors):
            raise ValueError(f"청크 {len(chunks)}개와 벡터 {len(vectors)}개의 수가 다르다")
        if not chunks:
            return 0

        try:
            with self.conn.cursor() as cur:
                for ch, vec in zip(chunks, vectors, strict=True):
                    cur.execute(
                        """
                        INSERT INTO chunks
                            (document_id, clause_id, ordinal, text, embedding, text_tsv)
                        VALUES (
                            %(doc)s, %(clause)s, %(ord)s, %(text)s, %(vec)s,
                            to_tsvector(
                                'simple',
                                coalesce(
                                    (SELECT cl.code || ' ' || cl.title
                                       FROM clauses cl WHERE cl.id = %(clause)s),
                                    ''
                                ) || ' ' || %(text)s
                            )
                        )
                        """,
                        {
                            "doc": document_id,
                            "clause": clause_ids.get(ch.clause_code) if ch.clause_code else None,
                            "ord": ch.ordinal,
                            "text": ch.text,
                            "vec": str(vec),
                        },
                    )
            self.conn.commit()
            return len(chunks)
        except Exception:
            self.conn.rollback()
            raise

    def count_chunks(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM chunks")
            return cur.fetchone()[0]

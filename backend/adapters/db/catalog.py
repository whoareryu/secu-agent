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
            return [
                PrincipalRow(name=r[0], department=r[1], clearance=r[2]) for r in cur.fetchall()
            ]

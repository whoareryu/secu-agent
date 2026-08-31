"""ChunkSearch 의 psycopg 구현.

WHERE 절이 ORDER BY 보다 먼저 적용된다 — 권한 없는 문서는 후보에
들어오지도 않고 LIMIT k 가 항상 채워진다(spec 5.1).

W1 에서는 필터가 사실상 모든 문서를 통과시킨다(전부 clearance 1, 부서 NULL).
그래도 SQL 을 지금 갖춰두는 이유: W2 에서 권한 데이터를 넣는 순간
필터가 저절로 동작해야 한다. 나중에 WHERE 를 끼워 넣으면 빠뜨린 경로가 생긴다.
"""

import re
from collections.abc import Sequence

import psycopg

from core.types import PolicyHit, Principal

Vector = list[float]

# 조항 번호는 한 덩어리로 남겨야 한다. simple 파서도 '2.11.3' 을 한 토큰으로
# 본다(실측). 그래서 점은 낱말 문자로 취급한다.
_낱말 = re.compile(r"[0-9A-Za-z가-힣]+(?:\.[0-9A-Za-z가-힣]+)*")


def 한국어_tsquery(query: str) -> str:
    """자연어 질의를 접두어 OR tsquery 문자열로 바꾼다.

    낱말이 하나도 없으면 빈 문자열을 준다 — 호출부가 그때 빈 결과를 낸다.
    """
    낱말들 = [w for w in _낱말.findall(query) if len(w) >= 2]
    # 중복 낱말은 점수만 부풀리고 결과를 바꾸지 않는다. 순서는 유지한다.
    본_것: set[str] = set()
    고유 = [w for w in 낱말들 if not (w in 본_것 or 본_것.add(w))]
    return " | ".join(f"{w}:*" for w in 고유)


# 권한 필터. 두 검색 메서드가 같은 조건을 쓴다 — 한쪽만 적용하면 그쪽으로 누출된다.
# 전사 공개는 두 가지로 저장될 수 있다: NULL 과 빈 배열.
# core.types.Document 는 allowed_departments=() 를 전사 공개로 정의하고
# upsert_document 는 이를 NULL 로 정규화해 넣는다(adapters/db/document_store.py).
# cardinality(...) = 0 절은 그 정규화를 거치지 않고 빈 배열을 직접 써넣는
# 다른 경로(수동 SQL, 다른 어댑터)에 대비한 방어책이다 — 정규화를 믿지 않고
# 여기서도 한 번 더 받아준다. 실측: 빈 배열을 안 받아주면 그 문서는 자기
# 부서에도 안 보인다 — 조용히 사라진다.
_권한_WHERE = """
    d.required_clearance <= %(clearance)s
    AND (
        d.allowed_departments IS NULL
        OR cardinality(d.allowed_departments) = 0
        OR %(dept)s = ANY(d.allowed_departments)
    )
"""


# 이 SQL 을 모듈 상수로 둔 이유는 테스트가 EXPLAIN 으로 **실제로 실행되는 문장**을
# 검사하기 위해서다. 테스트가 SQL 을 다시 적으면 그건 사본을 검사하는 것이고,
# 구현이 바뀌어도 통과한다.
_벡터_SQL = f"""
    WITH 허용 AS MATERIALIZED (
        SELECT c.id, c.embedding
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE {_권한_WHERE}
    )
    SELECT id
    FROM 허용
    ORDER BY embedding <=> %(qvec)s
    LIMIT %(k)s
"""


class PgChunkSearch:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def by_vector(self, vec: Vector, principal: Principal, k: int) -> list[int]:
        """권한 통과 청크만 모은 뒤 그 안에서 정확 검색한다.

        `AS MATERIALIZED` 가 이 메서드의 핵심이고, 성능이 아니라 **보안** 때문에
        있다. 이것을 빼면 플래너가 CTE 를 인라인해서 HNSW 인덱스를 먼저 타고
        권한 필터를 나중에 적용한다(사후 필터링). 그 순간:

          · HNSW 는 근사 인덱스라 후보를 ef_search 개만 뽑는다
          · 그 후보가 전부 권한 밖 문서면 필터 후 **0건**이 남는다
          · 볼 수 있는 청크가 2,000개 있어도 0건이다

        실측(pgvector:pg16, 공개 2,000 + 기밀 2,000 청크): 인라인되면 등급1
        사용자가 k=10 을 요청해도 `actual rows=0`. `AS MATERIALIZED` 를 붙이면
        10건이 온다.

        이건 정확성 문제이면서 동시에 **누출**이다. 받는 결과 개수가 "내가 못
        보는 곳에 이 질의와 아주 가까운 문서가 있다"를 알려준다 — spec 5.3 이
        금지한 바로 그 채널이다.

        대가는 HNSW 를 못 쓴다는 것이다. 권한 통과 집합에 대한 순차 정확 검색이
        된다. 실측 2.5ms(314청크) / 8.8ms(2,000) / 8.0ms(4,000) 이라 이 프로젝트
        규모에서는 문제가 없다. 코퍼스가 10만 청크를 넘어가면 권한 컬럼을
        chunks 로 비정규화하고 부분 인덱스를 검토해야 한다 — 그때도 근사 인덱스
        위에서 사후 필터링으로 돌아가서는 안 된다.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                _벡터_SQL,
                {
                    "clearance": principal.clearance,
                    "dept": principal.department,
                    "qvec": str(vec),
                    "k": k,
                },
            )
            return [row[0] for row in cur.fetchall()]

    def by_keyword(self, query: str, principal: Principal, k: int) -> list[int]:
        """이 메서드에는 `AS MATERIALIZED` 가 필요 없다 — GIN 은 정확 인덱스라
        조건에 맞는 후보 전체를 내놓으므로, HNSW 처럼 근사 검색이 권한 밖
        후보만 뽑아 사후 필터 결과가 0건이 되는 일이 없다. by_vector 와
        형태를 맞추려고 이걸 옮기거나 빼면 안 된다 — 인덱스 정확도 차이지
        스타일 문제가 아니다.
        """
        tsq = 한국어_tsquery(query)
        if not tsq:
            # 검색할 낱말이 없다. 빈 tsquery 를 넘기면 Postgres 가 NOTICE 를
            # 뿜으므로 여기서 끊는다. 권한과 무관한 경로라 누출과 상관없다.
            return []
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT c.id
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE {_권한_WHERE}
                  AND c.text_tsv @@ to_tsquery('simple', %(q)s)
                ORDER BY ts_rank(c.text_tsv, to_tsquery('simple', %(q)s)) DESC
                LIMIT %(k)s
                """,
                {
                    "clearance": principal.clearance,
                    "dept": principal.department,
                    "q": tsq,  # 원문이 아니라 변환된 tsquery 를 넘긴다
                    "k": k,
                },
            )
            return [row[0] for row in cur.fetchall()]

    def load_hits(self, ids: Sequence[int], principal: Principal) -> list[PolicyHit]:
        """chunk id → PolicyHit. 결과 표시에 쓴다.

        **`principal` 이 필수인 이유:** 이 메서드는 청크 **본문**을 돌려준다.
        권한 검사를 검색 쪽에만 두면, id 를 아는 호출자는 이 경로로 본문을
        그대로 가져갈 수 있다. 존재 누출보다 나쁜 내용 누출이다.
        지금은 호출자가 하나뿐이고 그 호출자가 이미 걸러진 id 만 주지만,
        W3 의 에이전트와 API 가 다른 데서 온 id 를 넘길 새 호출자다.
        spec 5.3 이 "나중에 끼워 넣으면 빠뜨린 경로가 생긴다"고 한 그대로다.

        권한 밖 id 는 **조용히 빠진다.** 예외를 던지면 안 된다 —
        "그 id 는 접근 불가" 라는 응답 자체가 존재 확인이 된다.

        순서는 호출자가 준 id 순서를 따른다 — SQL 의 반환 순서에 기대면
        융합 결과의 순위가 뒤집힌다.
        """
        if not ids:
            return []
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT c.id, c.text, d.title, cl.code,
                       d.required_clearance, d.allowed_departments
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                LEFT JOIN clauses cl ON cl.id = c.clause_id
                WHERE c.id = ANY(%(ids)s)
                  AND {_권한_WHERE}
                """,
                {
                    "ids": list(ids),
                    "clearance": principal.clearance,
                    "dept": principal.department,
                },
            )
            by_id = {
                row[0]: PolicyHit(
                    chunk_id=row[0],
                    text=row[1],
                    doc_title=row[2],
                    clause_code=row[3],
                    required_clearance=row[4],
                    # NULL(전사 공개)은 빈 튜플로 정규화한다. core 쪽 규칙은
                    # 빈 튜플을 전사 공개로 읽으므로 여기서 맞춰준다.
                    allowed_departments=tuple(row[5] or ()),
                )
                for row in cur.fetchall()
            }
        return [by_id[i] for i in ids if i in by_id]

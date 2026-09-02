"""사전·사후 두 경로를 같은 질의로 돌려 비교한다.

임베딩은 한 번만 계산해 여섯 번의 검색이 공유한다. LLM 호출이 없어
이 경로는 요금이 0원이다 — 시연을 몇 번 돌려도 마찬가지다.
"""

from dataclasses import dataclass

import psycopg

from adapters.db.chunk_search import PgChunkSearch
from core.ports import Embedder
from core.types import Principal
from demo.naive_search import naive_ids

MAX_DEMO_K = 20


@dataclass(frozen=True)
class 경로결과:
    count: int
    clause_codes: list[str]


def _조항코드(conn: psycopg.Connection, ids: list[int]) -> list[str]:
    """chunk id → 조항 코드. **본문은 읽지 않는다.**

    순서는 준 id 순서를 따른다 — 순위 채널을 보여주려면 순서가 의미를 갖는다.
    """
    if not ids:
        return []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT c.id, cl.code FROM chunks c"
            " LEFT JOIN clauses cl ON cl.id = c.clause_id"
            " WHERE c.id = ANY(%s)",
            (ids,),
        )
        코드 = dict(cur.fetchall())
    return [코드.get(i) or "조항 밖" for i in ids]


def compare(conn, embedder: Embedder, query: str, k: int, principals: list[tuple[str, Principal]]):
    k = max(1, min(k, MAX_DEMO_K))
    vec = embedder.encode([query], kind="query")[0]
    검색 = PgChunkSearch(conn)

    나온다 = []
    for 이름, p in principals:
        사전 = 검색.by_vector(vec, p, k)
        사후 = naive_ids(conn, vec, p, k)
        나온다.append(
            {
                "name": 이름,
                "department": p.department,
                "clearance": p.clearance,
                "prefiltered": 경로결과(len(사전), _조항코드(conn, 사전)),
                "naive": 경로결과(len(사후), _조항코드(conn, 사후)),
            }
        )
    return {"query": query, "k": k, "personas": 나온다}

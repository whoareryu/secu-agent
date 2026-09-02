"""사전·사후 두 경로를 같은 질의로 돌려 비교한다.

임베딩은 한 번만 계산해 여섯 번의 검색이 공유한다. LLM 호출이 없어
이 경로는 요금이 0원이다 — 시연을 몇 번 돌려도 마찬가지다.
"""

from dataclasses import dataclass

import psycopg

from adapters.db.chunk_search import PgChunkSearch
from adapters.db.permission_sql import 권한_WHERE
from core.ports import Embedder
from core.types import Principal
from demo.naive_search import naive_ids

MAX_DEMO_K = 20

# 권한 조건이 id 조회와 **같은 문장 안**에 있다. 조각을 모듈 상수에 따로
# 저장하지 않는다 — 사본이 생기면 원본이 바뀔 때 조용히 어긋난다
# (naive_search.py 와 같은 방식).
_조항코드_SQL = f"""
    SELECT c.id, cl.code
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    LEFT JOIN clauses cl ON cl.id = c.clause_id
    WHERE c.id = ANY(%(ids)s)
      AND {권한_WHERE("d")}
"""


@dataclass(frozen=True)
class 경로결과:
    count: int
    clause_codes: list[str]


def _조항코드(conn: psycopg.Connection, ids: list[int], principal: Principal) -> list[str]:
    """chunk id → 조항 코드. **본문은 읽지 않는다.**

    **`principal` 이 필수인 이유:** 조항 코드는 본문이 아니지만 그 문서가
    **존재한다**는 것을 확인해 준다. 권한 검사를 검색 쪽에만 두면 id 를 아는
    호출자가 이 경로로 권한 밖 조항 코드를 그대로 가져갈 수 있다 —
    adapters/db/chunk_search.py 의 load_hits 가 같은 이유로 principal 을
    받는다. 오늘은 두 호출부가 이미 권한 필터를 지난 id 만 주지만, 이 데모의
    가장 그럴듯한 다음 편집(사후 필터링 **전**의 상위 k 를 같이 보여주기)이
    그 전제를 깬다. 나중에 끼워 넣으면 빠뜨린 경로가 생긴다(spec 5.3).

    권한 밖 id 는 **조용히 빠진다.** 예외를 던지면 안 된다 — "그 id 는 접근
    불가" 라는 응답 자체가 존재 확인이 된다(load_hits 와 같은 계약). 그래서
    돌려주는 목록이 준 id 보다 짧을 수 있다.

    순서는 준 id 순서를 따른다 — 순위 채널을 보여주려면 순서가 의미를 갖는다.

    `조항 밖` 은 **clause_id 가 NULL 인 청크**만 가리킨다. `or` 폴백을 쓰면
    빈 문자열 code 와 아예 없는 id 까지 같은 라벨로 뭉개져, 권한 밖 id 가
    빠지는지 남는지를 화면에서 구별할 수 없게 된다.
    """
    if not ids:
        return []
    with conn.cursor() as cur:
        cur.execute(
            _조항코드_SQL,
            {"ids": ids, "clearance": principal.clearance, "dept": principal.department},
        )
        코드 = dict(cur.fetchall())
    return ["조항 밖" if 코드[i] is None else 코드[i] for i in ids if i in 코드]


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
                "prefiltered": 경로결과(len(사전), _조항코드(conn, 사전, p)),
                "naive": 경로결과(len(사후), _조항코드(conn, 사후, p)),
            }
        )
    return {"query": query, "k": k, "personas": 나온다}

"""**이 경로는 의도적으로 샌다. 프로덕션에서 호출되면 안 된다.**

교과서적인 순진한 RAG 다 — 전체 청크에서 상위 k개를 뽑고 **그다음에**
권한으로 거른다. 그러면 결과 개수가 주체의 권한 범위 크기를 그대로
드러내고, 그 개수 차이가 "여기 네가 못 보는 문서가 있다"는 신호가 된다.

이것을 저장소에 두는 이유는 시연이 말이 아니라 실행이어야 하기 때문이다
(보충 spec 결정 17). 프로덕션 경로에 닿지 않는다는 것은
tests/test_demo_isolation.py 가 집합 동일성으로 강제한다.

adapters/db/chunk_search.py 의 by_vector 와 나란히 놓고 읽으면 차이가
한 줄이다 — WHERE 가 ORDER BY 앞에 있는가 뒤에 있는가.
"""

import psycopg

from adapters.db.permission_sql import 권한_WHERE
from core.types import Principal

Vector = list[float]

# 권한 조건이 **바깥**에 있다. 안쪽 서브쿼리는 전체 청크에서 상위 k개를
# 뽑는다 — 그 k개가 전부 권한 밖이면 필터 뒤에 0건이 남는다.
_순진한_SQL = f"""
    SELECT t.id
    FROM (
        SELECT c.id, c.document_id
        FROM chunks c
        ORDER BY c.embedding <=> %(qvec)s
        LIMIT %(k)s
    ) t
    JOIN documents d ON d.id = t.document_id
    WHERE {권한_WHERE("d")}
"""


def naive_ids(conn: psycopg.Connection, vec: Vector, principal: Principal, k: int) -> list[int]:
    """사후 필터링으로 chunk id 를 뽑는다. **새는 경로다.**"""
    with conn.cursor() as cur:
        cur.execute(
            _순진한_SQL,
            {
                "qvec": str(vec),
                "k": k,
                "clearance": principal.clearance,
                "dept": principal.department,
            },
        )
        return [r[0] for r in cur.fetchall()]

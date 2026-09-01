"""권한 WHERE 조각 — 문서와 로그가 공유한다.

이 규칙은 이미 여러 곳에 산다: 이 SQL, core/access/visibility.py, 그리고
frontend/components/DocumentTable.tsx(표시용). 늘어난 이유는 각각 다른
일을 하기 때문이다 — SQL 은 사전 필터링, 파이썬은 재검증, TypeScript 는
화면 설명. 그러나 **같은 계층에서 두 벌이 되는 것**은 다르다. 로그가
자기 SQL 을 새로 쓰면 그건 이유 없는 사본이다.

별칭을 인자로 받는 이유: documents 와 hosts 가 같은 두 컬럼을 갖지만
쿼리 안에서 다른 이름으로 불린다.
"""


def 권한_WHERE(alias: str) -> str:
    """`alias` 테이블의 권한 컬럼에 대한 WHERE 조건.

    전사 공개는 두 가지로 저장될 수 있다: NULL 과 빈 배열. upsert 경로가
    빈 배열을 NULL 로 정규화하지만, 수동 SQL 같은 다른 경로를 대비해
    여기서도 받아준다 — 정규화를 믿지 않는다.
    """
    return f"""
    {alias}.required_clearance <= %(clearance)s
    AND (
        {alias}.allowed_departments IS NULL
        OR cardinality({alias}.allowed_departments) = 0
        OR %(dept)s = ANY({alias}.allowed_departments)
    )
"""

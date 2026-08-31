"""가시성 규칙 — 순수 함수.

adapters/db/chunk_search.py 의 _권한_WHERE 와 **같은 판정**을 내야 한다.
두 벌이 존재하는 이유: SQL 은 검색을 사전 필터링하고(존재를 감춘다),
이 함수는 이미 나온 결과를 재검증한다(spec 5.4). 재검증이 SQL 을 다시
부르면 그건 검증이 아니라 같은 코드를 두 번 믿는 것이다.

두 벌이 어긋나면 재검증이 무의미해지므로 tests/test_search_integration.py
가 실제 DB 로 둘을 대조한다.

Document 가 아니라 두 필드를 받는 이유: PolicyHit 도 Document 도 이 규칙을
쓰는데 둘은 다른 타입이다. 공통 조상을 만들면 한 번 쓰는 추상화가 된다.
"""

from core.types import Principal


def visible(required_clearance: int, allowed_departments: tuple[str, ...], p: Principal) -> bool:
    """이 주체에게 보이는가.

    허용부서가 비어 있으면 전사 공개다 — "아무도 못 본다"가 아니다.
    W1 실측: 빈 배열을 안 받아주면 그 문서는 자기 부서에도 안 보이고,
    에러가 아니라 조용한 누락이라 발견이 늦다.
    """
    return required_clearance <= p.clearance and (
        not allowed_departments or p.department in allowed_departments
    )

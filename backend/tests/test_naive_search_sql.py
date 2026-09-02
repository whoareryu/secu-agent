"""_순진한_SQL 문자열 자체를 검사한다. DB 가 필요 없다.

tests/test_search_sql.py 와 같은 이유로 존재한다: DB 기반 테스트는 이
규모(문서 9개·청크 338개)에서 Postgres 가 우연히 Nested Loop + Memoize
계획을 골라 순서를 그대로 보존해 버리면 바깥 ORDER BY 를 통째로 지워도
초록불이 나온다 — 실측(리뷰): 수정 전/후 SQL 을 각각 여덟 번 돌려도 둘 다
`[8, 17, 11, 19, 12, 13, 14, 15, 9, 3]` 로 완전히 같았다. 계획이 우연히
순서를 보존하는가와 무관하게 회귀를 잡으려면, 문장 자체에 그 보장이
쓰여 있는지를 봐야 한다.

`권한_WHERE` 를 직접 import 하지 않는다 — naive_search.py 는 (test_search_
sql.py 가 쓰는 chunk_search.py 와 달리) 렌더링된 조각을 모듈 상수로 저장해
두지 않으므로, 여기서 직접 import 하면 이 파일 자체가 권한_WHERE 의 여섯째
직접 importer 가 돼 화면의 "다섯입니다" 를 거짓으로 만든다
(test_how_screen_claims.py 가 그걸 잡는다 — 실제로 한 번 그렇게 됐다가
되돌렸다). 대신 리터럴 `WHERE` 키워드로 필터 절 위치를 찾는다 — 이
SQL 안에 WHERE 는 그 한 자리뿐이라 안쪽 서브쿼리와 섞일 일이 없다.
"""

from demo.naive_search import _순진한_SQL


def test_바깥_ORDER_BY가_있다():
    # 이 절이 없으면 안쪽 서브쿼리가 고른 거리 순서를 바깥 JOIN 이 그대로
    # 낸다는 보장이 없다 — Postgres 는 조인 출력 순서를 규정하지 않는다.
    assert "ORDER BY t.dist" in _순진한_SQL


def test_WHERE는_이_문장에_한_번뿐이다():
    """아래 위치 비교 테스트가 공허하게 통과하지 않기 위한 가드.

    안쪽 서브쿼리에 WHERE 가 생기면(지금은 없다) `.index("WHERE")` 가
    엉뚱한 자리를 찾아 다음 테스트가 의미 없이 통과한다.
    """
    assert _순진한_SQL.count("WHERE") == 1


def test_바깥_ORDER_BY가_권한_필터보다_뒤에_온다():
    # "필터 먼저, 그 결과를 다시 정렬은 나중"을 문장의 위치 관계로
    # 인코딩한다 — test_search_sql.py 의 test_권한_필터가_정렬보다_먼저_온다
    # 와 짝이다.
    필터_위치 = _순진한_SQL.index("WHERE")
    정렬_위치 = _순진한_SQL.index("ORDER BY t.dist")
    assert 필터_위치 < 정렬_위치

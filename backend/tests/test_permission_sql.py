"""권한 WHERE 조각.

문서와 로그가 같은 문자열을 쓴다. 두 벌이 되면 한쪽만 고쳐지고, 그
어긋남은 조용하다 — 결과가 줄어들 뿐 에러가 나지 않는다.
"""

from adapters.db.permission_sql import 권한_WHERE


def test_별칭이_전부_치환된다():
    조각 = 권한_WHERE("h")
    assert "d." not in 조각, "다른 별칭이 남았다"
    assert 조각.count("h.") == 4, (
        "required_clearance · allowed_departments IS NULL · "
        "cardinality(...) · = ANY(...) 네 자리 전부가 별칭을 달아야 한다"
    )


def test_권한_컬럼이_별칭_없이_등장하지_않는다():
    """별칭 없는 컬럼 참조는 두 테이블 조인에서 모호성 오류를 내거나,
    더 나쁘게는 엉뚱한 테이블의 컬럼으로 조용히 붙는다. 개수만 세는
    검사는 이것을 못 잡는다.
    """
    import re

    조각 = 권한_WHERE("h")
    for 컬럼 in ("required_clearance", "allowed_departments"):
        # 컬럼 이름 바로 앞이 "h." 가 아닌 등장을 찾는다
        for m in re.finditer(re.escape(컬럼), 조각):
            앞 = 조각[max(0, m.start() - 2) : m.start()]
            assert 앞 == "h.", f"{컬럼} 이 별칭 없이 등장한다 (앞: {앞!r})"


def test_세_가지_전사공개_표현을_모두_받는다():
    """NULL 과 빈 배열 둘 다 전사 공개다.

    빈 배열을 안 받아주면 그 문서는 자기 부서에도 안 보인다 — W1 실측.
    조용한 누락이라 발견이 늦다.
    """
    조각 = 권한_WHERE("d")
    assert "IS NULL" in 조각
    assert "cardinality" in 조각
    assert "= ANY(" in 조각


def test_파라미터_이름이_고정되어_있다():
    """호출부가 전부 이 두 이름으로 값을 넘긴다."""
    조각 = 권한_WHERE("x")
    assert "%(clearance)s" in 조각
    assert "%(dept)s" in 조각


def test_chunk_search_가_이_조각을_쓴다():
    """복사본이 남아 있으면 잡는다."""
    from adapters.db import chunk_search

    assert chunk_search._권한_WHERE == 권한_WHERE("d")

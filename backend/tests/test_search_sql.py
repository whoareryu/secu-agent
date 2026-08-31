"""_벡터_SQL / _권한_WHERE 문자열 자체를 검사한다. DB 가 필요 없다.

기본 스위트는 -m db 를 제외하므로, 권한 필터를 건드리는 회귀는 여기가
아니면 CI 에서 전혀 잡히지 않는다. tests/test_search_integration.py 의
EXPLAIN 기반 테스트(-m db)는 "실제로 이 계획대로 실행되는가"를 보고,
이 파일은 "그 문장 자체가 그렇게 쓰여 있는가"를 본다 — 서로 대체재가
아니라 보완재다.
"""

from adapters.db.chunk_search import _권한_WHERE, _벡터_SQL


def test_MATERIALIZED_힌트가_있다():
    # 이 열한 글자가 지워지면 플래너가 CTE 를 인라인해서 권한 필터가
    # 순위 뒤로 밀린다 — 사후 필터링이 되어 존재가 새어나간다(spec 5.3).
    assert "AS MATERIALIZED" in _벡터_SQL


def test_권한_필터가_정렬보다_먼저_온다():
    # "필터 먼저, 정렬 나중"을 문장의 위치 관계로 인코딩한다.
    필터_위치 = _벡터_SQL.index(_권한_WHERE)
    정렬_위치 = _벡터_SQL.index("ORDER BY")
    assert 필터_위치 < 정렬_위치


def test_권한_비교가_이하이다():
    # required_clearance <= 를 >= 로 뒤집으면 등급이 높을수록 문서가 보이는
    # 게 아니라 낮을수록 다 보이게 된다 — 실측: 기본 스위트는 그래도 초록불.
    assert "required_clearance <=" in _권한_WHERE
    assert "required_clearance >=" not in _권한_WHERE

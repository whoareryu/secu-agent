"""권한 조건을 담은 SQL 문장 자체를 검사한다. DB 가 필요 없다.

기본 스위트는 -m db 를 제외하므로, 권한 필터를 건드리는 회귀는 여기가
아니면 CI 에서 전혀 잡히지 않는다. tests/test_search_integration.py 의
EXPLAIN 기반 테스트(-m db)는 "실제로 이 계획대로 실행되는가"를 보고,
이 파일은 "그 문장 자체가 그렇게 쓰여 있는가"를 본다 — 서로 대체재가
아니라 보완재다.

**네 문장 전부를 보는 이유.** 한때 이 파일은 _벡터_SQL 하나만 봤고,
나머지 셋은 메서드 안의 인라인 f-string 이거나(chunk_search) 상수인데도
검사 대상이 아니었다(log_search). 실측한 결과:

    load_hits 의 `AND {_권한_WHERE}` → `AND TRUE`   → 274 passed
    by_keyword 의 `WHERE {_권한_WHERE}` → `WHERE TRUE` → 274 passed
    log_search 를 LIMIT 뒤 필터(=사후 필터링)로 변경   → 274 passed

세 가지 모두 이 프로젝트의 핵심 불변식을 깨는데 전부 초록불이었다.
문장을 상수로 올리고 여기서 고정한다.
"""

import pytest

from adapters.db.chunk_search import _권한_WHERE, _벡터_SQL, _키워드_SQL, _히트_SQL
from adapters.db.log_search import _조회_SQL
from adapters.db.permission_sql import 권한_WHERE

_로그_권한_WHERE = 권한_WHERE("h")

# (이름, 문장, 그 문장이 쓰는 권한 조각). 권한 조건을 담은 문장은 이것이
# 전부다 — 새 검색 경로가 생기면 여기에 올라와야 한다.
_권한을_담은_문장 = [
    ("chunk_search._벡터_SQL", _벡터_SQL, _권한_WHERE),
    ("chunk_search._키워드_SQL", _키워드_SQL, _권한_WHERE),
    ("chunk_search._히트_SQL", _히트_SQL, _권한_WHERE),
    ("log_search._조회_SQL", _조회_SQL, _로그_권한_WHERE),
]


@pytest.mark.parametrize(
    "이름,문장,조각", _권한을_담은_문장, ids=lambda v: v if isinstance(v, str) else ""
)
def test_권한_조건이_문장_안에_있다(이름: str, 문장: str, 조각: str):
    """조건을 통째로 지우거나 TRUE 로 바꾸는 변이를 잡는다."""
    assert 조각 in 문장, f"{이름} 에 권한 조건이 없다"


@pytest.mark.parametrize(
    "이름,문장,조각", _권한을_담은_문장, ids=lambda v: v if isinstance(v, str) else ""
)
def test_권한_조건이_순위와_상한보다_먼저_온다(이름: str, 문장: str, 조각: str):
    """사전 필터링을 문장의 **위치 관계**로 인코딩한다.

    권한 조건이 ORDER BY 나 LIMIT 뒤로 밀리면 그 순간 사후 필터링이고,
    결과 개수가 권한 범위의 크기를 그대로 드러낸다(spec 5.3).
    ORDER BY·LIMIT 가 없는 문장(_히트_SQL)은 이 검사가 공허하므로 건너뛴다.
    """
    필터_위치 = 문장.index(조각)
    for 표지 in ("ORDER BY", "LIMIT"):
        위치 = 문장.find(표지)
        if 위치 == -1:
            continue
        assert 필터_위치 < 위치, f"{이름} 의 권한 조건이 {표지} 뒤에 있다 — 사후 필터링이다"


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

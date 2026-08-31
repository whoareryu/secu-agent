"""마크다운 사내 규정 파서.

front matter 가 권한을 들고 있는 이유: 문서 8개를 CLI 인자 8벌로 적재하면
어느 문서가 어느 등급인지가 셸 히스토리에만 남는다. 문서가 자기 등급을
들고 있어야 재적재가 같은 결과를 낸다.
"""

import pytest

from adapters.parsing.markdown import parse_front_matter, split_clauses

문서 = """---
title: 임원 성과급 산정 기준
clearance: 3
departments: []
---

## 6.1.1 성과급 재원 산정

영업이익의 일정 비율을 재원으로 삼는다.

## 6.1.2 지급 시기

회계연도 종료 후 90일 이내에 지급한다.
"""


def test_front_matter_를_읽는다():
    meta, body = parse_front_matter(문서)
    assert meta["title"] == "임원 성과급 산정 기준"
    assert meta["clearance"] == 3
    assert meta["departments"] == []


def test_front_matter_는_본문에_남지_않는다():
    # 남으면 "clearance: 3" 이 청크로 적재되어 검색된다.
    _, body = parse_front_matter(문서)
    assert "clearance" not in body
    assert body.lstrip().startswith("## 6.1.1")


def test_front_matter_가_없으면_예외를_던진다():
    # 조용히 기본값을 쓰면 등급 3 문서가 등급 1 로 적재된다 —
    # 누출이고, 발견이 아주 늦다.
    with pytest.raises(ValueError):
        parse_front_matter("## 6.1.1 제목\n본문")


def test_조항_코드와_제목을_나눈다():
    _, body = parse_front_matter(문서)
    clauses = split_clauses(body)
    assert [c.code for c in clauses] == ["6.1.1", "6.1.2"]
    assert clauses[0].title == "성과급 재원 산정"


def test_조항_본문이_다음_조항까지만이다():
    _, body = parse_front_matter(문서)
    clauses = split_clauses(body)
    assert "영업이익" in clauses[0].text
    assert "회계연도" not in clauses[0].text


def test_세_자리_조항만_받는다():
    # ISMS-P 파서와 같은 규칙이다. "## 개요" 같은 제목은 조항이 아니다.
    clauses = split_clauses("## 개요\n머리말\n\n## 6.1.1 진짜 조항\n본문")
    assert [c.code for c in clauses] == ["6.1.1"]
    assert "머리말" not in clauses[0].text

"""가시성 규칙 — spec 3.1 의 두 줄.

이 규칙이 단순한 이유가 있다. SQL WHERE 로 그대로 번역되어야 사전
필터링이 된다. 복잡해지면 애플리케이션 레이어로 밀려나고, 그 순간
사후 필터링이 되어 존재가 누출된다.
"""

from core.access.visibility import visible
from core.types import Principal

사원 = Principal(department="개발팀", clearance=1)
팀장 = Principal(department="인사팀", clearance=2)
임원 = Principal(department="경영지원팀", clearance=3)


def test_등급이_충분하면_보인다():
    assert visible(1, (), 사원)


def test_등급이_모자라면_안_보인다():
    assert not visible(3, (), 사원)


def test_등급이_같으면_보인다():
    # 비교가 <= 여야 한다. < 로 쓰면 등급 3 임원이 등급 3 문서를 못 본다.
    assert visible(3, (), 임원)


def test_허용부서가_비면_전사_공개다():
    # 빈 튜플을 "아무도 못 본다"로 읽으면 그 문서는 조용히 사라진다.
    assert visible(1, (), 사원)
    assert visible(1, (), 팀장)


def test_허용부서에_들면_보인다():
    assert visible(1, ("개발팀",), 사원)


def test_허용부서에_없으면_등급이_높아도_안_보인다():
    # 두 조건은 AND 다. 등급이 부서를 덮어쓰면 임원이 모든 부서 문서를 본다.
    assert not visible(1, ("개발팀",), 임원)


def test_두_조건_중_하나만_모자라도_안_보인다():
    assert not visible(2, ("개발팀",), 사원)  # 등급도 부서도 모자람
    assert not visible(3, ("인사팀",), 팀장)  # 부서는 맞고 등급이 모자람

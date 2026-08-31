"""도구 출력 재검증.

정상 경로에서는 절대 발동하지 않는다 — 발동했다는 것은 사전 필터링이
깨졌다는 뜻이다. 그래서 조용히 걸러내지 않고 터진다(spec 5.4).
"""

import pytest

from core.agent.policy import AccessViolation, enforce
from core.types import PolicyHit, Principal

사원 = Principal(department="개발팀", clearance=1)

문서제목 = "임원전용지침"


def _hit(chunk_id=1, clearance=1, depts=(), text="본문"):
    return PolicyHit(
        chunk_id=chunk_id,
        text=text,
        doc_title=문서제목,
        clause_code="2.6.1",
        required_clearance=clearance,
        allowed_departments=depts,
    )


def test_전부_권한_안이면_그대로_돌려준다():
    hits = [_hit(1), _hit(2)]
    assert enforce(hits, 사원) == hits


def test_빈_결과는_그대로_통과한다():
    # 볼 수 있는 문서가 없는 것과 규칙이 깨진 것은 다르다.
    assert enforce([], 사원) == []


def test_등급이_높은_항목이_섞이면_예외가_난다():
    with pytest.raises(AccessViolation):
        enforce([_hit(1), _hit(2, clearance=3)], 사원)


def test_타부서_항목이_섞이면_예외가_난다():
    with pytest.raises(AccessViolation):
        enforce([_hit(1, depts=("인사팀",))], 사원)


def test_조용히_걸러내지_않는다():
    """걸러내면 사후 필터링이 되고, 버그가 결과 개수 뒤에 숨는다."""
    with pytest.raises(AccessViolation):
        enforce([_hit(1), _hit(2, clearance=3)], 사원)


def test_예외_메시지가_본문도_문서_제목도_담지_않는다():
    """메시지는 로그와 에러 응답을 타고 나간다.

    권한 밖 문서의 본문이나 제목을 담으면 이 예외 자체가 내용 누출 경로가
    된다 — 막으려고 만든 장치가 통로가 된다.
    """
    비밀 = "임원 성과급은 영업이익의 100분의 3을 상한으로 한다"
    with pytest.raises(AccessViolation) as e:
        enforce([_hit(7, clearance=3, text=비밀)], 사원)
    메시지 = str(e.value)
    assert 비밀 not in 메시지
    assert 문서제목 not in 메시지
    assert "7" in 메시지  # chunk_id 는 있어야 추적이 된다

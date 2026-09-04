"""데모 비교의 질의는 서버가 고른다 — 그 계약을 고정한다. DB 가 필요 없다.

**왜 이 파일이 있는가.** `/demo/compare` 는 세 계정의 결과를 한 응답에 담고,
거기에는 각 계정이 볼 수 있는 **조항 코드**가 들어 있다. 그것이 화면의
요점이지만, 질의를 호출자가 정할 수 있으면 그 순간 존재 오라클이 된다 —
로그인한 누구나 임의의 주제를 물어 "등급 3 계정에게는 이 주제로 어떤 조항이
잡히는가" 를 열거할 수 있다.

실측(2026-09-04, 자유 입력이 살아 있던 시점):

    POST /demo/compare {"query": "임원 성과급 재원은 영업이익의 몇 퍼센트인가", "k": 3}
      김개발(등급1) naive: 0건 []
      최임원(등급3) naive: 3건 ["6.1.1", "6.1.2", "6.1.3"]

등급 1 계정의 브라우저가 6.1.x 의 존재를 확인했다. 로그인은 이 프로젝트가
스스로 정의했듯 권한이 아니라 요금 게이트라 그 앞을 막지 못한다.

`tests/test_demo_isolation.py` 는 "`/ask` 가 demo 를 import 하지 않는다" 를
본다 — 그 테스트는 초록불인 채로 이 누출이 살아 있었다. 울타리의 종류가
다르다: 저쪽은 코드 도달성, 이쪽은 입력 계약이다.
"""

import re
from pathlib import Path

import pytest

from api.schemas import CompareRequest
from demo.compare import 시연_질의

_화면 = Path("../frontend/components/LeakCompare.tsx")


def test_요청에_자유_질의_필드가_없다():
    """`query: str` 이 되살아나면 오라클도 함께 돌아온다.

    api/schemas.py 가 AskRequest 에 department·clearance 를 두지 않는 것과
    같은 종류의 계약이다 — 클라이언트가 정할 수 있는 값이 곧 공격면이다.
    """
    필드 = set(CompareRequest.model_fields)
    assert "query" not in 필드, "자유 질의 필드가 되살아났다 — 존재 오라클이 다시 열린다"
    assert 필드 == {"demo_index", "k"}


def test_시연_질의가_비어_있지_않다():
    """0개면 아래 대조 테스트가 공허하게 통과한다."""
    assert len(시연_질의) >= 2
    assert all(q.strip() for q in 시연_질의)


def test_화면_칩_목록이_서버_목록과_순서까지_같다():
    """인덱스로 주고받으므로 순서가 어긋나면 라벨과 결과가 조용히 엇갈린다.

    집합이 아니라 **리스트**로 비교하는 이유가 그것이다. 화면은 0번을 눌렀다고
    믿는데 서버는 2번을 계산하는 상태가 아무 에러 없이 성립한다.
    """
    assert _화면.exists(), f"{_화면} 가 없다 — 이 테스트가 공허해진다"
    본문 = _화면.read_text(encoding="utf-8")

    블록 = re.search(r"const 시연_질의 = \[(.*?)\];", 본문, re.DOTALL)
    assert 블록, "LeakCompare.tsx 에서 시연_질의 배열을 찾지 못했다"
    화면_목록 = re.findall(r'"([^"]+)"', 블록.group(1))

    assert 화면_목록 == list(시연_질의)


def test_화면에_자유_입력창이_없다():
    """입력창이 되살아나면 서버가 인덱스만 받아도 화면이 그것을 요구하게 된다.

    문자열 검사라 거칠지만, 이 파일이 막으려는 편집(`<input>` 을 되돌리는 것)은
    정확히 이 모양으로 나타난다.
    """
    본문 = _화면.read_text(encoding="utf-8")
    assert "<input" not in 본문, "LeakCompare 에 입력창이 생겼다 — 자유 질의 경로인지 확인하라"


@pytest.mark.parametrize("색인", [0, len(시연_질의) - 1])
def test_유효한_색인은_질의로_풀린다(색인: int):
    assert isinstance(시연_질의[색인], str)

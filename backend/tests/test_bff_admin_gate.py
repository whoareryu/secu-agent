"""BFF 라우트 핸들러의 문지기를 고정한다. DB 도 Node 도 필요 없다.

**여기가 유일한 강제 지점이다.** 백엔드는 공유 시크릿만 본다 — 시크릿을 든
요청이면 `/access-log` 든 `/log-events` 든 그대로 답한다(관리자라는 개념이
백엔드에 없다). 그래서 "관리자만 열람 이력을 본다" 를 실제로 지키는 것은
`frontend/app/api/*/route.ts` 안의 `roleFor(...) !== "admin"` 두 줄뿐이다.
그 두 줄이 사라지면 로그인한 아무나 콘솔에서 `fetch('/api/access-log')` 로
전사 열람 이력을 받는다. 라우트 파일 자신이 주석에 그 위험을 정확히 적어
두었는데, 그 인식을 붙잡아 두는 테스트는 없었다.

`npm test` 는 `lib/*.test.ts` 만 본다 — 라우트 핸들러는 그 글롭 밖이다.
여기서 잡는다. 실행이 아니라 **모양**을 보는 검사라, "403 을 실제로
돌려준다" 가 아니라 "검사가 백엔드 호출보다 먼저 있다" 를 고정한다.
tests/test_search_sql.py 가 권한 조건과 ORDER BY 의 위치 관계로 사전
필터링을 인코딩하는 것과 같은 방식이다.
"""

import re
from pathlib import Path

import pytest

_저장소 = Path(__file__).resolve().parents[2]
_라우트 = _저장소 / "frontend" / "app" / "api"

# 이 문자열을 담은 파일은 백엔드로 나가는 통로다.
_시크릿 = "BACKEND_SHARED_SECRET"

# 화면 문장이 아니라 코드를 보므로 주석도 그대로 센다 — 여기서 찾는 것은
# 한국어 문장이 아니라 호출이고, 주석에 `roleFor(` 를 적어 통과시키는 편집은
# 아래 위치 검사(fetch 보다 앞)를 함께 만족시켜야 해서 우연히 나오지 않는다.
_관리자_검사 = re.compile(r'roleFor\([^)]*\)\s*!==\s*"admin"')
_백엔드_호출 = re.compile(r"fetch\(\s*`\$\{process\.env\.BACKEND_URL\}")

# 관리자 데이터를 중계하는 라우트. **집합 동일성**으로 고정한다 —
# 부분집합으로 두면 관리자 데이터를 새로 중계하는 라우트가 문지기 없이
# 생겨도 조용히 통과한다.
관리자_라우트 = {
    "access-log/route.ts",
    "log-events/route.ts",
}


def _라우트_파일들() -> list[Path]:
    return sorted(_라우트.rglob("route.ts"))


def _이름(p: Path) -> str:
    return str(p.relative_to(_라우트))


def test_검사할_라우트가_있다():
    """0개면 아래 테스트들이 공허하게 통과한다."""
    assert len(_라우트_파일들()) >= 5, "라우트 핸들러를 찾지 못했다"


@pytest.mark.parametrize("파일", _라우트_파일들(), ids=_이름)
def test_백엔드로_나가는_라우트는_먼저_세션을_본다(파일: Path):
    """시크릿을 든 통로에 무인증 경로를 만들지 않는다.

    이 시크릿을 들고 백엔드를 부를 수 있으면 그 뒤에는 LLM 과 전사 데이터가
    있다. 로그인은 권한이 아니라 요금 게이트지만, 그 게이트조차 없는 통로는
    만들지 않는다.
    """
    본문 = 파일.read_text(encoding="utf-8")
    if _시크릿 not in 본문:
        pytest.skip("백엔드로 나가지 않는 라우트")
    assert "await auth()" in 본문, f"{_이름(파일)} 가 세션을 보지 않고 백엔드를 부른다"


def test_관리자_문지기를_가진_라우트_목록이_그대로다():
    """집합 동일성. 늘어도 줄어도 실패한다.

    줄면 문지기가 사라진 것이고, 늘면 관리자 데이터를 중계하는 통로가
    새로 생긴 것이다 — 둘 다 리뷰에 끌어올려야 할 변경이다.
    """
    실제 = {_이름(p) for p in _라우트_파일들() if _관리자_검사.search(p.read_text(encoding="utf-8"))}
    assert 실제 == 관리자_라우트


@pytest.mark.parametrize("이름", sorted(관리자_라우트))
def test_관리자_검사가_백엔드_호출보다_먼저다(이름: str):
    """뒤로 밀리면 이미 가져온 데이터를 버리는 것일 뿐이다.

    응답을 안 돌려줘도 백엔드는 이미 불렸고, 그 사이에 얼마든지 다른 실수가
    끼어들 수 있다. 순서를 코드의 위치 관계로 못 박는다.
    """
    본문 = (_라우트 / 이름).read_text(encoding="utf-8")
    검사 = _관리자_검사.search(본문)
    호출 = _백엔드_호출.search(본문)
    assert 검사 is not None, f"{이름} 에 관리자 검사가 없다"
    assert 호출 is not None, f"{이름} 에서 백엔드 호출을 찾지 못했다"
    assert 검사.start() < 호출.start(), f"{이름} 의 관리자 검사가 백엔드 호출보다 뒤에 있다"


def test_ask_의_요금_상한이_본문_파싱_뒤_백엔드_호출_앞이다():
    """라우트 주석이 적어둔 순서를 그대로 고정한다.

        "본문을 파싱한 뒤, 백엔드를 부르기 전에 상한을 검사한다. 순서가 둘 다
         중요하다 — 파싱보다 앞이면 형식이 깨진 요청도 하루 할당량을 한 번 쓰고,
         백엔드 호출보다 뒤면 이미 부른 요금을 못 막는다."

    lib/rate-limit.test.ts 는 check() 자체만 검증한다. 리팩터링으로 세 줄이
    뒤바뀌면 요금 방어가 조용히 사라지고, 실패가 청구서에서만 보인다.
    """
    본문 = (_라우트 / "ask" / "route.ts").read_text(encoding="utf-8")
    파싱 = 본문.index("await req.json()")
    상한 = 본문.index("check(")
    호출 = _백엔드_호출.search(본문)
    assert 호출 is not None, "ask 라우트에서 백엔드 호출을 찾지 못했다"
    assert 파싱 < 상한 < 호출.start(), (
        "ask 라우트의 순서가 어긋났다 — 파싱 → 요금 상한 → 백엔드 호출 이어야 한다."
    )

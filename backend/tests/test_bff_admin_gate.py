"""BFF 라우트 핸들러의 문지기를 고정한다. DB 도 Node 도 필요 없다.

**전제가 W7 에서 바뀌었다.** 예전에는 `/access-log` 와 `/log-events` 가
`roleFor(email) !== "admin"` 으로 막았고 그것이 유일한 강제 지점이었다.
지금은 관리자 **면**이 페르소나 역할로 막히고(lib/surface.ts 의 guard),
라우트는 방문자 세션 id 를 상류로 나른다. 라우트에서 확인할 것은 둘이다:

- 백엔드로 나가는 통로에 세션 검사가 필요한 곳(/ask)에는 그것이 있다
- /ask 의 요금 상한이 본문 파싱 뒤·백엔드 호출 앞이다
"""

import re
from pathlib import Path

_저장소 = Path(__file__).resolve().parents[2]
_라우트 = _저장소 / "frontend" / "app" / "api"

# 이 문자열을 담은 파일은 백엔드로 나가는 통로다.
_시크릿 = "BACKEND_SHARED_SECRET"

_백엔드_호출 = re.compile(r"fetch\(\s*`\$\{process\.env\.BACKEND_URL\}")

# 세션 검사를 가진 라우트를 찾는 정규식. 주석에 적어도 이 검사를 잡지만,
# 그런 편집은 아래 순서 검사(백엔드 호출보다 앞)를 우연히 만족시키지 않는다.
_세션_검사 = re.compile(r"await auth\(\)")

# 세션 검사를 가진 라우트 파일의 집합. **집합 동일성**으로 고정한다 — W7
# 이전에는 관리자_라우트(roleFor 두 곳)의 집합 동일성이 이 역할을 했다.
# roleFor 가 사라지면서 그 그물도 함께 사라졌으므로, 같은 모양의 net 을
# 새 전제로 다시 세운다: /ask 에서 세션 검사가 사라지면 유료 LLM 경로가
# 로그인 없이 열리고, 다른 라우트에 세션 검사가 새로 생기면 W7 이 로그인
# 벽을 걷어서 연 화면(/documents, /principals, /how 등)이 조용히 다시
# 잠긴다 — 둘 다 이 집합이 깨져야 리뷰에 끌어올려진다.
세션_검사_라우트 = {"ask/route.ts"}


def _라우트_파일들() -> list[Path]:
    return sorted(_라우트.rglob("route.ts"))


def _이름(p: Path) -> str:
    return str(p.relative_to(_라우트))


def test_검사할_라우트가_있다():
    """0개면 아래 테스트들이 공허하게 통과한다."""
    assert len(_라우트_파일들()) >= 5, "라우트 핸들러를 찾지 못했다"


def test_ask_는_세션_없이_백엔드를_부르지_않는다():
    """/ask 뒤에는 LLM 이 있다. 로그인은 권한이 아니라 요금 게이트이고,
    W7 이 다른 면의 로그인을 걷은 뒤로 이 라우트가 그 게이트의 유일한 자리다.
    """
    본문 = (_라우트 / "ask" / "route.ts").read_text(encoding="utf-8")
    세션 = 본문.index("await auth()")
    호출 = _백엔드_호출.search(본문)
    assert 호출 is not None
    assert 세션 < 호출.start(), "세션 검사가 백엔드 호출보다 뒤에 있다"


def test_세션_검사를_가진_라우트_집합이_ask_뿐이다():
    """집합 동일성. 늘어도 줄어도 실패한다.

    줄면(ask 에서 사라지면) 로그인 없이 유료 LLM 경로가 열린 것이고, 늘면
    (다른 라우트에 새로 생기면) W7 이 로그인 벽을 걷어서 연 화면이 그
    라우트에서만 조용히 다시 잠긴 것이다 — 둘 다 리뷰에 끌어올려야 할
    변경이다.
    """
    실제 = {_이름(p) for p in _라우트_파일들() if _세션_검사.search(p.read_text(encoding="utf-8"))}
    assert 실제 == 세션_검사_라우트


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

"""역할은 서버가 정한다 — 프론트에 이름→역할 맵이 없다.

W6 §2.2 가 못박은 불변식을 역할로 확장한 것이다:

    쿠키에 담기는 것은 **이름뿐**이고 등급·부서는 백엔드가 principals
    테이블에서 번역한다.

프론트에 `{ 남감사: "auditor" }` 같은 상수를 두면 권한 판정의 네 번째
사본이 되고, `(explain)/documents` 화면이 *"이 화면의 계산은 표시용이고
실제 강제는 서버의 SQL"* 이라고 경고한 그 함정을 새로 파는 일이다.

이 스펙(§2.1)이 지켜지는지를 코드로 보는 유일한 그물이다.
"""

from pathlib import Path

_저장소 = Path(__file__).resolve().parents[2]
_프론트 = _저장소 / "frontend"
_역할 = ("auditor", "developer")


def _소스들() -> list[Path]:
    나온다: list[Path] = []
    for 뿌리 in ("app", "components", "lib"):
        d = _프론트 / 뿌리
        나온다 += sorted(d.rglob("*.tsx")) + sorted(d.rglob("*.ts"))
    return [p for p in 나온다 if not p.name.endswith(".test.ts")]


def test_검사할_파일이_있다():
    """0개면 아래 테스트가 공허하게 통과한다."""
    assert len(_소스들()) > 20


def test_페르소나_이름과_역할이_같은_줄에_없다():
    """맵을 만들면 `"남감사": "auditor"` 처럼 한 줄에 붙는다.

    문자열 검사라 거칠지만, 이 파일이 막으려는 편집은 정확히 이 모양으로
    나타난다. 우회하려면 일부러 갈라 써야 하고, 그건 리뷰에서 눈에 띈다.
    """
    이름 = [
        "김개발",
        "정개발",
        "서인사",
        "박인사",
        "이보안",
        "한보안",
        "오보안",
        "윤총무",
        "남감사",
        "최임원",
    ]
    걸린_것 = []
    for p in _소스들():
        for i, 줄 in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if any(n in 줄 for n in 이름) and any(r in 줄 for r in _역할):
                걸린_것.append(f"{p.relative_to(_저장소)}:{i}")
    assert 걸린_것 == [], (
        f"프론트가 페르소나 이름을 역할에 잇고 있다: {걸린_것}. "
        "역할은 GET /principals 응답에서만 온다(스펙 §2.1)."
    )


def test_역할_문자열이_surface_에만_산다():
    """`auditor` 를 여러 파일이 리터럴로 쓰면 오타 하나가 조용히 게이트를 연다."""
    쓰는_파일 = {
        str(p.relative_to(_프론트))
        for p in _소스들()
        if any(r in p.read_text(encoding="utf-8") for r in _역할)
    }
    assert 쓰는_파일 == {"lib/surface.ts"}, (
        f"역할 리터럴을 쓰는 파일이 늘었다: {sorted(쓰는_파일)}. 판정은 guard() 한 곳에서만 한다."
    )

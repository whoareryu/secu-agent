"""저장소가 개인 메일 주소를 평문으로 싣지 않는다.

이 저장소는 public 이고 `jekyll/` 은 GitHub Pages 로 배포된다. 소스에 평문
주소가 있으면 정규식 한 줄로 긁힌다 — 실제로 `_config.yml` 의 `email:` 이
`index.html` 두 자리와 `_layouts/base.html` 한 자리에서 `mailto:` 링크로
렌더돼, 라이브 HTML 에 그대로 있었다.

**연락처를 없애자는 것이 아니다.** 포트폴리오에 연락 수단은 있어야 한다.
`_includes/email.html` 이 주소를 사용자·도메인으로 나눠 담고 표시할 때
조립한다 — 사람에게는 그대로 보이고, 소스에는 `@` 로 이어진 문자열이 없다.

**이 검사는 완벽하지 않다.** JS 를 실행하는 스크래퍼는 여전히 긁고, 커밋
author 이메일(과거 184개)은 이 검사의 범위 밖이다. 막는 것은 "정규식 한
줄로 긁히는 평문" 하나이고, 그것이 가장 싸게 막을 수 있는 것이다.

**테스트에 실제 주소를 적지 않는다.** 적으면 그것이 또 노출이다. 실주소가
쓰이는 도메인의 **패턴**으로 검사하고, 합성 도메인은 허용 목록으로 뺀다.
"""

import re
import subprocess
from pathlib import Path

_저장소 = Path(__file__).resolve().parents[2]

# 사람이 실제로 쓰는 메일 서비스. 저장소 안에서 이 도메인의 주소가 평문으로
# 나오면 그건 누군가의 진짜 주소다.
_실주소_도메인 = (
    "gmail",
    "naver",
    "daum",
    "hanmail",
    "kakao",
    "outlook",
    "hotmail",
    "yahoo",
    "icloud",
    "proton",
)
_평문_주소 = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]*(?:" + "|".join(_실주소_도메인) + r")\.[A-Za-z]{2,}",
    re.IGNORECASE,
)

# **추적 파일만 본다.** 관심사는 "커밋돼 배포되는 것" 이지 작업 디렉터리에
# 무엇이 있는가가 아니다. 실제로 첫 판은 저장소를 통째로 훑어
# `frontend/.env.local`(gitignore, 관리자 알리스트라 실주소가 들어 있는 것이
# 정상)과 `.jekyll-cache/` 빌드 산출물까지 걸었다 — 고칠 수 없는 것을
# 실패로 부르는 검사는 곧 꺼진다.
_건너뛸_확장자 = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".lock",
    ".tsbuildinfo",
}
_건너뛸_파일 = {"package-lock.json", "Gemfile.lock", "uv.lock"}


def _검사할_파일들() -> list[Path]:
    나온다 = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=_저장소,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.split("\0")
    return [
        _저장소 / 이름
        for 이름 in 나온다
        if 이름
        and Path(이름).suffix.lower() not in _건너뛸_확장자
        and Path(이름).name not in _건너뛸_파일
        and (_저장소 / 이름).is_file()
    ]


def test_검사할_파일이_있다():
    """0개면 아래 테스트가 공허하게 통과한다."""
    파일들 = _검사할_파일들()
    assert len(파일들) > 100, f"검사 대상이 너무 적다: {len(파일들)}개"
    # 실제로 사이트 소스를 보고 있는지 확인한다 — 걸러내기가 과해서
    # jekyll 을 통째로 건너뛰면 이 파일이 아무것도 지키지 않는다.
    이름들 = {str(p.relative_to(_저장소)) for p in 파일들}
    assert "jekyll/_config.yml" in 이름들
    assert "jekyll/index.html" in 이름들
    assert "jekyll/_layouts/base.html" in 이름들


def test_평문_개인_메일_주소가_없다():
    """실주소 도메인의 주소가 평문으로 있으면 실패한다.

    합성 주소(example.com · x.com · users.noreply.github.com)는 패턴에
    걸리지 않는다 — 도메인 목록에 없기 때문이다. 테스트 픽스처가 쓰는
    가짜 주소까지 막으면 이 검사가 방해만 된다.
    """
    걸린_것: list[str] = []
    for p in _검사할_파일들():
        try:
            본문 = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # 텍스트가 아니다
        for m in _평문_주소.finditer(본문):
            줄 = 본문[: m.start()].count("\n") + 1
            # 주소 자체는 메시지에 싣지 않는다 — 실패 출력이 또 하나의
            # 노출 경로가 되면 안 된다. 도메인까지만 남긴다.
            도메인 = m.group(0).split("@", 1)[1]
            걸린_것.append(f"{p.relative_to(_저장소)}:{줄} (@{도메인})")

    assert 걸린_것 == [], (
        "개인 메일 주소가 평문으로 있다 — 이 저장소는 public 이고 jekyll/ 은 "
        f"배포된다: {걸린_것}. jekyll/_includes/email.html 처럼 조립해서 쓴다."
    )

"""/how 화면이 인쇄한 전수 주장을 고정한다.

`frontend/app/(app)/how/page.tsx` 는 "이 목록이 전부다" 라는 문장을 싣고
있다 — 권한 SQL 조각을 import 하는 파일 목록, `visible()` 을 부르는 비테스트
호출부 목록. 그런 문장은 코드가 늘어나는 순간 조용히 거짓이 된다. 화면은
자기가 세는 대상이 늘어난 것을 알 방법이 없다.

이 브랜치가 그 문제에 맞는 도구를 이미 만들었다: 목록이 바뀌면 큰 소리로
실패해서 그 변경을 리뷰에 끌어올리는 집합 동일성 테스트
(tests/test_demo_isolation.py). demo importer 에만 쓰고 있던 그 도구를
여기서 화면의 전수 주장에도 건다.

**이 파일이 실패하면 코드와 화면 문장을 같이 고친다.** 목록만 고치고 화면을
그대로 두면 화면이 거짓말한다 — 그것이 이 파일이 존재하는 이유다.

행 번호까지 고정하는 항목이 있다. 화면이 `chunk_search.py` 40행,
`log_search.py`:34 처럼 **행 번호를 인쇄하기 때문**이다. 실제로 이 리뷰
라운드에서 `naive_search.py` 의 독스트링 한 줄이 늘어나며 화면의 `:33` 이
`:34` 로 밀렸다 — 아무 테스트도 그것을 잡지 못했다.
"""

import ast
from pathlib import Path

화면 = "frontend/app/(app)/how/page.tsx"

# 테스트를 포함한 전 계층. .venv 를 피하려고 디렉터리를 명시한다.
_전체 = ("core", "adapters", "api", "pipeline", "eval", "demo", "tests")
_비테스트 = ("core", "adapters", "api", "pipeline", "eval", "demo")

# 화면 문장: "이를 직접 import 하는 파일은 다섯입니다 — …"
권한_조각을_import_하는_파일 = {
    "adapters/db/chunk_search.py",
    "adapters/db/log_search.py",
    "demo/naive_search.py",
    "demo/compare.py",
    "tests/test_permission_sql.py",
}

# 화면 문장: "사본을 따로 두는 것은 chunk_search.py 뿐입니다 — 40행이 …
# log_search.py:34 · naive_search.py:34 · compare.py:28 은 …"
권한_조각_호출_위치 = {
    ("adapters/db/chunk_search.py", 40),
    ("adapters/db/log_search.py", 34),
    ("demo/naive_search.py", 34),
    ("demo/compare.py", 28),
}

# 화면 문장: "visible() 을 부르는 비테스트 호출부는 core/agent/policy.py 안에
# 둘입니다 — 62행이 청크 히트 재검증, 98행이 로그 이벤트 재검증입니다."
visible_호출_위치 = {("core/agent/policy.py", 62), ("core/agent/policy.py", 98)}


def _파일들(*디렉터리: str) -> list[Path]:
    나온다: list[Path] = []
    for d in 디렉터리:
        나온다 += sorted(Path(d).rglob("*.py"))
    return 나온다


def _트리(py: Path) -> ast.AST:
    return ast.parse(py.read_text(encoding="utf-8"))


def _호출_행(py: Path, 이름: str) -> set[int]:
    """`py` 안에서 `이름(...)` 을 부르는 행 번호들.

    문자열 검색이 아니라 AST 를 쓴다 — 주석과 독스트링에 함수 이름을 적어둔
    파일이 여럿이라(core/types.py 등) 문자열로 세면 호출부가 아닌 것을 센다.
    """
    return {
        n.func.lineno
        for n in ast.walk(_트리(py))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 이름
    }


def test_검사할_파일이_있다():
    """0개면 아래 테스트들이 공허하게 통과한다."""
    assert _파일들(*_전체)
    assert _파일들(*_비테스트)


def test_권한_조각을_import_하는_파일_목록이_그대로다():
    """화면이 인쇄한 grep 의 결과를 집합 동일성으로 고정한다.

    다섯째 importer 가 생기면 화면의 "다섯입니다" 가 조용히 거짓이 된다.
    """
    실제 = set()
    for py in _파일들(*_전체):
        for node in ast.walk(_트리(py)):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "adapters.db.permission_sql"
                and any(a.name == "권한_WHERE" for a in node.names)
            ):
                실제.add(str(py))
    assert 실제 == 권한_조각을_import_하는_파일, (
        f"권한_WHERE 를 import 하는 파일이 바뀌었다.\n"
        f"기대: {sorted(권한_조각을_import_하는_파일)}\n실제: {sorted(실제)}\n"
        f"이 목록은 {화면} 의 패널 ④ 에 개수와 함께 인쇄돼 있다 — "
        "여기 목록만 고치면 화면이 거짓말한다. 화면 문장도 같이 고친다."
    )


def test_권한_조각_호출_위치가_그대로다():
    """화면이 파일:행으로 인쇄한 자리를 고정한다.

    화면의 주장은 "사본을 저장하는 것은 chunk_search.py 하나" 다. 호출이
    늘거나 줄면 그 주장이 흔들리고, 행이 밀리면 인쇄된 번호가 거짓이 된다.
    """
    실제 = {(str(py), 행) for py in _파일들(*_비테스트) for 행 in _호출_행(py, "권한_WHERE")}
    assert 실제 == 권한_조각_호출_위치, (
        f"권한_WHERE 호출 위치가 바뀌었다.\n"
        f"기대: {sorted(권한_조각_호출_위치)}\n실제: {sorted(실제)}\n"
        f"{화면} 의 패널 ④ 가 이 파일:행 을 그대로 인쇄한다 — 화면 문장도 같이 고친다."
    )


def test_visible_비테스트_호출부가_그대로다():
    """화면 문장: "visible() 을 부르는 비테스트 호출부는 … 둘입니다."

    세 번째 호출부가 생기면 그 문장이 거짓이 되고, 더 중요하게는 문서와
    로그가 **같은 판정 함수 하나**를 공유한다는 이 패널의 주장이 다시
    검토돼야 한다.
    """
    실제 = {(str(py), 행) for py in _파일들(*_비테스트) for 행 in _호출_행(py, "visible")}
    assert 실제 == visible_호출_위치, (
        f"visible() 의 비테스트 호출부가 바뀌었다.\n"
        f"기대: {sorted(visible_호출_위치)}\n실제: {sorted(실제)}\n"
        f"{화면} 의 패널 ④ 가 이 개수와 행 번호를 인쇄한다 — 화면 문장도 같이 고친다."
    )

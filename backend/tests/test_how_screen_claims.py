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
# log_search.py:34 · naive_search.py:40 · compare.py:28 은 …"
권한_조각_호출_위치 = {
    ("adapters/db/chunk_search.py", 40),
    ("adapters/db/log_search.py", 34),
    ("demo/naive_search.py", 40),
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

    맨 이름 호출(`권한_WHERE(...)`)뿐 아니라 `모듈.이름(...)` 형태의 속성
    호출(`permission_sql.권한_WHERE(...)`, `visibility.visible(...)`)도 잡는다
    — test_demo_isolation.py 의 I1 과 같은 유형의 구멍이었다: 이름만 보면
    직접 부르는데도 조용히 안 잡힌다.
    """
    행: set[int] = set()
    for n in ast.walk(_트리(py)):
        if not isinstance(n, ast.Call):
            continue
        func = n.func
        if isinstance(func, ast.Name) and func.id == 이름:
            행.add(func.lineno)
        elif isinstance(func, ast.Attribute) and func.attr == 이름:
            행.add(func.lineno)
    return 행


def test_검사할_파일이_있다():
    """0개면 아래 테스트들이 공허하게 통과한다."""
    assert _파일들(*_전체)
    assert _파일들(*_비테스트)
    # 화면 자체가 없으면 아래 테스트들이 존재하지 않는 경로를 가리킨 채
    # 전부 통과한다 — 실패 메시지 안에서만 쓰이던 경로라 존재 단언이 없었다.
    # 화면 은 저장소 루트 기준 경로다 — 다른 _파일들 인자들과 달리 backend/
    # 밖을 가리키므로 한 단계 올라가서 본다(테스트는 backend/ 를 cwd 로 돈다).
    assert Path("..", 화면).exists()


def _권한_WHERE_를_import_하는가(node: ast.AST) -> bool:
    """`권한_WHERE` 에 한 홉으로 닿는 import 형태 셋을 잡는다.

    이름 직접 import(`from adapters.db.permission_sql import 권한_WHERE`)만
    보면, `from adapters.db import permission_sql` 뒤 `permission_sql.
    권한_WHERE("d")` 로 부르는 파일을 놓친다 — import 하고 직접 호출하는데도
    목록에 안 잡힌다(test_demo_isolation.py 의 I1 과 같은 유형).

    받아들인 구멍: `from adapters import db` 뒤 `db.permission_sql.
    권한_WHERE(alias)` 처럼 한 홉 더 들어간 형태는 여기서도 놓친다 — 이
    간접 참조 트리는 끝이 없어 전부 잡으려 하지 않는다. 이 형태를 실제로
    써도 `test_권한_조각_호출_위치가_그대로다`(아래, `_호출_행` 이 이미
    속성 호출을 본다)는 새 호출 위치를 잡아 리뷰어를 끌어들인다 — 그
    테스트가 실질적인 마지막 방어선이다.
    """
    if isinstance(node, ast.ImportFrom):
        if node.module == "adapters.db.permission_sql":
            return any(a.name == "권한_WHERE" for a in node.names)
        if node.module == "adapters.db":
            return any(a.name == "permission_sql" for a in node.names)
        return False
    if isinstance(node, ast.Import):
        return any(a.name == "adapters.db.permission_sql" for a in node.names)
    return False


def test_권한_조각을_import_하는_파일_목록이_그대로다():
    """화면이 인쇄한 grep 의 결과를 집합 동일성으로 고정한다.

    다섯째 importer 가 생기면 화면의 "다섯입니다" 가 조용히 거짓이 된다.
    """
    실제 = {
        str(py)
        for py in _파일들(*_전체)
        for node in ast.walk(_트리(py))
        if _권한_WHERE_를_import_하는가(node)
    }
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

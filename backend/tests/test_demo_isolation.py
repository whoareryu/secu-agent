"""데모 경로 격리.

demo/ 는 의도적으로 새는 코드를 담는다. 그것이 프로덕션 경로에 닿으면
시연 장치가 곧 취약점이 된다. 세 방향 전부를 막는다.

**핵심은 세 번째 테스트다.** 부분집합이 아니라 집합 동일성을 본다 —
main.py 가 언젠가 편의상 demo 를 끌어다 쓰면 그 순간 터진다.
"""

import ast
from pathlib import Path

import pytest

안쪽_계층 = ["core", "adapters", "pipeline", "eval"]
# api/demo.py 를 만드는 커밋에서 채운다(Task 3) — Task 1 시점에는 그 파일이
# 없어 비워뒀다. 목록이 리뷰에 보이는 것이 이 테스트의 목적이다.
데모를_아는_파일 = {"api/demo.py"}


def _import_이름들(py: Path) -> set[str]:
    tree = ast.parse(py.read_text(encoding="utf-8"))
    이름 = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            이름 += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                이름.append(node.module)
            else:
                # from .. import demo — 모듈 경로 없이 이름만 들여오는 형태다.
                # test_boundaries.py 는 이 형태를 의도적으로 무시하지만, 이
                # 울타리는 **의도적으로 새는 코드**를 막는 것이라 다르게 판단한다.
                # 지금은 backend/ 에 최상위 __init__.py 가 없어 이 import 가
                # 런타임에 실패하므로 악용될 수 없다 — 그러나 "지금은 도달
                # 불가능" 은 낡는 논거다. 패키지 구조가 바뀌는 날을 위해 막는다.
                이름 += [a.name for a in node.names]
    return {n.split(".")[0] for n in 이름}


def _파일들(*디렉터리: str) -> list[Path]:
    나온다 = []
    for d in 디렉터리:
        나온다 += sorted(Path(d).rglob("*.py"))
    return 나온다


def test_검사할_파일이_있다():
    """0개면 아래 테스트들이 공허하게 통과한다."""
    assert _파일들(*안쪽_계층)
    assert _파일들("api")


@pytest.mark.parametrize("py", _파일들(*안쪽_계층), ids=str)
def test_안쪽_계층은_demo_를_모른다(py):
    assert "demo" not in _import_이름들(py), f"{py} 가 demo 를 import 한다"


def test_api_에서_demo_를_아는_파일은_정확히_하나다():
    """부분집합이 아니라 **동일성**을 본다.

    "api/demo.py 는 demo 를 import 해도 된다" 만 검사하면, main.py 가
    나중에 하나 끌어다 써도 통과한다. 목록 자체를 고정한다.
    """
    실제 = {str(py) for py in _파일들("api") if "demo" in _import_이름들(py)}
    assert 실제 == 데모를_아는_파일, (
        f"demo 를 import 하는 api 파일이 바뀌었다.\n"
        f"기대: {sorted(데모를_아는_파일)}\n실제: {sorted(실제)}\n"
        "새 파일이 정말 demo 를 알아야 한다면 이 테스트의 목록을 함께 고친다 — "
        "그 변경이 리뷰에 보이는 것이 목적이다."
    )


def test_demo_모듈이_자기_성격을_문서화한다():
    """읽는 사람이 이 파일을 프로덕션 코드로 오해하면 안 된다."""
    독스트링 = ast.get_docstring(ast.parse(Path("demo/naive_search.py").read_text("utf-8")))
    assert 독스트링 is not None
    assert "의도적으로" in 독스트링 and "프로덕션" in 독스트링


def test_모듈_경로_없는_상대_import_도_잡는다(tmp_path):
    """`from .. import demo` 는 모듈 경로가 없어 node.module 이 None 이다.

    이 형태를 흘려보내면 울타리에 구멍이 남는다. 지금 패키지 구조에서는
    런타임에 실패해 악용될 수 없지만, 그 사실은 구조가 바뀌면 사라진다.
    """
    py = tmp_path / "샘플.py"
    py.write_text("from .. import demo\n", encoding="utf-8")
    assert "demo" in _import_이름들(py)


def test_점_있는_경로도_최상위_이름으로_줄인다():
    """`from demo.naive_search import x` 도 demo 로 읽혀야 한다."""
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("from demo.naive_search import naive_ids\n")
        경로 = Path(f.name)
    try:
        assert "demo" in _import_이름들(경로)
    finally:
        경로.unlink()

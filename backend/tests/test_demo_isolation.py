"""데모 경로 격리.

demo/ 는 의도적으로 새는 코드를 담는다. 그것이 답변 경로에 닿으면
시연 장치가 곧 취약점이 된다. 안쪽 계층 · api/ · demo/ 자신 세 방향을 막는다.

**핵심은 `test_api_에서_demo_에_닿는_파일은_정확히_둘이다` 다.** 부분집합이
아니라 집합 동일성을 본다 — main.py 가 언젠가 편의상 demo 를 끌어다 쓰면
그 순간 터진다.

판정은 **한 홉** 단위다: `demo` 뿐 아니라 `api.demo` 도 오염된 이름으로 본다
(아래 `_오염된_이름` 주석). `importlib.import_module("demo.naive_search")`
같은 동적 import 는 범위 밖이다 — 이 울타리의 목적은 샌드박스가 아니라
리뷰 가시성이다.
"""

import ast
from pathlib import Path

import pytest

안쪽_계층 = ["core", "adapters", "pipeline", "eval"]

# 한 홉으로 순진한 경로에 닿는 이름들.
#
# `demo` 만 보면 안 되는 이유: api/demo.py 가 모듈 수준에서
# `from demo.compare import compare` 를 하므로 **`api.demo.compare` 는 곧
# `demo.compare.compare`** 다. 최상위 이름만 남기면 `from api.demo import
# compare` 가 {"api"} 로 읽혀 이 울타리를 그냥 지나가고, 그러면 어느 파일이든
# 한 줄로 순진한 경로를 부르면서 검사기는 초록으로 남는다.
_오염된_이름 = ("demo", "api.demo")

# demo 에 한 홉으로 닿아도 되는 api/ 파일. 목록이 리뷰에 보이는 것이 이
# 테스트의 목적이다.
#
# 둘인 이유: api/demo.py 는 순진한 경로를 실제로 부르는 라우터이고,
# api/deps.py 는 그 라우터를 조립하는 프로덕션 조립 지점이다
# (`from api.demo import build_demo_router`). 조립하는 파일도 같은 한 홉
# 거리에 있으므로 숨기지 않고 적어둔다 — 울타리의 목적은 샌드박스가 아니라
# **리뷰 가시성**이고, 목록에서 빠진 파일이 곧 아무도 안 본 경로다.
데모에_닿는_파일 = {"api/demo.py", "api/deps.py"}


def _import_이름들(py: Path) -> set[str]:
    """import 문이 들여오는 **점 있는 전체 경로**를 모은다.

    최상위 이름으로 줄이지 않는다 — `api.demo` 와 `api.schemas` 를 구분해야
    하기 때문이다. `from X import y` 는 `X` 와 `X.y` 를 둘 다 낸다:
    `from api import demo` 와 `from api.demo import compare` 는 같은 한 홉인데
    AST 에서는 서로 다른 자리에 이름이 나온다.
    """
    tree = ast.parse(py.read_text(encoding="utf-8"))
    이름: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            이름 |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            # node.module 이 None 인 형태(`from .. import demo`)도 이름을 본다.
            # test_boundaries.py 는 이 형태를 의도적으로 무시하지만, 이
            # 울타리는 **의도적으로 새는 코드**를 막는 것이라 다르게 판단한다.
            # 지금은 backend/ 에 최상위 __init__.py 가 없어 이 import 가
            # 런타임에 실패하므로 악용될 수 없다 — 그러나 "지금은 도달
            # 불가능" 은 낡는 논거다. 패키지 구조가 바뀌는 날을 위해 막는다.
            앞 = f"{node.module}." if node.module else ""
            if node.module:
                이름.add(node.module)
            이름 |= {f"{앞}{a.name}" for a in node.names}
    return 이름


def _demo에_닿는_이름들(py: Path) -> set[str]:
    """`py` 가 한 홉으로 demo 에 닿는 import 이름들. 없으면 빈 집합.

    `demo`·`api.demo` 자신과 그 아래 경로(`demo.naive_search`,
    `api.demo.compare`)를 잡는다. `adapters.db.demo_helper` 같은 이름은
    점 경계로 끊어 보므로 걸리지 않는다.
    """
    return {
        n
        for n in _import_이름들(py)
        if any(n == 오염 or n.startswith(f"{오염}.") for 오염 in _오염된_이름)
    }


def _파일들(*디렉터리: str) -> list[Path]:
    나온다 = []
    for d in 디렉터리:
        나온다 += sorted(Path(d).rglob("*.py"))
    return 나온다


def test_검사할_파일이_있다():
    """0개면 아래 테스트들이 공허하게 통과한다."""
    assert _파일들(*안쪽_계층)
    assert _파일들("api")
    assert _파일들("demo")


@pytest.mark.parametrize("py", _파일들(*안쪽_계층), ids=str)
def test_안쪽_계층은_demo_를_모른다(py):
    닿는_것 = _demo에_닿는_이름들(py)
    assert not 닿는_것, f"{py} 가 demo 에 닿는다: {sorted(닿는_것)}"


def test_api_에서_demo_에_닿는_파일은_정확히_둘이다():
    """부분집합이 아니라 **동일성**을 본다.

    "api/demo.py 는 demo 를 import 해도 된다" 만 검사하면, main.py 가
    나중에 하나 끌어다 써도 통과한다. 목록 자체를 고정한다.

    `demo` 뿐 아니라 `api.demo` 도 센다. api/demo.py 가 `compare` 를 모듈
    수준에서 끌어와 두고 있어 `from api.demo import compare` 한 줄이면
    순진한 경로를 그대로 부를 수 있기 때문이다 — 최상위 이름만 보던 시절에는
    그 한 줄이 이 테스트를 통과했다.

    api/ 안에서는 이 동일성이 여러 홉도 덮는다: api/x.py 가 api/y.py 를
    거쳐 demo 에 닿으려면 y.py 가 이 목록에 올라와야 하고, 그러면 그 변경이
    여기서 보인다.
    """
    실제 = {str(py) for py in _파일들("api") if _demo에_닿는_이름들(py)}
    assert 실제 == 데모에_닿는_파일, (
        f"demo 에 닿는 api 파일이 바뀌었다.\n"
        f"기대: {sorted(데모에_닿는_파일)}\n실제: {sorted(실제)}\n"
        "새 파일이 정말 demo 를 알아야 한다면 이 테스트의 목록을 함께 고친다 — "
        "그 변경이 리뷰에 보이는 것이 목적이다. README 의 데모 문단도 이 목록을 "
        "인용하므로 같이 고친다."
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
    assert _demo에_닿는_이름들(py)


@pytest.mark.parametrize(
    "코드",
    [
        "import demo",
        "import demo.naive_search",
        "from demo.naive_search import naive_ids",
        "from demo import compare",
        # 아래 넷이 한 홉 우회 형태다. api/demo.py 가 compare 를 모듈 수준에
        # 끌어와 두고 있으므로 전부 순진한 경로에 그대로 닿는다.
        "import api.demo",
        "from api.demo import compare",
        "from api import demo",
        "from api import demo as d",
    ],
    ids=str,
)
def test_한_홉으로_demo_에_닿는_형태를_전부_잡는다(tmp_path, 코드):
    py = tmp_path / "샘플.py"
    py.write_text(f"{코드}\n", encoding="utf-8")
    assert _demo에_닿는_이름들(py), f"{코드!r} 를 놓쳤다"


@pytest.mark.parametrize(
    "코드",
    ["from api.schemas import CompareRequest", "from adapters.db import demo_helper"],
    ids=str,
)
def test_이름이_비슷할_뿐인_import_는_잡지_않는다(tmp_path, 코드):
    """점 경계로 끊어 본다 — 안 그러면 울타리가 무관한 파일을 물고 신뢰를 잃는다."""
    py = tmp_path / "샘플.py"
    py.write_text(f"{코드}\n", encoding="utf-8")
    assert not _demo에_닿는_이름들(py)


# `demo/` 가 LLM 라이브러리에 닿으면 "이 경로는 요금이 0원" 이라는 화면 문구
# (LeakCompare.tsx 의 로딩 문구)와 demo/compare.py 의 모듈 독스트링이 거짓이
# 된다. test_demo_api.py 의 `test_LLM_을_부르지_않는다` 는 독 든 에이전트
# 공장으로 **배선**이 모델에 닿지 않음을 보일 뿐, demo/ 자신에 대해서는 아무
# 말도 하지 않는다. 여기서 구조로 못 박는다.
_LLM_라이브러리 = {"langchain", "langchain_google_genai", "langgraph", "google", "openai"}


@pytest.mark.parametrize("py", _파일들("demo"), ids=str)
def test_demo_는_LLM_라이브러리를_모른다(py):
    최상위 = {n.split(".")[0] for n in _import_이름들(py)}
    닿는_것 = 최상위 & _LLM_라이브러리
    assert not 닿는_것, f"{py} 가 {sorted(닿는_것)} 을 import 한다 — 이 경로는 LLM 을 부르지 않는다"

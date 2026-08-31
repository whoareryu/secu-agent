"""계층 경계를 CI 가 강제한다.

spec 2.4 의 규칙을 문서가 아니라 테스트로 만든다. 방침만 적어두면 지켜지지 않는다.
"""

import ast
from pathlib import Path

import pytest

# core/ 는 안쪽이다. 이 이름들은 전부 바깥이다.
바깥_계층 = ("adapters", "api", "pipeline", "eval")

# core/ 에 들어오는 순간 경계가 무너지는 것들.
# langchain 이 여기 있는 것이 핵심이다 — 프레임워크가 도메인에 스며들면
# 버전이 바뀔 때 도메인 로직까지 끌려간다(spec 2.3).
인프라_프레임워크 = (
    "psycopg",
    "sqlalchemy",
    "anthropic",
    "fastapi",
    "langchain",
    "langgraph",
    "sentence_transformers",
    "torch",
    "transformers",
    "pypdf",
)


def _최상위_import(py: Path) -> list[str]:
    """파일이 import 하는 모듈들의 최상위 이름."""
    tree = ast.parse(py.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            # `from . import x` 는 node.module 이 None 이다 — 상대 import 는 검사 대상이 아니다
            if node.level == 0 and node.module:
                names.append(node.module)
    return [n.split(".")[0] for n in names]


def _core_파일들() -> list[Path]:
    return sorted(Path("core").rglob("*.py"))


def test_core_에_검사할_파일이_있다():
    # 파일이 0개면 아래 두 테스트가 공허하게 통과한다.
    assert _core_파일들(), "core/ 에 파이썬 파일이 없다"


@pytest.mark.parametrize("py", _core_파일들(), ids=lambda p: str(p))
def test_core_는_바깥_계층을_import_하지_않는다(py):
    for name in _최상위_import(py):
        assert name not in 바깥_계층, f"{py} 가 바깥 계층 {name} 을 import 한다"


@pytest.mark.parametrize("py", _core_파일들(), ids=lambda p: str(p))
def test_core_는_인프라_프레임워크를_import_하지_않는다(py):
    for name in _최상위_import(py):
        assert name not in 인프라_프레임워크, f"{py} 가 {name} 을 import 한다"

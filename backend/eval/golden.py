"""골든셋 로더.

JSONL 인 이유: 한 줄에 한 건이라 diff 가 읽히고, 건을 더해도 기존 줄이
움직이지 않는다.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from core.types import Principal

DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "golden.jsonl"


@dataclass(frozen=True)
class GoldenQuery:
    query: str
    principal: Principal
    relevant: frozenset[str]


def load(path: Path = DEFAULT_PATH) -> list[GoldenQuery]:
    출력: list[GoldenQuery] = []
    for 줄 in path.read_text(encoding="utf-8").splitlines():
        줄 = 줄.strip()
        if not 줄:
            continue
        d = json.loads(줄)
        출력.append(
            GoldenQuery(
                query=d["query"],
                principal=Principal(department=d["department"], clearance=int(d["clearance"])),
                relevant=frozenset(d["relevant"]),
            )
        )
    return 출력

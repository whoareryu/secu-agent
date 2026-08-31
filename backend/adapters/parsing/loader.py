"""확장자로 파서를 고른다.

DOCX·MD 는 W1 범위 밖이다. 지원하지 않는 포맷은 조용히 건너뛰지 않고
예외를 던진다 — 조용히 넘기면 적재가 끝난 뒤에야 문서가 없다는 것을 안다.
"""

from pathlib import Path

from adapters.parsing import pdf
from core.types import Chunk, Clause


def load(path: Path) -> tuple[list[Clause], list[Chunk]]:
    suffix = path.suffix.lower()
    if suffix != ".pdf":
        raise ValueError(f"아직 지원하지 않는 포맷이다: {suffix} ({path})")
    clauses = pdf.split_clauses(pdf.extract_text(path))
    return clauses, pdf.chunk_clauses(clauses)

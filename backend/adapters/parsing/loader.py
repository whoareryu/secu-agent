"""확장자로 파서를 고른다.

DOCX 는 아직 범위 밖이다. 지원하지 않는 포맷은 조용히 건너뛰지 않고
예외를 던진다 — 조용히 넘기면 적재가 끝난 뒤에야 문서가 없다는 것을 안다.
"""

from pathlib import Path

from adapters.parsing import markdown, pdf
from core.types import Chunk, Clause


def load(path: Path) -> tuple[list[Clause], list[Chunk]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        clauses = pdf.split_clauses(pdf.extract_text(path))
        return clauses, pdf.chunk_clauses(clauses)
    if suffix == ".md":
        return markdown.load(path)
    raise ValueError(f"아직 지원하지 않는 포맷이다: {suffix} ({path})")


def load_meta(path: Path) -> dict:
    """문서가 스스로 들고 있는 메타데이터. PDF 에는 없다.

    빈 딕셔너리를 주는 것이 맞다 — PDF 의 권한은 적재하는 사람이
    CLI 인자로 부여한다(spec 4.1).
    """
    if path.suffix.lower() == ".md":
        return markdown.load_meta(path)
    return {}

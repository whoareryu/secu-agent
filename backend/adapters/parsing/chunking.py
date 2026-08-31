"""조항 안에서 청킹한다. 문서 포맷과 무관한 규칙이라 파서들이 공유한다.

pdf.py 에 있던 것을 옮겼다 — markdown.py 라는 두 번째 호출자가 생겼기
때문이다. 청킹 규칙이 두 벌로 갈라지면 PDF 와 MD 의 청크 크기가 조용히
달라지고, 평가 지표가 포맷에 따라 흔들린다.
"""

from core.types import Chunk, Clause


def chunk_clauses(clauses: list[Clause], max_chars: int = 900, overlap: int = 150) -> list[Chunk]:
    """조항 안에서만 청킹한다. 청크는 조항 경계를 넘지 않는다.

    겹침을 두는 이유: 문장이 청크 경계에서 잘리면 그 문장은 어느 쪽에서도
    온전히 검색되지 않는다.
    """
    if overlap >= max_chars:
        # step = max_chars - overlap 가 0 이하가 되어 시작 위치가 전진하지
        # 않는다 — while 루프가 끝나지 않는다.
        raise ValueError(f"overlap({overlap})은 max_chars({max_chars})보다 작아야 한다")
    chunks: list[Chunk] = []
    for c in clauses:
        본문 = c.text
        if len(본문) <= max_chars:
            chunks.append(Chunk(clause_code=c.code, ordinal=0, text=본문))
            continue

        시작 = 0
        ordinal = 0
        step = max_chars - overlap
        while 시작 < len(본문):
            조각 = 본문[시작 : 시작 + max_chars]
            chunks.append(Chunk(clause_code=c.code, ordinal=ordinal, text=조각))
            if 시작 + max_chars >= len(본문):
                break
            시작 += step
            ordinal += 1
    return chunks

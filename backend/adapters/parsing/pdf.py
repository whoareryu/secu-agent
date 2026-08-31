"""PDF → 조항 → 청크.

ISMS-P 안내서는 "2.6.1 네트워크 접근" 형태로 조항 코드가 줄 앞에 온다.
조항 경계를 먼저 잡고 그 안에서 청킹하는 이유: 경계를 무시하고 고정 길이로
자르면 한 청크가 두 조항에 걸치고, 리포트에서 잘못된 조항을 인용하게 된다.

이 모듈은 문서 포맷만 안다 — DB 도 임베딩도 모른다.
"""

import re
from pathlib import Path

from pypdf import PdfReader

from core.types import Chunk, Clause

# "1.3.1 보호대책 구현" — 줄 앞의 조항 코드와 제목.
#
# 각 자리는 반드시 \d+ 다. \d 로 쓰면 2.10·2.11·2.12 가 구조적으로 매치되지
# 않는다 — 실측에서 그 16개(2.10.1~2.12.2)를 통째로 잃었다. 그 안에는
# "2.11.3 이상행위 분석 및 모니터링" 처럼 이 프로젝트의 핵심 조항이 들어 있다.
# 실측: 255쪽 전문에서 고유 조항 102개 — ISMS-P 2022 공식 인증기준 수와 일치한다.
조항_패턴 = re.compile(r"^\s*(\d+\.\d+\.\d+)\s+(\S[^\n]{0,60})$", re.MULTILINE)


def extract_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def split_clauses(text: str) -> list[Clause]:
    """조항 코드로 텍스트를 분할한다.

    조항 앞의 머리말(표지·목차)은 버린다 — 조항이 아니고, 검색되면
    "규정 어디에 있다"고 말할 수 없다.

    각 조항 코드는 목차와 본문에 각각 한 번씩 등장한다(실측: 204회 = 고유
    102개 x 2, 예외 없음). 같은 코드가 두 번 잡히면 본문이 더 긴 쪽을 채택한다 —
    목차 항목은 다음 목차 줄이 바로 뒤따라 본문이 극히 짧게 잘리기
    때문이다. 순서는 최초 등장 순서를 유지한다.
    """
    matches = list(조항_패턴.finditer(text))
    by_code: dict[str, Clause] = {}
    order: list[str] = []
    for i, m in enumerate(matches):
        시작 = m.end()
        끝 = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        본문 = text[시작:끝].strip()
        code = m.group(1)
        clause = Clause(code=code, title=m.group(2).strip(), text=본문)
        기존 = by_code.get(code)
        if 기존 is None:
            order.append(code)
            by_code[code] = clause
        elif len(clause.text) > len(기존.text):
            by_code[code] = clause
    return [by_code[code] for code in order]


def chunk_clauses(
    clauses: list[Clause], max_chars: int = 900, overlap: int = 150
) -> list[Chunk]:
    """조항 안에서만 청킹한다. 청크는 조항 경계를 넘지 않는다.

    겹침을 두는 이유: 문장이 청크 경계에서 잘리면 그 문장은 어느 쪽에서도
    온전히 검색되지 않는다.
    """
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

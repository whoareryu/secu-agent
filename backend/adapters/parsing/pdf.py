"""PDF → 조항 → 청크.

ISMS-P 안내서는 "2.6.1 네트워크 접근" 형태로 조항 코드가 줄 앞에 온다.
조항 경계를 먼저 잡고 그 안에서 청킹하는 이유: 경계를 무시하고 고정 길이로
자르면 한 청크가 두 조항에 걸치고, 리포트에서 잘못된 조항을 인용하게 된다.

이 모듈은 문서 포맷만 안다 — DB 도 임베딩도 모른다.
"""

import re
from pathlib import Path

from pypdf import PdfReader

from adapters.parsing.chunking import chunk_clauses
from core.types import Clause

# "1.3.1 보호대책 구현" — 줄 앞의 조항 코드와 제목.
#
# 각 자리는 반드시 \d+ 다. \d 로 쓰면 2.10·2.11·2.12 가 구조적으로 매치되지
# 않는다 — 실측에서 그 16개(2.10.1~2.12.2)를 통째로 잃었다. 그 안에는
# "2.11.3 이상행위 분석 및 모니터링" 처럼 이 프로젝트의 핵심 조항이 들어 있다.
# 실측: 255쪽 전문에서 고유 조항 102개 — ISMS-P 2022 공식 인증기준 수와 일치한다.
조항_패턴 = re.compile(r"^\s*(\d+\.\d+\.\d+)\s+(\S[^\n]{0,60})$", re.MULTILINE)

# 마지막 조항(3.5.3) 뒤에 붙는 참고문헌 목록의 시작 표지.
# ISMS-P 안내서 실물(인쇄본 기준 약 250쪽)의 후주에서 실측으로 확인한
# 값이다 — 일반적인 규칙이 아니라 이 문서에 한정된 값이므로, 다른
# 안내서나 개정판에서는 다시 확인해야 한다. 이 표지가 없으면(픽스처처럼
# 후주가 없는 텍스트) 마지막 조항은 지금처럼 문서 끝까지 이어진다.
참고자료_표지 = "참고자료"


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
        if i + 1 < len(matches):
            끝 = matches[i + 1].start()
        else:
            # 마지막 조항은 다음 조항 코드가 없어 원래 문서 끝까지 이어진다.
            # 그런데 ISMS-P 안내서는 마지막 조항(3.5.3) 바로 뒤에 참고문헌
            # 목록이 붙어 있어, 표지를 찾지 못하면 그 목록까지 본문으로
            # 삼켜버린다. 표지가 있으면 거기서 끊고, 없으면(픽스처처럼
            # 후주가 없는 텍스트) 지금까지처럼 문서 끝까지 쓴다.
            표지_위치 = text.find(참고자료_표지, 시작)
            끝 = 표지_위치 if 표지_위치 != -1 else len(text)
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


# loader 와 기존 테스트가 pdf.chunk_clauses 로 부른다. 이름을 유지한다.
__all__ = ["extract_text", "split_clauses", "chunk_clauses", "조항_패턴", "참고자료_표지"]

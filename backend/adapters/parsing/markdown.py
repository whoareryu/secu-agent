"""마크다운 → 조항 → 청크.

합성 사내 규정을 읽는다. 각 문서는 front matter 로 자기 권한을 들고 있다 —
CLI 인자로 받으면 어느 문서가 어느 등급인지가 셸 히스토리에만 남고,
재적재가 다른 결과를 낸다.

조항 코드는 ISMS-P 와 같은 세 자리(4.1.1) 형태다. 파서 두 벌이 다른 코드
체계를 쓰면 리포트의 인용 형식이 문서마다 달라진다. 4.x·5.x·6.x 를 쓰는
이유는 ISMS-P 가 1.x~3.x 를 차지하고 있어 코드가 부딪히지 않기 위해서다.

이 모듈은 문서 포맷만 안다 — DB 도 임베딩도 모른다.
"""

import re
from pathlib import Path

import yaml

from adapters.parsing.chunking import chunk_clauses
from core.types import Chunk, Clause

_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)

# "## 6.1.1 성과급 재원 산정" — pdf.조항_패턴 과 같은 세 자리 규칙이다.
# 각 자리가 \d+ 인 것이 중요하다. \d 로 쓰면 4.10.1 이 매치되지 않는다 —
# W1 실측에서 ISMS-P 조항 16개를 그렇게 잃었다.
# 제목 길이 상한. 넘으면 그 줄이 조항으로 안 잡히고, **조항 전체가 앞
# 조항의 본문으로 삼켜지면서 조항 코드가 사라진다** — 에러 없이 데이터가
# 없어지는 경로다. 상한 자체는 필요하다(본문 한 줄이 우연히 "2.6.1 " 로
# 시작할 때 조항으로 오인하는 것을 막는다). 실측으로 여유를 넓혔다: 지금
# 코퍼스의 최장 제목은 21자이고, 200 으로 올려도 조항 102개·청크 314개가
# 그대로다.
_제목_최대 = 200
조항_패턴 = re.compile(rf"^##\s+(\d+\.\d+\.\d+)\s+(\S[^\n]{{0,{_제목_최대}}})$", re.MULTILINE)


def parse_front_matter(text: str) -> tuple[dict, str]:
    """(메타, 본문) 으로 나눈다. front matter 가 없으면 예외를 던진다.

    조용히 기본값을 쓰지 않는다 — 등급 3 문서가 등급 1 로 적재되면
    그것이 곧 누출이고, 검색이 되어버리므로 발견이 아주 늦다.
    """
    m = _FRONT_MATTER.match(text)
    if not m:
        raise ValueError("front matter 가 없다 — 문서가 자기 권한을 들고 있어야 한다")
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError(f"front matter 가 매핑이 아니다: {type(meta).__name__}")
    return meta, text[m.end() :]


def split_clauses(body: str) -> list[Clause]:
    """ "## 6.1.1 제목" 으로 본문을 조항 단위로 나눈다.

    첫 조항 앞의 머리말은 버린다 — 조항이 아니라서 "규정 어디에 있다"고
    말할 수 없다. PDF 파서가 표지·목차를 버리는 것과 같은 이유다.
    """
    matches = list(조항_패턴.finditer(body))
    clauses: list[Clause] = []
    for i, m in enumerate(matches):
        끝 = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        clauses.append(
            Clause(code=m.group(1), title=m.group(2).strip(), text=body[m.end() : 끝].strip())
        )
    return clauses


def load(path: Path) -> tuple[list[Clause], list[Chunk]]:
    _, body = parse_front_matter(path.read_text(encoding="utf-8"))
    clauses = split_clauses(body)
    return clauses, chunk_clauses(clauses)


def load_meta(path: Path) -> dict:
    meta, _ = parse_front_matter(path.read_text(encoding="utf-8"))
    return meta

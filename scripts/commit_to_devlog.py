#!/usr/bin/env python3
"""커밋 하나를 Jekyll 개발 로그 한 건으로 옮긴다.

PostToolUse 훅이 `git commit` 성공 직후 호출한다. 커밋 메시지에 이미
"무엇을 왜 했는가"가 들어 있으므로 LLM 없이 그대로 가공한다 — 훅이
느려지거나 비용이 들거나, 같은 커밋에서 매번 다른 문장이 나오는 일이 없다.

만들어진 파일은 커밋하지 않고 워킹트리에 남긴다. 훅 안에서 커밋하면
그 커밋이 다시 훅을 부르고, 로그가 로그를 기록하게 된다.
"""

import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

LOGS = Path("jekyll/_logs")

# 저장소 디렉토리 → 칸반·개발로그의 작업 영역.
# 이 매핑은 jekyll/kanban.markdown 의 area 설명과 같은 이름을 쓴다.
AREA_RULES: list[tuple[str, str]] = [
    ("backend/pipeline/", "data"),
    ("backend/adapters/source/", "data"),
    ("backend/adapters/db/", "data"),
    ("backend/db/", "data"),
    ("data/", "data"),
    ("backend/core/", "rag"),
    ("backend/eval/", "rag"),
    ("backend/adapters/embedding/", "rag"),
    ("backend/adapters/llm/", "rag"),
    ("backend/api/", "api"),
    ("frontend/", "web"),
    ("flutter/", "web"),
    ("backend/", "api"),  # 위에서 안 걸린 backend 파일 (pyproject·requirements 등)
    ("jekyll/", "infra"),
    (".github/", "infra"),
    ("scripts/", "infra"),
    ("docs/", "infra"),
]
DEFAULT_AREA = "infra"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def area_for(paths: list[str]) -> str:
    """변경 파일들의 다수결로 영역을 정한다."""
    hits = Counter()
    for p in paths:
        for prefix, area in AREA_RULES:
            if p.startswith(prefix):
                hits[area] += 1
                break
        else:
            hits[DEFAULT_AREA] += 1
    return hits.most_common(1)[0][0] if hits else DEFAULT_AREA


def next_seq(day: str) -> int:
    """그날 이미 있는 로그 다음 번호. 파일명 정렬이 시간순이 되도록 두 자리로 쓴다."""
    existing = [
        int(m.group(1))
        for f in LOGS.glob(f"{day}-*.md")
        if (m := re.match(rf"{day}-(\d+)-", f.name))
    ]
    return max(existing, default=0) + 1


def to_bullets(subject: str, body: str) -> str:
    """커밋 제목을 굵은 리드로, 본문은 원래 줄 구조를 지킨 채 들여쓴다.

    본문을 문단 단위로 합치지 않는다 — 커밋 메시지의 목록은 목록으로 쓰인
    것이고, 한 줄로 이어붙이면 읽을 수 없게 된다.
    """
    out = [f"- **{subject}**"]

    kept: list[str] = []
    for raw in body.strip().splitlines():
        line = raw.rstrip()
        # 트레일러(Co-Authored-By:, Claude-Session: 등)는 로그에 남기지 않는다.
        if re.match(r"^[A-Za-z][A-Za-z-]*:\s", line):
            continue
        kept.append(line)

    # 앞뒤 빈 줄 정리
    while kept and not kept[0].strip():
        kept.pop(0)
    while kept and not kept[-1].strip():
        kept.pop()

    for line in kept:
        out.append(f"  {line}" if line.strip() else "")
    return "\n".join(out)


def main() -> int:
    # 훅 입력(stdin)은 읽고 버린다 — 필요한 것은 전부 git 에서 온다.
    try:
        sys.stdin.read()
    except Exception:
        pass

    if not LOGS.is_dir():
        return 0  # Jekyll 사이트가 없는 체크아웃에서는 조용히 지나간다

    try:
        sha = _git("rev-parse", "--short", "HEAD")
        subject = _git("log", "-1", "--pretty=%s")
        body = _git("log", "-1", "--pretty=%b")
        changed = [p for p in _git("show", "--name-only", "--pretty=", "HEAD").splitlines() if p]
    except subprocess.CalledProcessError:
        return 0  # 커밋이 없거나 git 저장소가 아니면 아무것도 하지 않는다

    if not changed:
        return 0

    # 로그만 건드린 커밋은 기록하지 않는다 — 로그가 로그를 기록하는 노이즈를 막는다.
    if all(p.startswith("jekyll/_logs/") for p in changed):
        return 0

    # 이미 이 커밋을 기록했으면 아무것도 하지 않는다.
    #
    # 훅은 한 커밋에 여러 번 불릴 수 있다 — 서브에이전트의 Bash 호출에도 적용되고,
    # HEAD 가 그대로인 동안 몇 번이든 발동한다. 트리거 조건을 아무리 좁혀도
    # "같은 커밋에 두 번 불리지 않는다"는 보장은 없으므로, 멱등성은 여기서 만든다.
    marker = f"커밋 `{sha}`"
    for existing in LOGS.glob("*.md"):
        if marker in existing.read_text(encoding="utf-8"):
            return 0

    day = date.today().isoformat()
    area = area_for(changed)
    seq = next_seq(day)
    path = LOGS / f"{day}-{seq:02d}-{area}.md"

    path.write_text(
        f"---\ndate: {day}\narea: {area}\nseq: {seq}\n---\n\n"
        f"{to_bullets(subject, body)}\n\n"
        f"- 커밋 `{sha}` · 파일 {len(changed)}개\n",
        encoding="utf-8",
    )

    print(json.dumps({"systemMessage": f"개발 로그를 남겼다 → {path}"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""에이전트 실행 정책 — 도구 출력 검증.

LangChain 은 도구가 돌려준 것을 그대로 LLM 에 넘긴다. 권한 밖 문서가
도구 출력에 섞이면 프레임워크는 막지 않는다(spec 5.4).

이 모듈이 core/ 에 있는 것이 요점이다. adapters/agent/ 의 런너가 도구를
@tool 로 감쌀 때도 이 검증을 우회할 수 없다.
"""

from collections.abc import Sequence

from core.access.visibility import visible
from core.types import PolicyHit, Principal

# 도구 호출 상한. 넘으면 그 도구만 막고 모델은 그때까지의 결과로 답한다.
# 상한이 없으면 에이전트가 도구를 반복 호출하며 비용과 지연이 무한정 늘어난다.
# 8 은 "규정 검색 → 재검색" 을 여러 바퀴 돌 수 있는 여유다(상위 spec 7.2).
MAX_TOOL_CALLS = 8


class AccessViolation(Exception):
    """도구 출력에 권한 밖 항목이 있다. 사전 필터링이 깨졌다는 뜻이다."""


def enforce(hits: Sequence[PolicyHit], p: Principal) -> list[PolicyHit]:
    """권한 밖 항목이 있으면 예외를 던진다. 없으면 그대로 돌려준다.

    정상 경로에서는 절대 발동하지 않는다 — 발동했다는 것은 사전 필터링이
    깨졌다는 뜻이고, 조용히 걸러내면 그 사실이 묻힌다. 걸러내는 순간
    사후 필터링이 되고, 버그가 결과 개수 뒤에 숨는다.

    메시지에 chunk_id 만 담는다. 본문이나 문서 제목을 담으면 이 예외가
    로그와 에러 응답을 타고 나가면서 내용 누출 경로가 된다 — 막으려고
    만든 장치가 통로가 된다.
    """
    위반 = [h.chunk_id for h in hits if not visible(h.required_clearance, h.allowed_departments, p)]
    if 위반:
        raise AccessViolation(
            f"권한 밖 청크가 도구 출력에 섞였다: {위반} "
            f"(부서 {p.department} · 등급 {p.clearance}) — 사전 필터링이 깨졌다"
        )
    return list(hits)

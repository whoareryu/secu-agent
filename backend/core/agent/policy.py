"""에이전트 실행 정책 — 도구 출력 검증.

LangChain 은 도구가 돌려준 것을 그대로 LLM 에 넘긴다. 권한 밖 문서가
도구 출력에 섞이면 프레임워크는 막지 않는다(spec 5.4).

이 모듈이 core/ 에 있는 것이 요점이다. adapters/agent/ 의 런너가 도구를
@tool 로 감쌀 때도 이 검증을 우회할 수 없다.
"""

from collections.abc import Sequence

from core.access.visibility import visible
from core.types import LogEvent, PolicyHit, Principal

# 도구 호출 상한. 넘으면 그 도구만 막고 모델은 그때까지의 결과로 답한다.
# 상한이 없으면 에이전트가 도구를 반복 호출하며 비용과 지연이 무한정 늘어난다.
# 8 은 "규정 검색 → 재검색" 을 여러 바퀴 돌 수 있는 여유다(상위 spec 7.2).
MAX_TOOL_CALLS = 8

# 모델 호출 상한. 도구 상한만으로는 종료가 보장되지 않는다 — 차단된 도구를
# 계속 시도하는 모델은 모델 호출만 반복하고, 비용은 그쪽에서 난다.
# 정상 경로에서는 발동하지 않는다: 도구 8회 + 최종 답변 1회면 충분하다.
MAX_MODEL_CALLS = 12

# 한 번의 검색이 가져올 수 있는 최대 조항 수. 호출 횟수를 묶어도 한 번의
# 작업량이 안 묶이면 비용이 그쪽으로 샌다 — hybrid.search 는 후보를 k 의
# 5배로 잡으므로 k 가 크면 검색 한 번이 그만큼 증폭된다.
MAX_K = 20


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


# 로그 조회 한 번에 가져올 최대 이벤트 수. MAX_K 와 짝을 이루는 작업량
# 상한이다 — 호출자가 LLM 이라 그 값을 믿지 않는다.
MAX_LOG_LIMIT = 50

# 로그 집계의 범위 고지. **조건 없이 항상 붙는다.**
#
# 숨겨진 이벤트가 1000건이든 0건이든 이 문구가 같고, 전 호스트를 볼 수
# 있는 주체에게도 같은 문장이 나간다. 값에 따라 변하지 않는 고지는 통로가
# 아니다 — 통로는 관측값이 숨은 데이터의 유무에 따라 *변할* 때 생긴다.
#
# 이 문구가 필요한 이유는 누출이 아니라 반대쪽이다. "인증 실패 12건" 은
# 세상에 대한 절대적 주장으로 읽히고, 그것을 믿은 담당자는 35건을 놓친
# 채 대응을 종료한다(보충 spec 2.2).
로그_범위_고지 = "이 집계는 열람 권한이 있는 호스트의 기록만 셉니다."


def enforce_events(events: Sequence[LogEvent], p: Principal) -> list[LogEvent]:
    """권한 밖 이벤트가 있으면 터진다. 걸러내지 않는다.

    enforce 와 같은 이유다 — 조용히 걸러내면 사후 필터링이 되고 버그가
    개수 뒤에 숨는다(상위 spec 5.4).

    메시지에는 **이벤트 id 만** 담는다. raw 도 호스트 이름도 담지 않는다.
    오류가 우회 경로가 되면 안 된다.
    """
    새는_것 = [e for e in events
              if not visible(e.required_clearance, e.allowed_departments, p)]
    if 새는_것:
        raise AccessViolation(
            f"권한 밖 이벤트가 도구 출력에 있다: {[e.id for e in 새는_것]}"
        )
    return list(events)

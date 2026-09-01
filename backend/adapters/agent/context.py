"""에이전트 한 번의 실행에 딸리는 런타임 컨텍스트.

principal 이 여기 있는 것이 요점이다 — 도구 인자가 아니라 컨텍스트다.
그래서 LLM 이 볼 수도, 지정할 수도 없다.

collected 는 도구가 채우고 호출자가 읽는다. 컨텍스트 객체는 그래프를
지나 도구까지 **같은 객체로** 전달되므로(실측: id 가 일치), 도구가 여기에
담은 것을 invoke 가 끝난 뒤 바깥에서 그대로 꺼낼 수 있다. API 가
인용 근거를 얻는 경로가 이것이다.
"""

from dataclasses import dataclass, field

from core.types import PolicyHit, Principal


@dataclass
class AgentContext:
    principal: Principal
    collected: list[PolicyHit] = field(default_factory=list)
    # 도구가 실제로 실행된 횟수. ToolMessage 개수를 세면 상한에 막힌 호출도
    # 잡힌다 — 차단된 호출도 ToolMessage 를 만들기 때문이다. 이건 도구 본문이
    # 실행될 때만 늘어난다.
    tool_calls: int = 0
    # query_logs 가 불렸는가. API 가 범위 고지를 붙일지 정하는 데 쓴다.
    # 모델이 고지를 문장에 넣어주기를 바라지 않는다 — 모델은 잊는다.
    queried_logs: bool = False

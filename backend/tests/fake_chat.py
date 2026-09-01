"""대본대로 답하는 가짜 채팅 모델.

이것이 있어야 에이전트를 API 키 없이, 비용 없이 끝까지 테스트할 수 있다.

langchain_core 의 GenericFakeChatModel 을 쓸 수 없다 — bind_tools 를
구현하지 않아 create_agent 안에서 NotImplementedError 가 난다(실측).
필요한 것은 bind_tools 와 _generate 둘뿐이다.
"""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class 대본모델(BaseChatModel):
    """정해둔 AIMessage 를 순서대로 낸다. 대본이 끝나면 마지막 것을 반복한다."""

    대본: list[AIMessage] = []
    호출수: int = 0
    본_도구: list[Any] = []

    @property
    def _llm_type(self) -> str:
        return "대본모델"

    def bind_tools(self, tools, **kwargs):
        # 어떤 도구가 모델에게 전달되는지 기록한다 — 스키마 검사가 이걸 본다.
        self.본_도구 = list(tools)
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        msg = self.대본[min(self.호출수, len(self.대본) - 1)]
        self.호출수 += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])

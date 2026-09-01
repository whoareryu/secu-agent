"""Anthropic 모델 구성. 모델 ID 가 이 파일에만 있다.

thinking 을 지정하지 않는다 — Claude Opus 5 는 생략하면 adaptive 로 돈다.
검증할 수 없는 인자를 넣지 않는다.
"""

import os

from langchain_anthropic import ChatAnthropic

# 날짜 접미사를 붙이지 않는다. 이 문자열 그대로가 완전한 모델 ID 다.
MODEL_ID = "claude-opus-5"
MAX_TOKENS = 4096


def build_model(api_key: str | None = None) -> ChatAnthropic:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY 가 없다. 환경변수로 주거나 build_model(api_key=...) 로 넘긴다."
        )
    return ChatAnthropic(model=MODEL_ID, max_tokens=MAX_TOKENS, api_key=key)

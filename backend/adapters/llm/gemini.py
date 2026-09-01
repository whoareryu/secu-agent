"""Gemini 모델 구성. 모델 ID 가 이 파일에만 있다.

프로바이더를 바꾸는 변경이 이 파일 하나로 끝나는 것이 adapters 격리의
목적이다 — adapters/agent/runner.py 는 BaseChatModel 만 알고, core/ 는
LLM 이 있다는 사실조차 모른다.

환경변수가 GOOGLE_API_KEY 인 이유: langchain-google-genai 는 GOOGLE_API_KEY 와
GEMINI_API_KEY 를 모두 읽지만 GOOGLE_API_KEY 를 권장하고, 둘 다 설정되면
그것을 쓰면서 경고를 낸다. 하나만 쓴다.
"""

import os

from langchain_google_genai import ChatGoogleGenerativeAI

# 공식 문서가 "복잡한 코딩, 에이전트 워크플로, 신뢰할 수 있는 다단계 실행" 용으로
# 명시한 모델이다. 이 프로젝트는 도구를 부르는 에이전트다.
MODEL_ID = "gemini-3.7-flash"
MAX_OUTPUT_TOKENS = 4096


def build_model(api_key: str | None = None) -> ChatGoogleGenerativeAI:
    key = api_key or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "GOOGLE_API_KEY 가 없다. 환경변수로 주거나 build_model(api_key=...) 로 넘긴다."
        )
    return ChatGoogleGenerativeAI(model=MODEL_ID, max_output_tokens=MAX_OUTPUT_TOKENS, api_key=key)

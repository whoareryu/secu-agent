"""Gemini 모델 구성. 모델 ID 가 이 파일에만 있다.

**Vertex(Agent Platform) 백엔드를 쓴다.** AI Studio 의 Gemini API 경로가 아니다.
이유는 요금이다 — Google Cloud 무료 체험판 크레딧이 AI Studio Gemini API 는
커버하지 않고 Agent Platform 은 커버한다.

자격증명은 ADC(Application Default Credentials)로 받는다. 이 경로는 API 키를
받지 않는다 — 실측: api_key 인자를 주면 무시하고 ADC 를 찾다가 실패한다.
서비스 계정 JSON 의 경로를 GOOGLE_APPLICATION_CREDENTIALS 로 준다.

thinking 을 지정하지 않는다 — 모델이 알아서 한다. 검증할 수 없는 인자를
넣지 않는다.
"""

import os

from langchain_google_genai import ChatGoogleGenerativeAI

# 공식 문서가 "복잡한 코딩, 에이전트 워크플로, 신뢰할 수 있는 다단계 실행" 용으로
# 명시한 모델이다. 이 프로젝트는 도구를 부르는 에이전트다.
MODEL_ID = "gemini-3.7-flash"
MAX_OUTPUT_TOKENS = 4096

# 실측으로 동작을 확인한 리전. 바꾸려면 실제로 호출해보고 바꾼다.
DEFAULT_LOCATION = "global"

# 한 번의 모델 호출 상한(초). 에이전트는 이것을 도구 호출마다 쓸 수 있다.
TIMEOUT_SECONDS = 60


def build_model(project: str | None = None, location: str | None = None) -> ChatGoogleGenerativeAI:
    """Vertex 백엔드로 모델을 만든다.

    자격증명은 인자로 받지 않는다. GOOGLE_APPLICATION_CREDENTIALS 가 가리키는
    서비스 계정 JSON 을 라이브러리가 읽는다 — 자격증명을 파이썬 인자로 나르면
    로그와 예외 메시지에 섞여 나갈 경로가 생긴다.
    """
    proj = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not proj:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT 가 없다. 환경변수로 주거나 build_model(project=...) 로 넘긴다."
        )
    return ChatGoogleGenerativeAI(
        model=MODEL_ID,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        project=proj,
        location=location or os.environ.get("GOOGLE_CLOUD_LOCATION", DEFAULT_LOCATION),
        vertexai=True,
        # 타임아웃이 없으면 Gemini 가 응답하지 않을 때 invoke() 가 무한히
        # 기다린다. /ask 는 `def` 엔드포인트라 anyio 스레드풀 슬롯을 하나
        # 잡은 채로 매달리고, 그런 요청이 쌓이면 /healthz 를 포함한 **모든**
        # 엔드포인트가 응답을 멈춘다. 도구 호출 루프가 최대 MAX_TOOL_CALLS
        # 번 돌 수 있으므로 한 번의 상한을 넉넉히 잡되 유한하게 둔다.
        timeout=TIMEOUT_SECONDS,
        # 일시적인 429/503 을 재시도 없이 그대로 500 으로 내보내지 않는다.
        max_retries=2,
    )

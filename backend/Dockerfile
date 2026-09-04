# CPU 전용 torch 를 쓴다. 기본 wheel 은 CUDA 를 끌고 와 이미지가 몇 GB 더 커진다.
#
# 다이제스트로 핀한다. `python:3.12-slim` 은 움직이는 태그라, 같은 커밋을
# 다음 주에 빌드하면 다른 베이스 위에 올라간다 — uv.lock 을 고친 이유와
# 같다. 갱신은 의도적으로 한다:
#   docker pull python:3.12-slim && docker image inspect python:3.12-slim \
#     --format '{{index .RepoDigests 0}}'
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

WORKDIR /app

# 의존성을 먼저 설치해 레이어를 캐시한다 — 소스가 바뀌어도 재설치하지 않는다.
COPY requirements.txt .
RUN pip install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      -r requirements.txt

# 임베딩 모델을 빌드 시점에 받아 이미지에 굽는다. 런타임에 받으면
# 첫 요청이 다운로드까지 기다리고, 네트워크가 막히면 아예 못 뜬다.
ENV HF_HOME=/app/.hf
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('intfloat/multilingual-e5-small')"

# 루트로 돌리지 않는다. 이 컨테이너는 Cloudflare 터널로 공개되고, 같은
# 브리지에 남의 스택이 함께 있다(docker-compose.tunnel.yml 주석 참고).
# 뚫렸을 때 루트인 것과 아닌 것은 다르다.
#
# 모델 캐시를 먼저 굽고 나서 사용자를 만든다 — 순서를 바꾸면 캐시를 쓰는
# 레이어가 권한 때문에 실패한다.
RUN useradd --create-home --uid 10001 secuagent \
 && chown -R secuagent:secuagent /app

COPY core/ ./core/
COPY adapters/ ./adapters/
COPY pipeline/ ./pipeline/
COPY api/ ./api/
COPY demo/ ./demo/
COPY db/ ./db/

USER secuagent

EXPOSE 8080
CMD ["uvicorn", "api.deps:app", "--host", "0.0.0.0", "--port", "8080"]

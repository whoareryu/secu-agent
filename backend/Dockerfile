# CPU 전용 torch 를 쓴다. 기본 wheel 은 CUDA 를 끌고 와 이미지가 몇 GB 더 커진다.
FROM python:3.12-slim

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

COPY core/ ./core/
COPY adapters/ ./adapters/
COPY pipeline/ ./pipeline/
COPY api/ ./api/
COPY db/ ./db/

EXPOSE 8080
CMD ["uvicorn", "api.deps:app", "--host", "0.0.0.0", "--port", "8080"]

"""multilingual-e5-small 임베딩 어댑터.

이 모델을 고른 이유는 크기가 아니라 cross-lingual 이다 — 한국어 질의로
한국어 규정과 영문 로그를 같은 벡터 공간에서 검색한다(spec 2.5).

e5 계열은 "query: " / "passage: " 접두어를 요구한다. 접두어를 빼면 성능이
눈에 띄게 떨어지는데, 에러가 아니라 조용한 품질 저하라 발견이 늦다.
그래서 포트가 kind 를 필수 인자로 요구한다.
"""

from collections.abc import Sequence
from typing import Literal

from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-small"


class E5Embedder:
    def __init__(self, model_name: str = MODEL_NAME, device: str | None = None) -> None:
        self._model = SentenceTransformer(model_name, device=device)

    def encode(self, texts: Sequence[str], kind: Literal["query", "passage"]) -> list[list[float]]:
        if kind not in ("query", "passage"):
            raise ValueError(f"kind 는 query 또는 passage 여야 한다: {kind!r}")
        prefixed = [f"{kind}: {t}" for t in texts]
        vecs = self._model.encode(prefixed, normalize_embeddings=True)
        return [v.tolist() for v in vecs]

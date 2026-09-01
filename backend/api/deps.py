"""프로덕션 조립. 무거운 것을 한 번만 만든다.

임베딩 모델 로드가 수십 초 걸리므로 프로세스당 한 번만 한다.
에이전트는 요청마다 새로 만든다 — 도구가 클로저로 검색기를 닫고 있고,
그래프 조립 자체는 싸다.
"""

import os
from functools import lru_cache

from adapters.agent.runner import build_agent
from adapters.db.chunk_search import PgChunkSearch
from adapters.db.connection import connect
from adapters.db.principal_store import PgPrincipalStore
from adapters.embedding.e5 import E5Embedder
from adapters.llm.gemini import build_model
from api.main import build_app


@lru_cache(maxsize=1)
def _자원():
    conn = connect(os.environ.get("SECUAGENT_DSN"))
    embedder = E5Embedder()
    os.environ["SECUAGENT_MODEL_READY"] = "ready"
    return conn, embedder


def create_app():
    conn, embedder = _자원()
    searcher = PgChunkSearch(conn)
    저장소 = PgPrincipalStore(conn)

    def 에이전트_공장():
        return build_agent(embedder, searcher, build_model())

    return build_app(에이전트_공장, 저장소)


app = create_app()

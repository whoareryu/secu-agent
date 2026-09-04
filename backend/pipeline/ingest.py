"""문서 적재 오케스트레이션.

이 모듈은 core/ports 의 포트만 안다. psycopg 도 sentence-transformers 도
pypdf 도 모른다 — 그래서 테스트가 DB 없이, 모델 로드 없이 스텁으로 돈다.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from core.ports import DocumentStore, Embedder
from core.types import Chunk, Clause, Document

Loader = Callable[[Path], tuple[list[Clause], list[Chunk]]]

DEFAULT_BATCH = 64


@dataclass(frozen=True)
class IngestReport:
    clauses: int
    chunks: int


def _배치(items: Sequence[Chunk], size: int):
    if size <= 0:
        # range(0, n, 0) 은 "range() arg 3 must not be zero" 만 말한다.
        # batch_size 는 ingest() 의 공개 인자라 여기서 이름을 밝힌다.
        raise ValueError(f"batch_size 는 양수여야 한다: {size}")
    for i in range(0, len(items), size):
        yield items[i : i + size]


def ingest(
    path: Path,
    doc: Document,
    loader: Loader,
    embedder: Embedder,
    store: DocumentStore,
    batch_size: int = DEFAULT_BATCH,
) -> IngestReport:
    """문서를 파싱해 조항·청크·벡터를 저장한다.

    임베딩을 배치로 나누는 이유: 255쪽 문서는 청크가 수천 개가 되고,
    한 번에 넘기면 메모리가 터진다.
    """
    clauses, chunks = loader(path)

    document_id = store.upsert_document(doc)
    # 배치 루프 **밖**이다. insert_chunks 안에 두면 두 번째 배치가 첫 번째
    # 배치를 지운다 — 314청크짜리 ISMS-P 가 마지막 배치만 남는다.
    store.delete_chunks(document_id)
    clause_ids = store.insert_clauses(document_id, clauses) if clauses else {}

    if not chunks:
        return IngestReport(clauses=len(clauses), chunks=0)

    저장수 = 0
    for batch in _배치(chunks, batch_size):
        # 문서 쪽은 passage 다. query 를 쓰면 검색 품질이 조용히 나빠진다.
        vectors = embedder.encode([c.text for c in batch], kind="passage")
        저장수 += store.insert_chunks(document_id, clause_ids, batch, vectors)

    return IngestReport(clauses=len(clauses), chunks=저장수)

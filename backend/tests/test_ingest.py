from pathlib import Path

from core.types import EMBEDDING_DIM, Chunk, Clause, Document
from pipeline.ingest import IngestReport, ingest


class 스텁임베더:
    """호출 인자를 기록한다 — passage 접두어를 쓰는지 확인하기 위해서다."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    def encode(self, texts, kind):
        self.calls.append((len(texts), kind))
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class 메모리저장소:
    def __init__(self) -> None:
        self.docs: list[Document] = []
        self.clauses: list[Clause] = []
        self.chunks: list[Chunk] = []
        self.vectors: list[list[float]] = []

    def upsert_document(self, doc):
        self.docs.append(doc)
        return len(self.docs)

    def insert_clauses(self, document_id, clauses):
        self.clauses.extend(clauses)
        return {c.code: i for i, c in enumerate(clauses, start=1)}

    def insert_chunks(self, document_id, clause_ids, chunks, vectors):
        self.chunks.extend(chunks)
        self.vectors.extend(vectors)
        return len(chunks)

    def count_chunks(self):
        return len(self.chunks)


def _로더(path: Path):
    return (
        [Clause(code="1.1.1", title="가", text="본문 가"),
         Clause(code="2.6.1", title="나", text="본문 나")],
        [Chunk(clause_code="1.1.1", ordinal=0, text="청크 1"),
         Chunk(clause_code="2.6.1", ordinal=0, text="청크 2")],
    )


def _문서() -> Document:
    return Document(
        id=0, title="테스트", source_path="a.pdf", doc_type="pdf",
        required_clearance=1, allowed_departments=(),
    )


def test_조항과_청크를_적재한다():
    e, s = 스텁임베더(), 메모리저장소()
    report = ingest(Path("a.pdf"), _문서(), _로더, e, s)
    assert isinstance(report, IngestReport)
    assert report.clauses == 2
    assert report.chunks == 2


def test_임베딩은_passage_접두어로_한다():
    # e5 계열은 문서를 passage:, 질의를 query: 로 넣어야 한다.
    # 여기서 query 를 쓰면 검색 품질이 조용히 나빠진다.
    e, s = 스텁임베더(), 메모리저장소()
    ingest(Path("a.pdf"), _문서(), _로더, e, s)
    assert all(kind == "passage" for _, kind in e.calls)


def test_청크와_벡터의_수가_같다():
    e, s = 스텁임베더(), 메모리저장소()
    ingest(Path("a.pdf"), _문서(), _로더, e, s)
    assert len(s.chunks) == len(s.vectors)


def test_청크가_없으면_임베더를_부르지_않는다():
    # 빈 리스트로 API 를 호출하면 비용만 든다.
    def 빈로더(path):
        return [], []

    e, s = 스텁임베더(), 메모리저장소()
    report = ingest(Path("a.pdf"), _문서(), 빈로더, e, s)
    assert report.chunks == 0
    assert e.calls == []


def test_대량_청크는_배치로_임베딩한다():
    # 3천 개를 한 번에 넘기면 메모리가 터진다.
    def 큰로더(path):
        return [], [Chunk(clause_code=None, ordinal=i, text=f"청크 {i}") for i in range(250)]

    e, s = 스텁임베더(), 메모리저장소()
    ingest(Path("a.pdf"), _문서(), 큰로더, e, s, batch_size=64)
    assert len(e.calls) == 4          # 64 · 64 · 64 · 58
    assert all(n <= 64 for n, _ in e.calls)
    assert sum(n for n, _ in e.calls) == 250

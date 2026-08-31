import dataclasses

import pytest

from core.ports import ChunkSearch, DocumentStore, Embedder
from core.types import EMBEDDING_DIM, Chunk, Clause, Document, PolicyHit, Principal


def test_임베딩_차원이_384_다():
    # multilingual-e5-small 의 차원. db/schema.sql 의 vector(N) 과 일치해야 한다.
    assert EMBEDDING_DIM == 384


def test_주체는_부서와_등급을_갖고_불변이다():
    p = Principal(department="보안팀", clearance=2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.clearance = 3


def test_문서의_허용부서가_비면_전사_공개다():
    d = Document(
        id=1,
        title="ISMS-P 인증기준 안내서",
        source_path="data/raw/ismsp.pdf",
        doc_type="pdf",
        required_clearance=1,
        allowed_departments=(),
    )
    assert d.allowed_departments == ()


def test_조항은_코드와_제목과_본문을_갖는다():
    c = Clause(code="2.6.1", title="네트워크 접근", text="네트워크에 대한 비인가 접근을...")
    assert c.code == "2.6.1"
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.code = "x"


def test_청크는_조항_코드를_들고_다닌다():
    # 조항 코드가 없으면 리포트에서 "규정 2.6.1 위반"이라고 못 쓴다.
    ch = Chunk(clause_code="2.6.1", ordinal=0, text="본문 일부")
    assert ch.clause_code == "2.6.1"


def test_조항에_속하지_않는_청크도_허용된다():
    # 표지·목차처럼 조항 밖 텍스트가 있다.
    ch = Chunk(clause_code=None, ordinal=0, text="목차")
    assert ch.clause_code is None


def test_검색_결과는_조항_코드를_들고_다닌다():
    # 조항 코드가 없으면 리포트에서 "규정 2.6.1 위반"이라고 못 쓴다.
    h = PolicyHit(
        chunk_id=1,
        text="본문",
        doc_title="ISMS-P",
        clause_code="2.6.1",
        required_clearance=1,
        allowed_departments=(),
    )
    assert h.clause_code == "2.6.1"
    with pytest.raises(dataclasses.FrozenInstanceError):
        h.text = "x"


def test_조항_밖_결과는_코드가_None_이다():
    h = PolicyHit(
        chunk_id=1,
        text="목차",
        doc_title="ISMS-P",
        clause_code=None,
        required_clearance=1,
        allowed_departments=(),
    )
    assert h.clause_code is None


def test_포트를_스텁이_만족한다():
    class 임베더:
        def encode(self, texts, kind):
            return [[0.0] * EMBEDDING_DIM for _ in texts]

    class 저장소:
        def upsert_document(self, doc):
            return 1

        def insert_clauses(self, document_id, clauses):
            return {c.code: i for i, c in enumerate(clauses, start=1)}

        def insert_chunks(self, document_id, clause_ids, chunks, vectors):
            return len(chunks)

        def delete_chunks(self, document_id):
            return 0

        def count_all_chunks(self):
            return 0

    class 검색기:
        def by_vector(self, vec, p, k):
            return []

        def by_keyword(self, q, p, k):
            return []

    assert isinstance(임베더(), Embedder)
    assert isinstance(저장소(), DocumentStore)
    assert isinstance(검색기(), ChunkSearch)


def test_포트를_만족하지_않으면_False_다():
    class 빈것:
        pass

    assert not isinstance(빈것(), Embedder)
    assert not isinstance(빈것(), DocumentStore)
    assert not isinstance(빈것(), ChunkSearch)

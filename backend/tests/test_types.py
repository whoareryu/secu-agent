import dataclasses

import pytest

from core.ports import (
    AccessLog,
    ChunkSearch,
    DocumentCatalog,
    DocumentStore,
    Embedder,
    HostStore,
    LogSearch,
    PrincipalStore,
)
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

        def load_hits(self, ids, principal):
            return []

    class 주체저장소:
        def find(self, name):
            return None

    class 열람기록:
        def record(self, rows):
            return len(rows)

        def recent(self, limit):
            return []

        def violations(self, limit):
            return []

    class 카탈로그:
        def documents(self):
            return []

        def principals(self):
            return []

    class 로그검색기:
        def query(self, principal, event_type, since, limit):
            return []

    class 호스트저장소:
        def upsert(self, host):
            return None

        def names(self):
            return set()

    assert isinstance(임베더(), Embedder)
    assert isinstance(저장소(), DocumentStore)
    assert isinstance(검색기(), ChunkSearch)
    assert isinstance(주체저장소(), PrincipalStore)
    assert isinstance(열람기록(), AccessLog)
    assert isinstance(카탈로그(), DocumentCatalog)
    assert isinstance(로그검색기(), LogSearch)
    assert isinstance(호스트저장소(), HostStore)


def test_포트를_만족하지_않으면_False_다():
    class 빈것:
        pass

    assert not isinstance(빈것(), Embedder)
    assert not isinstance(빈것(), DocumentStore)
    assert not isinstance(빈것(), ChunkSearch)


def test_LogEvent_가_호스트_권한을_들고_다닌다():
    """PolicyHit 와 같은 이유다 — 재검증이 DB 를 다시 부르면 그건 검증이
    아니라 같은 코드를 두 번 믿는 것이다(core/access/visibility.py 독스트링).
    """
    from core.types import LogEvent

    e = LogEvent(
        id=1,
        ts=None,
        host="dev-web-01",
        process="sshd",
        event_type="auth_failure",
        principal_name="admin",
        raw="...",
        severity=None,
        required_clearance=2,
        allowed_departments=("개발팀",),
    )
    assert e.required_clearance == 2
    assert e.allowed_departments == ("개발팀",)


def test_LogEvent_에는_기본값이_없다():
    """권한 필드에 기본값을 주면 그것을 빠뜨린 생성이 조용히 통과한다.
    PolicyHit 이 같은 이유로 기본값을 갖지 않는다.
    """
    import dataclasses

    from core.types import LogEvent

    권한_필드 = [
        f
        for f in dataclasses.fields(LogEvent)
        if f.name in ("required_clearance", "allowed_departments")
    ]
    assert len(권한_필드) == 2
    for f in 권한_필드:
        assert f.default is dataclasses.MISSING, f"{f.name} 에 기본값이 있다"


def test_Host_가_documents_와_같은_권한_컬럼을_갖는다():
    """스펙 결정 13 — 같은 규칙의 네 벌째 사본을 만들지 않기 위해
    visibility.visible() 을 그대로 재사용한다. 필드 이름이 같아야 한다.
    """
    import dataclasses

    from core.types import Document, Host

    문서_권한 = {f.name for f in dataclasses.fields(Document)} & {
        "required_clearance",
        "allowed_departments",
    }
    호스트_권한 = {f.name for f in dataclasses.fields(Host)} & {
        "required_clearance",
        "allowed_departments",
    }
    assert 문서_권한 == 호스트_권한 == {"required_clearance", "allowed_departments"}


def test_visible_이_Host_에도_그대로_쓰인다():
    from core.access.visibility import visible
    from core.types import Host, Principal

    h = Host(
        name="hr-app-01", department="인사팀", required_clearance=2, allowed_departments=("인사팀",)
    )
    개발자 = Principal(department="개발팀", clearance=3)
    인사팀장 = Principal(department="인사팀", clearance=2)

    assert not visible(h.required_clearance, h.allowed_departments, 개발자)
    assert visible(h.required_clearance, h.allowed_departments, 인사팀장)


def test_principal_의_기본_역할은_일반_사용자다():
    """역할을 빠뜨린 생성이 조용히 감사가 되면 안 된다 — 닫히는 방향이 기본값이다.

    기존 호출부(pipeline/cli.py · api/demo.py)가 role 없이 Principal 을
    만들므로 기본값이 필요하다.
    """
    p = Principal(department="개발팀", clearance=1)
    assert p.role == "member"


def test_역할은_권한_판정에_쓰이지_않는다():
    """역할이 다르다고 보이는 문서가 달라지면 안 된다(스펙 §2.1).

    가시성은 등급·부서만 본다. 이 테스트가 실패하면 visible() 이 role 을
    보기 시작한 것이고, 그건 이 설계가 명시적으로 금지한 일이다.
    """
    from core.access.visibility import visible

    사원 = Principal(department="개발팀", clearance=1, role="member")
    감사 = Principal(department="개발팀", clearance=1, role="auditor")
    for 등급 in (1, 2, 3):
        for 부서 in ((), ("개발팀",), ("인사팀",)):
            assert visible(등급, 부서, 사원) == visible(등급, 부서, 감사)

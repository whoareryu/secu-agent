"""실제 DB 로 하이브리드 검색을 확인한다.

docker compose up -d
.venv/bin/python -m pytest -m db -v
"""

import os

import pytest

from adapters.db.chunk_search import _벡터_SQL, PgChunkSearch
from adapters.db.connection import apply_schema, connect
from adapters.db.document_store import PgDocumentStore
from core.ports import ChunkSearch
from core.retrieve.hybrid import search
from core.types import EMBEDDING_DIM, Chunk, Clause, Document, PolicyHit, Principal

pytestmark = pytest.mark.db

DSN = os.environ.get("SECUAGENT_DSN", "postgresql://secuagent:secuagent@localhost:5433/secuagent")
사원 = Principal(department="개발팀", clearance=1)

# [0.1]*N 과 [0.9]*N 은 스칼라배라 vector_cosine_ops 아래서 프로브와 코사인
# 거리 0(완전히 같은 방향)이다 — 순위를 구분하지 못한다. 프로브와 내적이
# 0이 되도록 부호를 번갈아 채운 벡터는 코사인 거리 1(직교)이라 "진짜 먼"
# 청크를 만든다. 짝수 차원이라 +1 과 -1 의 개수가 같아 내적이 정확히 0이다.
_직교_벡터 = [1.0 if i % 2 == 0 else -1.0 for i in range(EMBEDDING_DIM)]


class 고정임베더:
    """항상 같은 벡터를 준다 — 벡터 검색이 도는지만 본다."""

    def encode(self, texts, kind):
        return [[0.1] * EMBEDDING_DIM for _ in texts]


def _텍스트로_id(conn, 부분문자열: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM chunks WHERE text LIKE %s", (f"%{부분문자열}%",))
        row = cur.fetchone()
        assert row, f"'{부분문자열}' 을 포함한 청크를 찾을 수 없다"
        return row[0]


@pytest.fixture
def db():
    conn = connect(DSN)
    apply_schema(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE documents RESTART IDENTITY CASCADE")
    conn.commit()

    store = PgDocumentStore(conn)
    doc_id = store.upsert_document(
        Document(
            id=0,
            title="ISMS-P",
            source_path="a.pdf",
            doc_type="pdf",
            required_clearance=1,
            allowed_departments=(),
        )
    )
    ids = store.insert_clauses(
        doc_id,
        [
            Clause(code="2.6.1", title="네트워크 접근", text="네트워크 접근 통제"),
            Clause(code="2.5.1", title="사용자 계정 관리", text="계정 발급과 관리"),
        ],
    )
    store.insert_chunks(
        doc_id,
        ids,
        [
            Chunk(clause_code="2.6.1", ordinal=0, text="네트워크에 대한 비인가 접근을 통제한다"),
            Chunk(clause_code="2.5.1", ordinal=0, text="사용자 계정 발급 절차를 수립한다"),
            # 프로브와 직교(코사인 거리 1) — 벡터 검색에서는 항상 꼴찌지만
            # "백업" 이라는 낱말은 이 청크에만 있어 키워드 검색은 바로 찾는다.
            Chunk(
                clause_code=None, ordinal=1, text="정기적으로 시스템을 백업하고 보관 이력을 남긴다"
            ),
        ],
        [[0.1] * EMBEDDING_DIM, [0.9] * EMBEDDING_DIM, _직교_벡터],
    )

    # 등급 3(임원) 전용 문서 — required_clearance 축을 검사할 때 쓴다.
    임원_doc = store.upsert_document(
        Document(
            id=0,
            title="임원 전용 지침",
            source_path="exec.pdf",
            doc_type="pdf",
            required_clearance=3,
            allowed_departments=(),
        )
    )
    임원_clause = store.insert_clauses(
        임원_doc, [Clause(code="9.9.9", title="임원 전용", text="임원 전용 조항")]
    )
    store.insert_chunks(
        임원_doc,
        임원_clause,
        [Chunk(clause_code="9.9.9", ordinal=0, text="임원전용 보안 정책 요약")],
        [[0.5] * EMBEDDING_DIM],
    )

    # 인사팀에만 공개된 문서 — allowed_departments 축을 검사할 때 쓴다.
    인사_doc = store.upsert_document(
        Document(
            id=0,
            title="인사팀 내규",
            source_path="hr.pdf",
            doc_type="pdf",
            required_clearance=1,
            allowed_departments=("인사팀",),
        )
    )
    인사_clause = store.insert_clauses(
        인사_doc, [Clause(code="8.8.8", title="인사 정책", text="인사 정책 조항")]
    )
    store.insert_chunks(
        인사_doc,
        인사_clause,
        [Chunk(clause_code="8.8.8", ordinal=0, text="인사정책 상세 안내")],
        [[0.5] * EMBEDDING_DIM],
    )

    yield conn, PgChunkSearch(conn)
    conn.close()


def test_구현이_포트를_만족한다(db):
    _, searcher = db
    assert isinstance(searcher, ChunkSearch)


def test_벡터_검색이_결과를_돌려준다(db):
    _, searcher = db
    # 사원(개발팀, 등급1)에게 보이는 청크는 기본 문서의 3건뿐이다 —
    # 임원 전용(등급3)·인사팀 전용 문서는 권한 밖이다.
    assert len(searcher.by_vector([0.1] * EMBEDDING_DIM, 사원, k=10)) == 3


def test_벡터_검색이_가까운_청크를_먼저_돌려준다(db):
    """진짜 순위 단언 — 지금까지는 아무 테스트도 이걸 확인하지 않았다.

    "백업" 청크는 프로브와 직교(코사인 거리 1)라 항상 꼴찌여야 한다.
    "네트워크" 청크는 프로브와 같은 방향(코사인 거리 0)이라 항상 먼저 와야
    한다. `<=>` 를 `<->` 로 잘못 쓰거나 ORDER BY 를 DESC 로 뒤집으면 이
    단언이 깨진다.
    """
    conn, searcher = db
    가까운 = _텍스트로_id(conn, "네트워크")
    먼 = _텍스트로_id(conn, "백업")
    ids = searcher.by_vector([0.1] * EMBEDDING_DIM, 사원, k=10)
    assert ids.index(가까운) < ids.index(먼)


def test_벡터_검색은_고등급_문서와_타부서_문서를_배제한다(db):
    conn, searcher = db
    임원_id = _텍스트로_id(conn, "임원전용")
    인사_id = _텍스트로_id(conn, "인사정책")
    ids = searcher.by_vector([0.1] * EMBEDDING_DIM, 사원, k=10)
    assert 임원_id not in ids, "등급1 사원에게 등급3 문서의 청크가 보인다"
    assert 인사_id not in ids, "개발팀 사원에게 인사팀 전용 청크가 보인다"


def test_키워드_검색은_고등급_문서와_타부서_문서를_배제한다(db):
    conn, searcher = db
    임원_id = _텍스트로_id(conn, "임원전용")
    인사_id = _텍스트로_id(conn, "인사정책")
    assert 임원_id not in searcher.by_keyword("임원전용", 사원, k=10), (
        "등급1 사원에게 등급3 문서의 청크가 보인다"
    )
    assert 인사_id not in searcher.by_keyword("인사정책", 사원, k=10), (
        "개발팀 사원에게 인사팀 전용 청크가 보인다"
    )


def test_권한_필터가_순위보다_먼저_적용된다(db):
    """실행 계획을 직접 본다. 결과 개수로는 이걸 확인할 수 없다.

    처음에는 "권한 밖 문서를 가까이 심어두고 k 가 채워지는지" 로 쓰려 했다.
    실측해 보니 그 단언은 **흔들린다** — 문서당 500·2000 청크에서는 누출이
    재현되는데 50·200·1000 에서는 재현되지 않았다. HNSW 그래프가 삽입 순서와
    난수에 따라 달라지기 때문이다. `hnsw.ef_search` 를 1 까지 낮춰도 작은
    픽스처에서는 재현되지 않았다.

    흔들리는 보안 테스트는 결국 꺼진다. 그래서 증상 대신 **구조**를 단언한다:
    권한 통과 집합이 CTE 로 먼저 확정되고, 정렬이 그 CTE 위에서 일어나야 한다.
    이건 코퍼스 크기와 무관하게 참이거나 거짓이다.

    `AS MATERIALIZED` 를 지우면 플래너가 CTE 를 인라인해서 이 노드가 사라지고
    테스트가 실패한다.
    """
    conn, _ = db
    with conn.cursor() as cur:
        cur.execute(
            "EXPLAIN " + _벡터_SQL,
            {
                "clearance": 사원.clearance,
                "dept": 사원.department,
                "qvec": str([0.1] * EMBEDDING_DIM),
                "k": 10,
            },
        )
        계획 = "\n".join(row[0] for row in cur.fetchall())

    assert "CTE 허용" in 계획, (
        "권한 통과 집합이 CTE 로 확정되지 않는다. AS MATERIALIZED 가 빠졌거나 "
        f"플래너가 인라인했다. 사후 필터링이 되어 존재가 새어나간다(spec 5.3).\n{계획}"
    )
    assert "CTE Scan" in 계획, (
        f"정렬이 CTE 위에서 일어나지 않는다 — 순위가 권한보다 먼저 매겨진다.\n{계획}"
    )


def test_키워드_검색이_본문에_있는_말을_찾는다(db):
    _, searcher = db
    hits = searcher.by_keyword("네트워크", 사원, k=10)
    assert len(hits) == 1


def test_본문에_없는_말은_키워드_검색에서_0건이다(db):
    _, searcher = db
    assert searcher.by_keyword("존재하지않는단어", 사원, k=10) == []


def test_하이브리드_검색이_두_경로를_모두_쓴다(db):
    """벡터 단독으로는 등수 밖으로 밀리는 청크가 키워드 경로 덕에 들어온다.

    "백업" 청크는 고정임베더의 프로브와 직교(코사인 거리 1)라 벡터 검색에서
    항상 꼴찌다. 반면 낱말 "백업"은 이 청크에만 있다. k=2 로 좁히면:

    · 벡터 단독 top-2 는 [네트워크 청크, 계정 청크] — 백업 청크는 밀려난다.
    · 키워드 경로는 백업 청크 하나만, 1위로 돌려준다.
    · RRF 융합 점수는 백업 청크(벡터 3위 + 키워드 1위)가 계정 청크(벡터
      2위, 키워드 无) 를 앞질러 top-2 에 백업 청크가 들어오고 계정 청크가
      밀려난다.

    이 결과는 두 경로가 실제로 다 쓰여야만 나온다 — 벡터만 썼다면 계정
    청크가 그대로 남고 백업 청크는 나타나지 않는다.
    """
    conn, searcher = db
    hits = search("백업", 사원, 고정임베더(), searcher, k=2)
    assert len(hits) == 2

    백업_id = _텍스트로_id(conn, "백업")
    계정_id = _텍스트로_id(conn, "계정")
    assert 백업_id in hits, "키워드 전용 청크가 융합 결과에 없다 — 키워드 경로가 기여하지 않는다"
    assert 계정_id not in hits, (
        "벡터만 썼다면 top-2 에 남았을 청크가 그대로 있다 — 키워드 경로가 무시된다"
    )


def test_조항_코드까지_불러온다(db):
    _, searcher = db
    hits = search("네트워크", 사원, 고정임베더(), searcher, k=10)
    rows = searcher.load_hits(hits, 사원)
    assert all(isinstance(r, PolicyHit) for r in rows)
    assert {"2.6.1", "2.5.1"}.issubset({r.clause_code for r in rows})


def test_load_hits_는_권한_밖_청크의_본문을_주지_않는다(db):
    """검색을 막아도 여기가 뚫리면 소용없다.

    load_hits 는 청크 **본문**을 돌려준다. 권한 검사를 검색 쪽에만 두면
    id 를 아는 호출자가 이 경로로 본문을 그대로 가져간다. 존재 누출보다
    나쁜 내용 누출이다.

    권한 밖 id 는 조용히 빠져야 한다. 예외를 던지면 "그 id 는 접근 불가"
    라는 응답 자체가 존재 확인이 된다.
    """
    conn, searcher = db
    store = PgDocumentStore(conn)
    기밀 = store.upsert_document(
        Document(
            id=0,
            title="3급 기밀",
            source_path="secret.pdf",
            doc_type="pdf",
            required_clearance=3,
            allowed_departments=(),
        )
    )
    store.insert_chunks(
        기밀,
        {},
        [Chunk(clause_code=None, ordinal=0, text="대외비: 마스터 키")],
        [[0.5] * EMBEDDING_DIM],
    )
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM chunks")
        전체 = [r[0] for r in cur.fetchall()]

    받은 = searcher.load_hits(전체, 사원)

    assert all("대외비" not in r.text for r in 받은), (
        "등급 1 사원이 3급 기밀 청크의 본문을 받았다. load_hits 에 권한 필터가 없다."
    )
    assert len(받은) < len(전체), "권한 밖 청크가 걸러지지 않았다"


def test_load_hits_가_준_순서를_지킨다(db):
    # SQL 반환 순서에 기대면 융합 결과의 순위가 뒤집힌다.
    _, searcher = db
    ids = searcher.by_vector([0.1] * EMBEDDING_DIM, 사원, k=10)
    rows = searcher.load_hits(list(reversed(ids)), 사원)
    assert [r.chunk_id for r in rows] == list(reversed(ids))

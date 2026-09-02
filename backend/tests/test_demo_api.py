"""데모 비교 API.

**본문을 돌려주지 않는다.** 누출을 보여주는 데 본문이 필요 없다 —
개수와 조항 코드면 개수 채널과 순위 채널이 둘 다 보인다. 시연을 위해서라도
본문이 이 경로로 나가지 않는다는 불변식은 깨지 않는다(보충 spec 결정 18).

시딩은 tests/test_naive_leaks.py 의 좌표 블록 방식을 따른다(난수 단위벡터
금지 — 384차원에서 cos 0.1 이 나온다). 다만 이 파일은 사전·사후 개수
차이가 아니라 API 계약(개수·이름·본문 부재)을 본다 — 그래서 페르소나
셋이 전부 같은 전사공개 문서 하나를 보는 단순한 배치로 충분하다.

문서당 청크 수는 test_naive_leaks.py 의 논거를 그대로 따른다: 사전
필터링이 k(=10) 건을 채우려면 그 문서의 청크 수가 최소 k 이상이어야
한다는 것이 구조적 하한이다(`test_사전_필터링_개수가_k_로_고정된다`).
그 경계에 바로 붙이지 않고 2배인 20 을 골랐다 — 그 파일과 같은 이유로,
k 를 조금 올리는 미래 변경에도 이 파일이 구조적으로 깨지지 않을 여유를
두기 위해서다.
"""

import random

import pytest
from fastapi.testclient import TestClient

from adapters.db.chunk_search import PgChunkSearch
from adapters.db.principal_store import PgPrincipalStore
from api.demo import build_demo_router
from api.main import build_app
from core.types import EMBEDDING_DIM, Principal

pytestmark = pytest.mark.db

시크릿 = "demo-test-secret"
_시크릿 = {"X-Backend-Secret": 시크릿}

절반 = EMBEDDING_DIM // 2
# 기밀축을 정확히 가리키는 질의 벡터. "제1조" 청크를 이 값과 정확히
# 일치시켜 코사인 거리 0 을 만든다 — 다른 청크는 지터가 섞여 있어
# 이 청크가 항상 상위 k 안에 들어온다(비공허성 가드가 이것을 검사한다).
질의_벡터 = [1.0] * 절반 + [0.0] * 절반

문서당_청크 = 20


def _지터_벡터(rng: random.Random) -> str:
    앞 = [1.0 + rng.uniform(0, 0.1) for _ in range(절반)]
    뒤 = [0.0 for _ in range(절반)]
    return str(앞 + 뒤)


class _질의_임베더:
    """실제 e5 모델 대신 고정 벡터를 낸다 — 이 파일은 임베딩 품질이 아니라
    API 계약을 본다."""

    def encode(self, texts, kind):
        return [질의_벡터 for _ in texts]


@pytest.fixture
def _코퍼스(db연결):
    """전사공개 문서 하나에 청크 20개. 세 페르소나 모두 이 문서를 본다.

    0번 청크에 "제1조" 를 넣고 질의 벡터와 정확히 일치시킨다 —
    `test_응답에_본문이_없다` 가 공허하게 통과하지 않으려면 실제로 상위
    k 에 드는 "제1조" 문장이 코퍼스에 있어야 한다(보충 spec 결정 4).
    """
    conn = db연결
    with conn.cursor() as cur:
        cur.execute("TRUNCATE documents RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE principals RESTART IDENTITY CASCADE")

        cur.execute(
            "INSERT INTO documents (title, source_path, doc_type, "
            "required_clearance, allowed_departments) "
            "VALUES (%s, %s, 'md', %s, %s) RETURNING id",
            ("공개 규정", "demo-pub.md", 1, None),
        )
        문서_id = cur.fetchone()[0]

        삽입 = (
            "INSERT INTO chunks (document_id, clause_id, ordinal, text, embedding, text_tsv) "
            "VALUES (%s, NULL, %s, %s, %s, to_tsvector('simple', %s))"
        )
        cur.execute(
            삽입,
            (문서_id, 0, "제1조 비밀번호는 12자 이상이어야 한다", str(질의_벡터), "제1조"),
        )
        rng = random.Random(11)
        cur.executemany(
            삽입,
            [
                (문서_id, i, f"공개조항 {i}", _지터_벡터(rng), f"공개조항 {i}")
                for i in range(1, 문서당_청크)
            ],
        )

        cur.executemany(
            "INSERT INTO principals (name, department, clearance) VALUES (%s, %s, %s)",
            [
                ("김개발", "개발팀", 1),
                ("박인사", "인사팀", 2),
                ("최임원", "경영지원팀", 3),
            ],
        )
    conn.commit()
    yield conn


@pytest.fixture
def demo_client(monkeypatch, _코퍼스):
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)
    conn = _코퍼스
    저장소 = PgPrincipalStore(conn)
    데모_라우터 = build_demo_router(lambda: (conn, _질의_임베더()), 저장소)

    def _에이전트_공장():
        raise AssertionError("/demo/compare 는 /ask 의 에이전트를 쓰지 않는다")

    return TestClient(build_app(_에이전트_공장, 저장소, 데모_라우터=데모_라우터))


@pytest.fixture
def demo_client_모델_없음(monkeypatch, _코퍼스):
    """모델 자격증명이 없는 상태를 흉내낸다.

    에이전트 공장이 실제로 모델을 못 찾아 죽는 것처럼 만든다 — 이 경로가
    무료라는 주장은 "안 부른다"가 구조로 보장돼야 참이다.
    """
    monkeypatch.setenv("BACKEND_SHARED_SECRET", 시크릿)
    conn = _코퍼스
    저장소 = PgPrincipalStore(conn)
    데모_라우터 = build_demo_router(lambda: (conn, _질의_임베더()), 저장소)

    def _모델_없음_공장():
        raise RuntimeError("GEMINI_API_KEY 가 없다")

    return TestClient(build_app(_모델_없음_공장, 저장소, 데모_라우터=데모_라우터))


def test_코퍼스에_검사할_문장이_있다(_코퍼스):
    """`test_응답에_본문이_없다` 가 공허하게 통과하지 않는지 보장하는 가드.

    시딩 청크 중 "제1조" 를 담은 것이 실제로 사전 필터링 상위 k 에
    든다 — 아니면 구현이 본문을 통째로 흘려도 그 테스트는 잡지 못한다.
    """
    conn = _코퍼스
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM chunks WHERE text LIKE %s", ("%제1조%",))
        (제1조_id,) = cur.fetchone()
    검색 = PgChunkSearch(conn)
    상위 = 검색.by_vector(질의_벡터, Principal("개발팀", 1), 10)
    assert 제1조_id in 상위


def test_응답에_본문이_없다(demo_client):
    r = demo_client.post("/demo/compare", json={"query": "비밀번호", "k": 10}, headers=_시크릿)
    본문 = r.text
    assert "text" not in r.json()["personas"][0]["prefiltered"]
    # 실제 청크 본문의 한 조각이 응답 어디에도 없어야 한다
    assert "제1조" not in 본문


def test_세_페르소나가_모두_나온다(demo_client):
    r = demo_client.post("/demo/compare", json={"query": "비밀번호", "k": 10}, headers=_시크릿)
    이름 = [p["name"] for p in r.json()["personas"]]
    assert 이름 == ["김개발", "박인사", "최임원"]


def test_사전_필터링_개수가_k_로_고정된다(demo_client):
    r = demo_client.post("/demo/compare", json={"query": "비밀번호", "k": 10}, headers=_시크릿)
    assert all(p["prefiltered"]["count"] == 10 for p in r.json()["personas"])


def test_k_에_상한이_있다(demo_client):
    """모델이 부르는 경로는 아니지만 브라우저가 부른다 — 값을 믿지 않는다."""
    r = demo_client.post("/demo/compare", json={"query": "비밀번호", "k": 9999}, headers=_시크릿)
    assert r.json()["k"] <= 20
    assert all(p["prefiltered"]["count"] <= 20 for p in r.json()["personas"])


def test_LLM_을_부르지_않는다(demo_client_모델_없음):
    """모델 자격증명이 아예 없어도 200 이어야 한다.

    이 경로가 무료라는 주장이 참인지를 구조로 확인한다.
    """
    r = demo_client_모델_없음.post(
        "/demo/compare", json={"query": "비밀번호", "k": 10}, headers=_시크릿
    )
    assert r.status_code == 200


def test_시크릿_없이는_401(demo_client):
    r = demo_client.post("/demo/compare", json={"query": "비밀번호", "k": 10})
    assert r.status_code == 401

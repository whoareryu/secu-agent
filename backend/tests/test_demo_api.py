"""데모 비교 API.

**본문을 돌려주지 않는다.** 누출을 보여주는 데 본문이 필요 없다 —
개수와 조항 코드면 개수 채널과 순위 채널이 둘 다 보인다. 시연을 위해서라도
본문이 이 경로로 나가지 않는다는 불변식은 깨지 않는다(보충 spec 결정 18).

시딩은 tests/test_naive_leaks.py 의 좌표 블록 방식을 따른다(난수 단위벡터
금지 — 384차원에서 cos 0.1 이 나온다). 이 파일은 그 파일과 달리 "개수 차이가
존재한다"만이 아니라 API 계약(개수·이름·조항 코드·본문 부재) 전부를 봐야
하므로 문서를 두 개 둔다:

- 공개 규정(등급1, 전사공개): 세 페르소나가 전부 본다.
- 임원 전용 규정(등급3): 최임원만 본다. 청크를 질의 축에 딱 붙여 심어서
  시스템 전체 최근접 상위권을 이 문서가 차지하게 만든다 — 순진한 경로가
  사후에 그것을 걸러내면서 낮은 등급 페르소나의 naive 개수가 prefiltered
  보다 줄어드는 것을 실제로 관측 가능하게 만든다. (리뷰 지적 Important 1:
  이전 버전은 문서가 하나뿐이라 naive 와 prefiltered 가 구조적으로 같은
  값이 될 수밖에 없었고, 그것을 검사하는 테스트도 없었다.)

공개 문서의 청크 수(30)는 두 하한을 동시에 만족해야 한다: (1) 사전
필터링이 k(=10) 를 채우려면 페르소나가 보는 풀이 최소 k 이상이어야 한다는
구조적 하한(test_naive_leaks.py 와 같은 논거, `test_사전_필터링_개수가_k_로_
고정된다`), (2) k 상한 clamp(=20) 를 실제로 검증하려면 풀이 20 보다
커야 한다 — 그렇지 않으면 "count <= 20" 이 clamp 가 없어도 코퍼스 크기
때문에 우연히 참이 된다(리뷰 지적 Minor 3). 두 하한 중 더 큰 쪽(20)에
10 을 더해 30 을 골랐다 — k 를 조금 올리는 미래 변경에도 이 파일이
구조적으로 깨지지 않을 여유를 두기 위해서다. 임원 전용 문서의 청크 수
(15)에는 그런 하한이 없다 — 시스템 전체 최근접 상위 10 을 독점하기에
충분한 정도면 된다.

조항 코드 3개(1.1·1.2·1.3)를 공개 문서에 실제로 심는다 —
`demo/compare.py::_조항코드` 의 LEFT JOIN 매핑과 "호출자가 준 id 순서를
따른다"는 주장을 직접 검증하기 위해서다(리뷰 지적 Important 2). "제1조"
청크는 clause_id 를 NULL 로 남겨 "조항 밖" 폴백도 같이 덮는다.
"""

import random

import pytest
from fastapi.testclient import TestClient

from adapters.db.chunk_search import PgChunkSearch
from adapters.db.principal_store import PgPrincipalStore
from api.demo import build_demo_router
from api.main import build_app
from core.types import EMBEDDING_DIM, Principal
from demo.compare import MAX_DEMO_K, _조항코드

pytestmark = pytest.mark.db

시크릿 = "demo-test-secret"
_시크릿 = {"X-Backend-Secret": 시크릿}

절반 = EMBEDDING_DIM // 2
# 기밀축을 정확히 가리키는 질의 벡터. "제1조" 청크와 임원 전용 문서의
# 청크들을 이 축 근처에 심어, 시스템 전체 최근접 상위권이 그쪽으로
# 쏠리게 만든다(test_naive_leaks.py 와 같은 메커니즘).
질의_벡터 = [1.0] * 절반 + [0.0] * 절반

공개_문서당_청크 = 30
기밀_문서당_청크 = 15


def _기밀_지터(rng: random.Random) -> str:
    """질의 축 근처. 코사인 거리 ~0~0.1 — 공개 청크보다 압도적으로 가깝다."""
    앞 = [1.0 + rng.uniform(0, 0.1) for _ in range(절반)]
    뒤 = [0.0 for _ in range(절반)]
    return str(앞 + 뒤)


def _공개_지터(rng: random.Random) -> str:
    """질의 축과 무관한 직교축 근처. 코사인 거리 ~1.0."""
    앞 = [0.0 for _ in range(절반)]
    뒤 = [1.0 + rng.uniform(0, 0.1) for _ in range(절반)]
    return str(앞 + 뒤)


class _질의_임베더:
    """실제 e5 모델 대신 고정 벡터를 낸다 — 이 파일은 임베딩 품질이 아니라
    API 계약을 본다."""

    def encode(self, texts, kind):
        return [질의_벡터 for _ in texts]


@pytest.fixture
def _코퍼스(db연결):
    """공개 문서(전사공개, 등급1) + 임원 전용 문서(등급3).

    파일 상단 독스트링에 배치 근거를 적었다 — 여기서는 SQL 만 남긴다.
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
        공개_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO documents (title, source_path, doc_type, "
            "required_clearance, allowed_departments) "
            "VALUES (%s, %s, 'md', %s, %s) RETURNING id",
            ("임원 전용 규정", "demo-sec.md", 3, None),
        )
        기밀_id = cur.fetchone()[0]

        # 실제 조항 코드 3개 — _조항코드 가 LEFT JOIN 으로 실제 매핑을
        # 만든다는 것과, 그 결과가 호출자가 준 id 순서를 따른다는 것을
        # 검증하려면 진짜 clauses 행이 있어야 한다.
        조항_id = {}
        for code in ("1.1", "1.2", "1.3"):
            cur.execute(
                "INSERT INTO clauses (document_id, code, title, text) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (공개_id, code, f"조항 {code}", f"조항 {code} 본문"),
            )
            조항_id[code] = cur.fetchone()[0]

        삽입 = (
            "INSERT INTO chunks (document_id, clause_id, ordinal, text, embedding, text_tsv) "
            "VALUES (%s, %s, %s, %s, %s, to_tsvector('simple', %s))"
        )

        # 0번: "제1조", clause_id NULL, 질의 벡터와 정확히 일치(거리 0) —
        # test_응답에_본문이_없다 가 공허하게 통과하지 않으려면 이 문장이
        # 실제로 상위 k 에 들어야 한다(test_코퍼스에_검사할_문장이_있다 가드).
        cur.execute(
            삽입,
            (공개_id, None, 0, "제1조 비밀번호는 12자 이상이어야 한다", str(질의_벡터), "제1조"),
        )

        rng = random.Random(11)

        # 1~3번: 실제 조항이 달린 청크. 지터는 공개축 — _조항코드 검증에는
        # 순위가 필요 없으니 다른 공개 청크와 같은 스타일로 둔다.
        for i, code in enumerate(("1.1", "1.2", "1.3"), start=1):
            cur.execute(
                삽입,
                (공개_id, 조항_id[code], i, f"조항 {code} 청크", _공개_지터(rng), f"조항{code}"),
            )

        # 나머지 공개 청크 — clause_id NULL, 채우기용.
        cur.executemany(
            삽입,
            [
                (공개_id, None, i, f"공개조항 {i}", _공개_지터(rng), f"공개조항 {i}")
                for i in range(4, 공개_문서당_청크)
            ],
        )

        # 임원 전용 청크 — 전부 질의 축 근처. 낮은 등급 페르소나는 이
        # 문서를 아예 못 보므로, 순진한 경로가 이것들을 사후에 걸러내면서
        # naive 개수가 prefiltered 보다 줄어든다.
        cur.executemany(
            삽입,
            [
                (기밀_id, None, i, f"기밀조항 {i}", _기밀_지터(rng), f"기밀조항 {i}")
                for i in range(기밀_문서당_청크)
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


def test_조항코드가_호출자_순서를_따른다(_코퍼스):
    """`_조항코드`(demo/compare.py) 의 순서 보존·NULL 폴백 주장을 직접 본다.

    이 함수가 SQL 결과 자체의 순서(보통 id 오름차순)를 그대로 돌려주면
    화면의 순위 채널이 뒤집힌다. 호출자가 준 id 순서와 다르게 — 오름차순도
    아니고 내림차순도 아니게 — 섞어서 넘겨, 구현이 진짜로 호출자 순서를
    따르는지 본다. clause_id 가 NULL 인 청크("제1조")가 "조항 밖" 으로
    떨어지는 것도 같이 확인한다.
    """
    conn = _코퍼스
    with conn.cursor() as cur:
        cur.execute("SELECT cl.code, c.id FROM chunks c JOIN clauses cl ON cl.id = c.clause_id")
        코드별_id = dict(cur.fetchall())
        cur.execute("SELECT id FROM chunks WHERE text LIKE %s", ("%제1조%",))
        (제1조_id,) = cur.fetchone()

    순서 = [코드별_id["1.3"], 코드별_id["1.1"], 제1조_id, 코드별_id["1.2"]]
    assert _조항코드(conn, 순서, Principal("개발팀", 1)) == ["1.3", "1.1", "조항 밖", "1.2"]


def test_조항코드가_권한_밖_id_를_조용히_뺀다(_코퍼스):
    """`_조항코드` 가 자기 문장 안에 권한 필터를 갖는지 본다.

    조항 코드는 본문이 아니지만 그 문서가 **존재한다**는 것을 확인해 준다.
    오늘 두 호출부는 이미 걸러진 id 만 주므로 이 함수가 필터를 잃어도 응답은
    똑같다 — 그래서 계약을 여기서 직접 못 박는다. 권한 밖 id 는 예외도
    자리표시자도 없이 목록에서 그냥 빠져야 한다(chunk_search.load_hits 와
    같은 계약: 접근 불가라는 응답 자체가 존재 확인이 된다).

    등급 3 으로 같은 두 id 를 먼저 넣어본다 — 아니면 "id 가 애초에 없어서
    빠졌다" 와 구별되지 않아 이 테스트가 공허해진다.
    """
    conn = _코퍼스
    with conn.cursor() as cur:
        cur.execute("SELECT cl.code, c.id FROM chunks c JOIN clauses cl ON cl.id = c.clause_id")
        코드별_id = dict(cur.fetchall())
        cur.execute(
            "SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id"
            " WHERE d.title = %s ORDER BY c.id LIMIT 1",
            ("임원 전용 규정",),
        )
        (기밀_id,) = cur.fetchone()

    둘 = [코드별_id["1.1"], 기밀_id]
    assert _조항코드(conn, 둘, Principal("경영지원팀", 3)) == ["1.1", "조항 밖"]
    assert _조항코드(conn, 둘, Principal("개발팀", 1)) == ["1.1"]


def test_응답에_본문이_없다(demo_client):
    r = demo_client.post("/demo/compare", json={"demo_index": 1, "k": 10}, headers=_시크릿)
    본문 = r.text
    assert "text" not in r.json()["personas"][0]["prefiltered"]
    # 실제 청크 본문의 한 조각이 응답 어디에도 없어야 한다
    assert "제1조" not in 본문


def test_세_페르소나가_모두_나온다(demo_client):
    r = demo_client.post("/demo/compare", json={"demo_index": 1, "k": 10}, headers=_시크릿)
    이름 = [p["name"] for p in r.json()["personas"]]
    assert 이름 == ["김개발", "박인사", "최임원"]


def test_사전_필터링_개수가_k_로_고정된다(demo_client):
    r = demo_client.post("/demo/compare", json={"demo_index": 1, "k": 10}, headers=_시크릿)
    assert all(p["prefiltered"]["count"] == 10 for p in r.json()["personas"])


def test_순진한_경로가_사전_필터링과_달라진다(demo_client):
    """naive 채널이 prefiltered 를 그대로 복사한 것이 아님을 직접 본다.

    임원 전용 문서의 청크가 질의 축에 딱 붙어 있어 시스템 전체
    최근접 상위권을 차지한다(코퍼스 배치, 파일 상단 참고). 순진한 경로는
    그 최근접 상위 k 를 먼저 뽑고 나중에 걸러내므로, 그 문서를 못 보는
    페르소나는 사후 필터링에서 대부분을 잃는다 — 반면 사전 필터링은
    애초에 자신이 볼 수 있는 문서 안에서만 검색하므로 항상 k 를 채운다.
    이 차이가 갈리지 않으면 naive 가 prefiltered 와 같은 함수를 부르고
    있다는 뜻이다.
    """
    r = demo_client.post("/demo/compare", json={"demo_index": 1, "k": 10}, headers=_시크릿)
    페르소나 = {p["name"]: p for p in r.json()["personas"]}

    최임원 = 페르소나["최임원"]
    assert 최임원["naive"]["count"] == 최임원["prefiltered"]["count"] == 10

    for 이름 in ("김개발", "박인사"):
        p = 페르소나[이름]
        assert p["prefiltered"]["count"] == 10
        assert p["naive"]["count"] < p["prefiltered"]["count"], (
            f"{이름}: naive 개수가 prefiltered 와 같다({p['naive']['count']}) — "
            "순진한 경로가 실제로는 사전 필터링과 같은 함수를 부르고 있을 수 있다."
        )


def test_k_에_상한이_있다(demo_client):
    """모델이 부르는 경로는 아니지만 브라우저가 부른다 — 값을 믿지 않는다.

    코퍼스가 MAX_DEMO_K(20) 보다 많은 청크를 갖고 있어야 이 단언이 의미가
    있다 — 그렇지 않으면 clamp 가 없어도 코퍼스 크기 때문에 우연히
    20 이하가 나온다(리뷰 지적 Minor 3). 공개 문서만 30개라 김개발·박인사도
    풀이 20 을 넘는다.
    """
    r = demo_client.post("/demo/compare", json={"demo_index": 1, "k": 9999}, headers=_시크릿)
    assert r.json()["k"] == MAX_DEMO_K
    assert all(p["prefiltered"]["count"] == MAX_DEMO_K for p in r.json()["personas"])


def test_LLM_을_부르지_않는다(demo_client_모델_없음):
    """모델 자격증명이 아예 없어도 200 이어야 한다.

    이 경로가 무료라는 주장이 참인지를 구조로 확인한다.
    """
    r = demo_client_모델_없음.post(
        "/demo/compare", json={"demo_index": 1, "k": 10}, headers=_시크릿
    )
    assert r.status_code == 200


def test_시크릿_없이는_401(demo_client):
    r = demo_client.post("/demo/compare", json={"demo_index": 1, "k": 10})
    assert r.status_code == 401

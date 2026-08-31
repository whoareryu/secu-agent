"""누출 테스트 — 사후 필터링이면 반드시 실패한다.

docker compose up -d
.venv/bin/python -m pytest -m db tests/test_leakage.py -v

**이 테스트들은 TRUNCATE 로 시작한다.** 돌리고 나면 개발용으로 적재해둔
ISMS-P 와 사내 규정이 사라진다. 평가 하네스를 돌리기 전에 다시 적재한다:

    .venv/bin/python -m pipeline.cli ingest ../data/raw/ismsp.pdf \
        --title "ISMS-P 인증기준 안내서"
    .venv/bin/python -m pipeline.cli ingest-dir ../data/policies
"""

import os
import random
import statistics
import time

import pytest

from adapters.db.chunk_search import _벡터_SQL, PgChunkSearch
from adapters.db.connection import apply_schema, connect
from core.agent.policy import AccessViolation, enforce
from core.types import EMBEDDING_DIM, Principal

pytestmark = pytest.mark.db

DSN = os.environ.get("SECUAGENT_DSN", "postgresql://secuagent:secuagent@localhost:5433/secuagent")

사원 = Principal(department="개발팀", clearance=1)
팀장 = Principal(department="개발팀", clearance=2)
임원 = Principal(department="개발팀", clearance=3)

# 문서당 청크 수. **2,000 아래로 줄이면 이 파일의 판별력이 사라진다.**
# 실측(pgvector:pg16): AS MATERIALIZED 를 NOT MATERIALIZED 로 바꿨을 때
# 문서당 300개(총 600)면 여전히 10건이 나오고, 2,000개(총 4,000)여야 0건이
# 된다. 600 규모에서는 플래너가 인라인해도 순차 스캔으로 정확 검색을 해서
# 근사 인덱스의 후보 절단이 일어나지 않는다.
문서당_청크 = 2000

절반 = EMBEDDING_DIM // 2

# 좌표 블록으로 직교를 강제한다. 난수 단위벡터로 하면 안 된다 —
# 실측: 384차원에서 난수 두 개의 cos 가 0.101 이 나왔고, "기밀 축 근처"로
# 심은 청크들이 무관해야 할 질의의 상위 10건 중 9건을 차지했다.
질의_기밀축 = [1.0] * 절반 + [0.0] * 절반
질의_공개축 = [0.0] * 절반 + [1.0] * 절반


def _벡터(앞쪽: bool, rng: random.Random) -> str:
    앞 = [1.0 + rng.uniform(0, 0.1) if 앞쪽 else 0.0 for _ in range(절반)]
    뒤 = [0.0 if 앞쪽 else 1.0 + rng.uniform(0, 0.1) for _ in range(절반)]
    return str(앞 + 뒤)


@pytest.fixture(scope="module")
def 코퍼스():
    """공개 2,000 + 기밀 2,000 청크. executemany 로 약 4초 걸린다."""
    conn = connect(DSN)
    apply_schema(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE documents RESTART IDENTITY CASCADE")

        def 문서(title, path, clearance, depts=None):
            cur.execute(
                "INSERT INTO documents (title, source_path, doc_type, "
                "required_clearance, allowed_departments) "
                "VALUES (%s, %s, 'md', %s, %s) RETURNING id",
                (title, path, clearance, depts),
            )
            return cur.fetchone()[0]

        공개 = 문서("공개 규정", "pub.md", 1)
        기밀 = 문서("임원 전용 규정", "sec.md", 3)
        타부서 = 문서("인사팀 내규", "hr.md", 1, ["인사팀"])

        rng = random.Random(7)
        삽입 = (
            "INSERT INTO chunks (document_id, clause_id, ordinal, text, embedding, text_tsv) "
            "VALUES (%s, NULL, %s, %s, %s, to_tsvector('simple', %s))"
        )
        for doc_id, 앞쪽, 이름 in ((기밀, True, "기밀"), (공개, False, "공개")):
            cur.executemany(
                삽입,
                [
                    (doc_id, i, f"{이름}조항 {i}", _벡터(앞쪽, rng), f"{이름}조항 {i}")
                    for i in range(문서당_청크)
                ],
            )
        # 부서 축을 가르는 소량. 등급은 사원과 같고 부서만 다르다.
        cur.executemany(
            삽입,
            [(타부서, i, f"인사조항 {i}", _벡터(True, rng), f"인사조항 {i}") for i in range(50)],
        )
    conn.commit()
    yield conn, PgChunkSearch(conn)
    conn.close()


def _검색(searcher, q, principal, k=10):
    return searcher.by_vector(q, principal, k)


# ─────────────────────────── 누출 경로 ① 개수 ───────────────────────────


def test_결과_개수가_주체에_따라_달라지지_않는다(코퍼스):
    """사후 필터링이면 등급이 낮을수록 결과가 줄어든다."""
    _, searcher = 코퍼스
    개수 = [len(_검색(searcher, 질의_기밀축, p)) for p in (사원, 팀장, 임원)]
    assert 개수 == [10, 10, 10], f"등급별 결과 개수가 다르다: {개수}"


def test_결과_개수가_질의에_따라_달라지지_않는다(코퍼스):
    """**이 테스트가 사후 필터링을 잡는다.**

    고정 주체(등급 1)가 두 질의를 던진다. 하나는 자기가 못 보는 기밀 축을
    정확히 가리키고, 하나는 자기가 볼 수 있는 공개 축을 가리킨다.

    사후 필터링이면 기밀 축 질의의 상위 후보가 전부 걸러져 0건이 되고,
    그 0 이 "내가 못 보는 곳에 이 질의와 아주 가까운 문서가 있다"를
    알려준다. 실측: AS NOT MATERIALIZED 로 바꾸면 기밀축 0건 · 공개축 10건.
    """
    _, searcher = 코퍼스
    기밀축 = len(_검색(searcher, 질의_기밀축, 사원))
    공개축 = len(_검색(searcher, 질의_공개축, 사원))
    assert 기밀축 == 공개축 == 10, f"질의에 따라 개수가 갈린다: 기밀축 {기밀축} · 공개축 {공개축}"


# ─────────────────────────── 누출 경로 ② 순위 ───────────────────────────


def test_두_주체에게_모두_보이는_문서의_상대_순위가_같다(코퍼스):
    """등급 3 문서가 후보에 끼어들어도 공개 문서끼리의 상대 순위는 그대로여야 한다.

    흔들리면 "상위권에서 빠진 자리"가 보이고, 그 빈자리가 존재를 알린다.
    """
    _, searcher = 코퍼스
    사원_결과 = _검색(searcher, 질의_공개축, 사원, k=30)
    임원_결과 = _검색(searcher, 질의_공개축, 임원, k=30)

    공통 = set(사원_결과) & set(임원_결과)
    assert len(공통) >= 10, f"공통 문서가 너무 적어 순위를 비교할 수 없다: {len(공통)}"

    사원_순서 = [i for i in 사원_결과 if i in 공통]
    임원_순서 = [i for i in 임원_결과 if i in 공통]
    assert 사원_순서 == 임원_순서, "두 주체 모두에게 보이는 청크의 상대 순위가 다르다"


# ─────────────────────────── 누출 경로 ③ 타이밍 ───────────────────────────


def _계획(conn, sql, params) -> dict:
    with conn.cursor() as cur:
        cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + sql, params)
        return cur.fetchone()[0][0]


def _CTE_스캔_행수(plan: dict) -> int:
    찾은 = []

    def 훑기(node):
        if node.get("Node Type") == "CTE Scan":
            찾은.append(node["Actual Rows"])
        for ch in node.get("Plans", []):
            훑기(ch)

    훑기(plan["Plan"])
    assert 찾은, (
        "CTE Scan 노드가 없다 — 플래너가 CTE 를 인라인했다는 뜻이고, "
        "그 순간 권한 필터가 순위 뒤로 밀려 사후 필터링이 된다"
    )
    return 찾은[0]


def test_훑는_후보_집합이_질의와_무관하다(코퍼스):
    """타이밍 채널을 벽시계가 아니라 구조로 잰다.

    **벽시계로 재면 안 된다 — 실측으로 확인했다.** 사전/사후 두 구현의
    중앙값 비가 각각 1.17 과 1.21 로 사실상 같아, 어떤 임계를 골라도
    두 구현을 가르지 못한다. 통과하지만 아무것도 지키지 않는 테스트가 된다.

    타이밍이 새지 않는 진짜 근거는 "훑는 후보 집합이 주체에만 의존하고
    질의에는 의존하지 않는다"이다. EXPLAIN 이 그것을 결정론적으로 보여준다.
    실측: 등급 1 은 질의와 무관하게 2,000행, 등급 3 은 4,000행.
    """
    conn, _ = 코퍼스
    행수 = {}
    for 이름, q in (("기밀축", 질의_기밀축), ("공개축", 질의_공개축)):
        계획 = _계획(
            conn,
            _벡터_SQL,
            {"clearance": 사원.clearance, "dept": 사원.department, "qvec": str(q), "k": 10},
        )
        행수[이름] = _CTE_스캔_행수(계획)

    assert 행수["기밀축"] == 행수["공개축"], (
        f"질의에 따라 훑는 후보 수가 다르다: {행수} — 응답 시간이 질의에 따라 갈리고, "
        "그 차이가 숨겨진 문서의 존재를 알린다"
    )


def test_후보_집합이_주체의_권한_범위와_일치한다(코퍼스):
    """등급이 오르면 후보가 늘어나는 것은 누출이 아니다 — 주체는 남의 응답
    시간을 관측할 수 없다. 다만 그 수가 권한 범위와 정확히 맞아야 사전
    필터링이 실제로 걸렸다는 증거가 된다.

    실측: 등급 1 은 공개 2,000, 등급 3 은 공개 2,000 + 기밀 2,000 = 4,000.
    (부서 축 50개는 개발팀에게 안 보인다.)
    """
    conn, _ = 코퍼스

    def 행수(p):
        return _CTE_스캔_행수(
            _계획(
                conn,
                _벡터_SQL,
                {"clearance": p.clearance, "dept": p.department, "qvec": str(질의_기밀축), "k": 10},
            )
        )

    assert 행수(사원) == 문서당_청크
    assert 행수(임원) == 문서당_청크 * 2


@pytest.mark.slow
def test_응답시간이_질의에_따라_갈리지_않는다(코퍼스):
    """벽시계 보조 측정.

    **이 테스트만으로는 사후 필터링을 잡지 못한다** — 실측에서 고장난
    구현도 통과했다. 1급 근거는 위의 EXPLAIN 테스트다. 이것은 구조가
    맞는데도 시간이 크게 갈리는 예상 밖의 상황을 잡는 그물일 뿐이며,
    그래서 임계가 관대하다.
    """
    _, searcher = 코퍼스

    def 중앙값(q):
        ts = []
        for _ in range(30):
            t0 = time.perf_counter()
            _검색(searcher, q, 사원)
            ts.append(time.perf_counter() - t0)
        return statistics.median(ts)

    비 = 중앙값(질의_기밀축) / 중앙값(질의_공개축)
    assert 0.5 < 비 < 2.0, f"질의별 응답시간 비가 {비:.2f} 다"


# ─────────────────────── 누출 경로 ④ 도구 출력 ───────────────────────


def test_도구_출력에_권한_밖_항목이_있으면_예외가_난다(코퍼스):
    """enforce 가 조용히 걸러내지 않고 터지는지 실제 데이터로 확인한다."""
    conn, searcher = 코퍼스

    # 임원에게만 보이는 청크 하나를 골라 사원의 결과에 억지로 섞는다.
    임원_ids = _검색(searcher, 질의_기밀축, 임원)
    기밀_hits = searcher.load_hits(임원_ids, 임원)
    assert 기밀_hits, "임원 결과가 비면 이 테스트는 공허하다"
    기밀 = next(h for h in 기밀_hits if h.required_clearance == 3)

    사원_hits = searcher.load_hits(_검색(searcher, 질의_공개축, 사원), 사원)
    assert enforce(사원_hits, 사원) == 사원_hits  # 정상 경로는 통과한다

    with pytest.raises(AccessViolation):
        enforce([*사원_hits, 기밀], 사원)


def test_load_hits_는_권한_밖_id_를_조용히_뺀다(코퍼스):
    """예외를 던지면 안 된다 — "그 id 는 접근 불가"라는 응답 자체가 존재 확인이다."""
    _, searcher = 코퍼스
    임원_ids = _검색(searcher, 질의_기밀축, 임원)
    사원_결과 = searcher.load_hits(임원_ids, 사원)  # 예외가 나면 안 된다
    assert 사원_결과 == []

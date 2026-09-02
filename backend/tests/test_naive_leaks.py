"""순진한 경로가 실제로 새는지 확인한다.

이 테스트가 통과하지 않으면 시연 화면이 성립하지 않는다 — 두 경로가
같은 결과를 내면 보여줄 것이 없다.

test_leakage.py 와 방향이 반대다. 저쪽은 "우리 경로가 새지 않는가" 를
묻고, 이쪽은 "순진한 경로가 정말로 새는가" 를 묻는다. 둘 다 필요하다.
"""

import random

import pytest

from adapters.db.chunk_search import PgChunkSearch
from core.types import EMBEDDING_DIM, Principal
from demo.naive_search import naive_ids

pytestmark = pytest.mark.db

_k = 10
개발자 = Principal(department="개발팀", clearance=1)
임원 = Principal(department="경영지원팀", clearance=3)

# 문서당 청크 수. test_leakage.py 의 2,000 은 AS MATERIALIZED 인라인(2단계
# 누출, 근사 인덱스의 후보 절단)을 잡기 위한 규모였다. 여기서 잡는 것은
# 1단계 — 순진한 경로의 사후 필터링 — 이라 그 메커니즘이 필요 없다:
# 순진한 SQL 은 애초에 권한 없이 LIMIT k 를 뽑으므로, 기밀축 근처에 심은
# 청크가 공개 청크보다 코사인 거리로 압도적으로 가깝다(아래 _벡터 참고 —
# 기밀 쪽은 질의와 코사인 거리 ~0.0005, 공개 쪽은 ~1.0). 그래서 순진한
# 경로의 상위 k 는 문서당 청크 수와 무관하게 전부 기밀 쪽으로 쏠린다.
# 실측: 문서당 50 / 30 / 20 개 모두 사후 개수가 개발자 0건 · 임원 10건으로
# 동일했다. 문서당 5개로는 실패했다 — 원인은 임베딩 판별력이 아니라
# `test_사전_필터링은_개수가_k_로_고정된다` 가 구조적으로 요구하는 하한이다:
# 개발자(등급 1)가 보는 풀이 공개 문서 하나뿐이라 그 문서의 청크 수가
# k(10) 이상이어야 사전 필터링도 k 건을 채운다. 즉 진짜 하한은 문서당
# 청크 수 == k 다. 그 경계에 바로 붙이지 않고 2배인 20을 최종값으로
# 남긴다 — k 를 조금 올리는 미래 변경에도 이 파일이 구조적으로 깨지지
# 않을 여유를 두기 위해서다.
문서당_청크 = 20

절반 = EMBEDDING_DIM // 2

# 좌표 블록으로 직교를 강제한다. 난수 단위벡터로 하면 안 된다 —
# 실측(test_leakage.py): 384차원에서 난수 두 개의 cos 가 0.101 이 나왔고,
# "기밀 축 근처"로 심은 청크들이 무관해야 할 질의의 상위 10건 중 9건을
# 차지했다.
질의_기밀축 = [1.0] * 절반 + [0.0] * 절반
질의_공개축 = [0.0] * 절반 + [1.0] * 절반


def _벡터(앞쪽: bool, rng: random.Random) -> str:
    앞 = [1.0 + rng.uniform(0, 0.1) if 앞쪽 else 0.0 for _ in range(절반)]
    뒤 = [0.0 if 앞쪽 else 1.0 + rng.uniform(0, 0.1) for _ in range(절반)]
    return str(앞 + 뒤)


@pytest.fixture
def 코퍼스(db연결):
    """공개 문서 + 등급 3 문서. 등급 3 쪽 청크가 질의에 더 가깝게 심는다.

    이 배치가 이 파일의 전부다. 기밀 청크가 질의 근처에 없으면 순진한
    경로도 새지 않고, 그러면 시연이 아무것도 보여주지 못한다.
    """
    # test_leakage.py 의 좌표 블록 방식을 그대로 쓴다 — 난수 단위벡터는
    # 384차원에서 cos 가 0.1 씩 나와 직교가 보장되지 않는다(W2 실측).
    conn = db연결
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
    conn.commit()
    yield conn


@pytest.fixture
def 임베딩():
    """기밀축을 정확히 가리키는 질의 벡터.

    이래야 전체 청크 상위 k 가 기밀 문서 쪽으로 쏠려, 순진한 경로의
    사후 필터링이 개발자 결과를 눈에 띄게 깎아낸다.
    """
    return 질의_기밀축


def test_사전_필터링은_개수가_k_로_고정된다(코퍼스, 임베딩):
    검색 = PgChunkSearch(코퍼스)
    for p in (개발자, 임원):
        assert len(검색.by_vector(임베딩, p, _k)) == _k


def test_순진한_경로는_등급에_따라_개수가_갈린다(코퍼스, 임베딩):
    """**이 테스트가 시연의 전제다.**

    갈리지 않으면 화면에서 보여줄 것이 없다. 그때는 코퍼스 배치를
    고쳐야지 화면 문구를 고치면 안 된다.
    """
    낮음 = len(naive_ids(코퍼스, 임베딩, 개발자, _k))
    높음 = len(naive_ids(코퍼스, 임베딩, 임원, _k))
    assert 높음 == _k
    assert 낮음 < 높음, (
        f"순진한 경로에서도 개수가 같다({낮음} == {높음}). "
        "기밀 청크가 질의 근처에 없다 — 코퍼스 배치를 고친다."
    )


def test_개수_차이가_그대로_존재_신호다(코퍼스, 임베딩):
    """화면이 주장할 문장을 테스트로 고정한다.

    사후 필터링에서 빠진 건수 = 권한 밖 문서가 상위 k에 든 건수.
    """
    낮음 = naive_ids(코퍼스, 임베딩, 개발자, _k)
    assert _k - len(낮음) > 0


def test_순서가_호출마다_안정적이다(코퍼스, 임베딩):
    """이 코퍼스·이 플래너 계획에서 호출마다 같은 순서가 나오는지만 본다.

    **바깥 ORDER BY 가 있어서 안정적인지는 이 테스트가 증명하지 못한다.**
    실측(리뷰): 이 규모(문서 9개·청크 338개)에서 Postgres 는 Nested Loop +
    Memoize 계획을 골라 바깥 ORDER BY 를 통째로 지워도 여덟 번 다 똑같은
    순서(`[8, 17, 11, 19, 12, 13, 14, 15, 9, 3]`)가 나온다 — 계획이 우연히
    순서를 보존하기 때문이지, 문장이 그것을 보장해서가 아니다. 그 보장은
    tests/test_naive_search_sql.py 가 DB 없이 문장 위치로 고정한다. 이
    테스트는 그와 별개로 "지금 이 컨테이너에서 실제로 관측되는 순서가
    안정적인가"라는 더 약한 사실만 남긴다.
    """
    첫번째 = naive_ids(코퍼스, 임베딩, 임원, _k)
    두번째 = naive_ids(코퍼스, 임베딩, 임원, _k)
    assert 첫번째 == 두번째

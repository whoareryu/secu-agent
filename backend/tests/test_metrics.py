"""검색 지표 — 손으로 계산한 값과 대조한다.

지표가 조용히 틀리면 이후 모든 숫자가 거짓이 된다. 그래서 DB 도 모델도
없이, 답을 손으로 아는 사례로만 검증한다.
"""

import math

from eval.metrics import mrr_at_k, ndcg_at_k, recall_at_k


def test_recall_은_정답_중_찾은_비율이다():
    # 정답 2개 중 1개를 상위 10 안에서 찾았다.
    assert recall_at_k(["2.6.1", "2.5.1", "9.9.9"], {"2.6.1", "2.7.1"}, 10) == 0.5


def test_recall_은_k_밖을_세지_않는다():
    # 2.7.1 이 3위에 있지만 k=2 면 못 찾은 것이다.
    assert recall_at_k(["9.9.9", "8.8.8", "2.7.1"], {"2.7.1"}, 2) == 0.0


def test_recall_은_전부_찾으면_1이다():
    assert recall_at_k(["2.6.1", "2.7.1"], {"2.6.1", "2.7.1"}, 10) == 1.0


def test_정답이_없으면_recall_은_0이다():
    # 0으로 나누면 안 된다.
    assert recall_at_k(["2.6.1"], set(), 10) == 0.0


def test_mrr_은_첫_정답_순위의_역수다():
    assert mrr_at_k(["2.6.1", "9.9.9"], {"2.6.1"}, 10) == 1.0
    assert mrr_at_k(["9.9.9", "8.8.8", "2.6.1"], {"2.6.1"}, 10) == 1 / 3


def test_mrr_은_정답을_못_찾으면_0이다():
    assert mrr_at_k(["9.9.9"], {"2.6.1"}, 10) == 0.0


def test_ndcg_는_손계산과_맞는다():
    # 1위 정답, 2위 오답, 3위 정답.
    #   DCG  = 1/log2(2) + 0 + 1/log2(4) = 1 + 0.5 = 1.5
    #   IDCG = 1/log2(2) + 1/log2(3)     = 1 + 0.63093 = 1.63093
    #   nDCG = 1.5 / 1.63093 = 0.91972
    got = ndcg_at_k(["A", "X", "B"], {"A", "B"}, 10)
    assert math.isclose(got, 1.5 / (1 + 1 / math.log2(3)), rel_tol=1e-9)
    assert math.isclose(got, 0.91972, abs_tol=1e-5)


def test_ndcg_는_완벽하면_1이다():
    assert math.isclose(ndcg_at_k(["A", "B", "X"], {"A", "B"}, 10), 1.0)


def test_ndcg_는_하나도_못_찾으면_0이다():
    assert ndcg_at_k(["X", "Y"], {"A"}, 10) == 0.0


def test_중복_조항은_한_번만_센다():
    """한 조항에서 청크 여러 개가 뽑히면 같은 코드가 반복된다.

    중복을 그대로 세면 Recall 이 부풀고, 순위가 뒤로 밀린 정답이 앞에
    있는 것처럼 보인다. 처음 등장한 위치를 순위로 삼는다.
    """
    assert recall_at_k(["A", "A", "A", "B"], {"A", "B"}, 10) == 1.0
    # A 가 세 번 나와도 B 의 순위는 2위다 — 4위가 아니다.
    assert mrr_at_k(["A", "A", "A", "B"], {"B"}, 10) == 0.5

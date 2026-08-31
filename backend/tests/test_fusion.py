from core.retrieve.fusion import rrf, rrf_scores


def test_두_검색기_모두에_등장한_문서가_1위다():
    # 서로 다른 신호가 동의하는 문서를 올리는 것이 RRF 의 존재 이유다.
    assert rrf([[1, 2, 3], [3, 4, 5]])[0] == 3


def test_한_검색기_1위보다_두_검색기_2위가_이긴다():
    # 10 은 1위 한 번, 20 은 2위 두 번.
    fused = rrf([[10, 20], [30, 20]])
    assert fused.index(20) < fused.index(10)


def test_모든_후보가_결과에_포함된다():
    assert set(rrf([[1, 2], [3]])) == {1, 2, 3}


def test_중복이_없다():
    fused = rrf([[1, 1, 2], [1, 2]])
    assert len(fused) == len(set(fused))


def test_빈_입력은_빈_결과다():
    assert rrf([]) == []
    assert rrf([[], []]) == []


def test_검색기가_하나면_순위를_그대로_유지한다():
    assert rrf([[7, 8, 9]]) == [7, 8, 9]


def test_k가_클수록_순위차의_영향이_줄어든다():
    # k 는 상위권 쏠림을 완화하는 상수다.
    작은k = rrf_scores([[1, 2]], k=1)
    큰k = rrf_scores([[1, 2]], k=1000)
    assert 작은k[1] - 작은k[2] > 큰k[1] - 큰k[2]


def test_동점이면_먼저_등장한_순서를_지킨다():
    # 결과가 실행마다 흔들리면 평가 지표를 믿을 수 없다.
    for _ in range(5):
        assert rrf([[1], [2]]) == [1, 2]

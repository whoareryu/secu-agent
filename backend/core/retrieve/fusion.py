"""Reciprocal Rank Fusion.

가중 합산이 아니라 RRF 를 쓰는 이유는 두 검색기의 점수 스케일이 다르기
때문이다 — 코사인은 0~1, ts_rank 는 임의 스케일이다. 정규화하려면 분포를
조사하고 계수를 튜닝해야 하는데, 3~4주 일정에서 그럴 여유가 없다.
RRF 는 순위만 쓰므로 튜닝할 파라미터가 사실상 없다.

이 모듈은 DB 를 모른다. 순위 병합이 가장 버그가 나기 쉬운 곳이라
DB 없이 테스트되어야 한다.
"""

from collections.abc import Sequence

DEFAULT_K = 60


def rrf_scores(rankings: Sequence[Sequence[int]], k: int = DEFAULT_K) -> dict[int, float]:
    """후보 id → RRF 점수. 점수 = Σ 1/(k + 순위), 순위는 0부터."""
    if k <= 0:
        # k=0 이면 첫 순위(순위 0)에서 1/(0+0) 이다. 도달 불가라고 두지
        # 않는 이유: k 는 공개 인자이고, 튜닝하려고 0 을 넣어 보는 것이
        # 가장 그럴듯한 첫 시도다. 그때 나오는 것이 나눗셈 오류면 무엇이
        # 잘못됐는지 알 수 없다.
        raise ValueError(f"k 는 양수여야 한다: {k}")
    scores: dict[int, float] = {}
    for ranking in rankings:
        본_것: set[int] = set()
        순위 = 0
        for 후보 in ranking:
            # 같은 검색기가 같은 후보를 두 번 냈으면 첫 번째만 센다.
            if 후보 in 본_것:
                continue
            본_것.add(후보)
            scores[후보] = scores.get(후보, 0.0) + 1.0 / (k + 순위)
            순위 += 1
    return scores


def rrf(rankings: Sequence[Sequence[int]], k: int = DEFAULT_K) -> list[int]:
    """여러 순위 리스트를 하나로 융합한다.

    동점이면 먼저 등장한 순서를 지킨다 — 결과가 실행마다 흔들리면
    평가 지표를 믿을 수 없다.
    """
    scores = rrf_scores(rankings, k=k)

    등장순: dict[int, int] = {}
    for ranking in rankings:
        for 후보 in ranking:
            등장순.setdefault(후보, len(등장순))

    return sorted(scores, key=lambda 후보: (-scores[후보], 등장순[후보]))

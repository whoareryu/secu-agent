"""검색 지표 — 순수 함수. DB 도 모델도 모른다.

이진 관련도를 쓴다. 정답 조항이거나 아니거나 둘 중 하나이고, 등급을
매기려면 사람이 3단계 판정을 30건 x 10위 = 300번 해야 한다. 3~4주
일정에서 그 노동은 값을 하지 못한다.

**입력의 중복을 함수 안에서 제거한다.** 한 조항에서 청크가 여러 개
뽑히면 같은 코드가 반복되는데, 그대로 세면 Recall 이 부풀고 뒤에 있는
정답이 앞에 있는 것처럼 보인다. 호출자를 믿지 않고 여기서 정규화한다.
"""

import math
from collections.abc import Sequence


def _고유_상위(retrieved: Sequence[str], k: int) -> list[str]:
    """중복을 없애고 앞에서 k 개. 처음 등장한 위치가 순위다."""
    본_것: set[str] = set()
    출력: list[str] = []
    for code in retrieved:
        if code in 본_것:
            continue
        본_것.add(code)
        출력.append(code)
        if len(출력) == k:
            break
    return 출력


def recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """정답 조항 중 상위 k 안에서 찾은 비율."""
    if not relevant:
        return 0.0
    상위 = set(_고유_상위(retrieved, k))
    return len(상위 & relevant) / len(relevant)


def mrr_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """첫 정답 순위의 역수. 상위 k 안에 없으면 0."""
    for i, code in enumerate(_고유_상위(retrieved, k), start=1):
        if code in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """이진 관련도 nDCG. 이상적 순서(정답이 전부 앞에)로 정규화한다."""
    if not relevant:
        return 0.0
    상위 = _고유_상위(retrieved, k)
    dcg = sum(1.0 / math.log2(i + 1) for i, c in enumerate(상위, start=1) if c in relevant)
    이상적_개수 = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, 이상적_개수 + 1))
    return dcg / idcg if idcg else 0.0

import pytest

from adapters.embedding.e5 import E5Embedder
from core.types import EMBEDDING_DIM

pytestmark = pytest.mark.model


@pytest.fixture(scope="module")
def embedder():
    # 로드에 ~30초 걸린다. 모듈당 한 번만 한다.
    return E5Embedder()


def test_차원이_EMBEDDING_DIM_과_같다(embedder):
    vecs = embedder.encode(["네트워크 접근 통제"], kind="passage")
    assert len(vecs) == 1
    assert len(vecs[0]) == EMBEDDING_DIM


def test_kind_가_모델에_실제로_닿는다(embedder):
    """접두어가 붙는지를 목 없이 증명한다.

    같은 문장을 kind 만 바꿔 인코딩하면 결과가 달라야 한다. `encode` 에서
    접두어를 붙이는 줄을 지우면 두 호출이 같은 문자열을 인코딩하게 되어
    벡터가 완전히 같아지고, 이 테스트가 실패한다.

    실측: 접두어가 붙은 상태에서 두 벡터의 코사인 유사도는 0.9531 이다.
    """
    t = "이상행위를 탐지할 수 있도록 로그를 수집한다"
    q = embedder.encode([t], kind="query")[0]
    p = embedder.encode([t], kind="passage")[0]
    assert q != p, (
        "query 와 passage 가 같은 벡터다. encode 가 kind 를 받고도 "
        "접두어를 붙이지 않고 있다 — e5 계열은 접두어를 요구한다."
    )


def test_잘못된_kind_는_거부한다(embedder):
    with pytest.raises(ValueError):
        embedder.encode(["x"], kind="document")


def test_관련_문장이_무관한_문장보다_가깝다(embedder):
    """모델이 실제로 의미를 잡는지 최소한으로 확인한다."""
    q = embedder.encode(["이상행위 모니터링은 어떻게 하나요?"], kind="query")[0]
    관련, 무관 = embedder.encode(
        [
            "이상행위를 탐지할 수 있도록 이벤트 로그를 수집하여 분석 및 모니터링하여야 한다",
            "사용자 계정 발급 절차를 수립하고 계정 권한을 관리하여야 한다",
        ],
        kind="passage",
    )
    def 내적(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert 내적(q, 관련) > 내적(q, 무관), "관련 규정이 무관한 규정보다 멀다"

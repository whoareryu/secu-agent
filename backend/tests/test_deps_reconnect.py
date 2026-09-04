"""자원 수명주기 — 죽은 연결에서 스스로 돌아온다. DB 도 모델도 필요 없다.

예전에는 `@lru_cache(maxsize=1)` 가 `(conn, embedder)` 를 영구 보관했다.
연결이 한 번 죽으면 프로세스를 재시작할 때까지 모든 요청이 실패하고
`/healthz` 는 영원히 `db:false` 였다. 노트북 위에서 돌며 터널로 공개되는
구성이라 DB 컨테이너가 한 번 튀는 것은 드문 일이 아니다.

`lru_cache` 에는 두 번째 문제도 있었다. 함수 **실행 중** 락을 잡지 않으므로
동시 첫 요청 N개가 각각 `E5Embedder()`(~500MB · ~30초)를 만들고, 캐시에는
하나만 남아 나머지가 샌다.

여기서는 실제 연결도 실제 모델도 쓰지 않는다 — 이음매(`_새_연결` ·
`_새_임베더`)를 바꿔 끼워 수명주기만 본다.
"""

import threading
import time

import psycopg
import pytest

from api import deps


class 가짜연결:
    def __init__(self, 번호: int) -> None:
        self.번호 = 번호
        self.closed = 0
        self.autocommit = False

    def 죽인다(self) -> None:
        self.closed = 1


@pytest.fixture(autouse=True)
def _깨끗한_상태(monkeypatch):
    """모듈 상태는 프로세스 전역이다. 테스트끼리 새지 않게 매번 비운다."""
    deps._상태["conn"] = None
    deps._상태["embedder"] = None
    yield
    deps._상태["conn"] = None
    deps._상태["embedder"] = None


@pytest.fixture
def 연결들(monkeypatch):
    만들어진: list[가짜연결] = []

    def 새로(*_a, **_k):
        c = 가짜연결(len(만들어진))
        만들어진.append(c)
        return c

    monkeypatch.setattr(deps, "_새_연결", 새로)
    return 만들어진


@pytest.fixture
def 임베더들(monkeypatch):
    만들어진: list[object] = []

    def 새로():
        e = object()
        만들어진.append(e)
        return e

    monkeypatch.setattr(deps, "_새_임베더", 새로)
    return 만들어진


def test_같은_연결을_다시_쓴다(연결들, 임베더들):
    """매번 새로 붙으면 그건 풀도 캐시도 아니다."""
    c1, _ = deps._자원()
    c2, _ = deps._자원()

    assert c1 is c2
    assert len(연결들) == 1


def test_연결이_닫히면_다시_붙는다(연결들, 임베더들):
    c1, _ = deps._자원()
    c1.죽인다()

    c2, _ = deps._자원()

    assert c2 is not c1
    assert len(연결들) == 2


def test_재연결이_임베더를_다시_만들지_않는다(연결들, 임베더들):
    """연결이 죽었다고 모델을 다시 올리면 30초가 날아간다."""
    _, e1 = deps._자원()
    연결들[0].죽인다()

    _, e2 = deps._자원()

    assert e1 is e2
    assert len(임베더들) == 1, "임베더는 한 번만 만든다"


def test_동시_첫_호출이_임베더를_한_번만_만든다(연결들, monkeypatch):
    """lru_cache 는 실행 중 락을 잡지 않아 여기서 N개가 만들어졌다.

    각각 ~500MB 라 동시 요청 몇 개로 메모리가 무너진다. 캐시에는 하나만
    남고 나머지는 참조를 잃은 채 샌다.
    """
    만들어진: list[object] = []

    def 느린_임베더():
        time.sleep(0.05)  # 경합 창을 실제로 연다
        e = object()
        만들어진.append(e)
        return e

    monkeypatch.setattr(deps, "_새_임베더", 느린_임베더)

    결과: list[object] = []
    스레드 = [threading.Thread(target=lambda: 결과.append(deps._자원()[1])) for _ in range(8)]
    for t in 스레드:
        t.start()
    for t in 스레드:
        t.join()

    assert len(만들어진) == 1, f"임베더가 {len(만들어진)}번 만들어졌다"
    assert len(set(id(e) for e in 결과)) == 1, "모두 같은 임베더를 받아야 한다"


def test_읽기는_연결이_죽어_있으면_다시_붙어_재시도한다(연결들, 임베더들):
    """`closed` 만으로는 부족하다 — 서버가 끊어도 다음 쿼리 전까지 0 이다.

    그래서 실패를 보고 판단한다. 첫 시도가 OperationalError 면 연결을
    버리고 새로 붙어 **한 번만** 다시 부른다.
    """
    호출: list[int] = []

    def 작업(conn):
        호출.append(conn.번호)
        if len(호출) == 1:
            raise psycopg.OperationalError("server closed the connection unexpectedly")
        return "결과"

    assert deps.재시도(작업) == "결과"
    assert 호출 == [0, 1], "죽은 연결로 한 번, 새 연결로 한 번"
    assert len(연결들) == 2


def test_재시도는_한_번뿐이다(연결들, 임베더들):
    """무한히 다시 붙으면 DB 가 내려간 동안 요청이 끝나지 않는다."""
    호출: list[int] = []

    def 늘_실패(conn):
        호출.append(conn.번호)
        raise psycopg.OperationalError("여전히 죽어 있다")

    with pytest.raises(psycopg.OperationalError):
        deps.재시도(늘_실패)
    assert len(호출) == 2


def test_쓰기는_재시도하지_않는다(연결들, 임베더들):
    """autocommit 이라 첫 시도가 일부 행을 커밋한 뒤 죽었을 수 있다.

    executemany 중간에 끊기면 앞선 행은 이미 들어가 있고, 재시도하면
    그 행들이 두 번 들어간다. 열람 기록이 부풀면 감사 자료가 아니게 된다.
    """
    호출: list[int] = []

    def 쓰기(conn):
        호출.append(conn.번호)
        raise psycopg.OperationalError("쓰는 중에 끊겼다")

    with pytest.raises(psycopg.OperationalError):
        deps.한_번만(쓰기)
    assert 호출 == [0], "쓰기는 다시 부르지 않는다"


def test_모델_준비됨은_임베더가_생긴_뒤에만_참이다(연결들, 임베더들):
    assert deps.모델_준비됨() is False
    deps._자원()
    assert deps.모델_준비됨() is True

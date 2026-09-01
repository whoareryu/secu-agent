"""코퍼스가 판별력을 갖는지 검사한다.

코퍼스는 데이터이지 코드가 아니라서, 누가 줄여도 아무 테스트도 실패하지
않는다. 그래서 조건 자체를 테스트로 만든다 — test_leakage.py 가 문서당
청크 수를 상수와 주석으로 못 박아둔 것과 같은 이유다.
"""

import json
from pathlib import Path

from adapters.parsing.syslog import parse_line
from core.access.visibility import visible
from core.types import Principal

_데이터 = Path(__file__).resolve().parents[2] / "data"
_기본_limit = 10

세_페르소나 = [
    Principal(department="개발팀", clearance=1),
    Principal(department="인사팀", clearance=2),
    Principal(department="경영지원팀", clearance=3),
]


def _호스트들():
    return {h["name"]: h for h in json.loads((_데이터 / "hosts.json").read_text("utf-8"))}


def _이벤트들():
    이벤트 = []
    for p in sorted((_데이터 / "logs").glob("*.log")):
        연도 = int(p.stem[:4])
        이벤트 += [
            e
            for e in (parse_line(줄, year=연도) for 줄 in p.read_text("utf-8").splitlines())
            if e is not None
        ]
    return 이벤트


def test_코퍼스에_검사할_이벤트가_있다():
    # 이벤트가 0건이면 아래 "미등록 호스트 없다" · "최근 이벤트가 최고 등급
    # 전용이다" 두 테스트가 공허하게 통과한다(빈 집합에 대한 assert not 이
    # 항상 참이라서) — data/ 경로가 잘못돼도 그 두 테스트만으로는 잡히지
    # 않는다. test_boundaries.py 의 test_core_에_검사할_파일이_있다 와
    # 같은 이유로 이 가드를 둔다.
    assert _이벤트들(), "로그 이벤트가 0건이다 — data/logs 경로를 확인한다"


def test_모든_로그_호스트가_등록되어_있다():
    미등록 = {e.host for e in _이벤트들()} - set(_호스트들())
    assert not 미등록, f"hosts.json 에 없는 호스트: {sorted(미등록)}"


def test_세_페르소나_모두_기본_limit_이상을_본다():
    """'개수가 k 로 고정된다'는 주장이 성립하려면 각자 k건 이상 볼 수 있어야 한다."""
    호스트 = _호스트들()
    for p in 세_페르소나:
        보이는 = [
            e
            for e in _이벤트들()
            if visible(
                호스트[e.host]["required_clearance"],
                tuple(호스트[e.host]["allowed_departments"]),
                p,
            )
        ]
        assert len(보이는) >= _기본_limit, (
            f"{p.department} 등급{p.clearance} 가 {len(보이는)}건만 본다. "
            f"{_기본_limit}건 미만이면 개수 고정 주장이 성립하지 않는다."
        )


def test_가장_최근_이벤트들이_최고_등급_전용이다():
    """사후 필터링을 잡는 조건이다. 이것이 무너지면 누출 테스트가
    거짓 통과한다 — 시연도 아무것도 보여주지 못한다.
    """
    호스트 = _호스트들()
    최근 = sorted(_이벤트들(), key=lambda e: e.ts, reverse=True)[: _기본_limit + 5]
    개발자 = Principal(department="개발팀", clearance=1)
    보이는_것 = [
        e
        for e in 최근
        if visible(
            호스트[e.host]["required_clearance"],
            tuple(호스트[e.host]["allowed_departments"]),
            개발자,
        )
    ]
    assert not 보이는_것, (
        f"최근 {len(최근)}건 중 {len(보이는_것)}건이 등급1 에게 보인다. "
        "권한 밖 이벤트를 가장 최근으로 심어야 사후 필터링이 잡힌다."
    )


def test_다섯_가지_event_type_이_전부_있다():
    유형 = {e.event_type for e in _이벤트들()}
    assert {"auth_failure", "session_open", "session_close", "privilege_use", "other"} <= 유형

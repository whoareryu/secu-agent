"""도구 로직 — LangChain 도 LLM 도 DB 도 없이 검사한다.

이 파일이 존재할 수 있는 이유가 곧 설계 근거다. LangChain 의 컨텍스트
주입은 컴파일된 그래프를 거쳐야만 동작하므로(실측), 로직이 @tool 래퍼
안에 있으면 단위 테스트할 방법이 없다. 그래서 로직은 core 에 있다.
"""

from datetime import datetime

import pytest

from core.agent.policy import AccessViolation
from core.agent.tools import search_policy
from core.retrieve.hybrid import CANDIDATE_MULTIPLIER
from core.types import EMBEDDING_DIM, LogEvent, PolicyHit, Principal

사원 = Principal(department="개발팀", clearance=1)


def _주체():
    return 사원


def _이벤트(id=1, required_clearance=1, allowed_departments=(), raw="", host="host-01"):
    """LogEvent 를 채워 만드는 지역 헬퍼. 이 파일의 로그 도구 테스트만 쓴다."""
    return LogEvent(
        id=id,
        ts=datetime(2026, 9, 1, 0, 0, 0),
        host=host,
        process="sshd",
        event_type="auth_failure",
        principal_name=None,
        raw=raw,
        severity=None,
        required_clearance=required_clearance,
        allowed_departments=allowed_departments,
    )


class 고정임베더:
    def encode(self, texts, kind):
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class 스텁검색기:
    """받은 principal 을 기록하고, 미리 정해둔 hit 을 돌려준다."""

    def __init__(self, hits: list[PolicyHit]) -> None:
        self.hits = hits
        self.받은_주체: list[Principal] = []
        self.받은_k: list[int] = []

    def by_vector(self, vec, principal, k):
        self.받은_주체.append(principal)
        self.받은_k.append(k)
        return [h.chunk_id for h in self.hits]

    def by_keyword(self, query, principal, k):
        self.받은_주체.append(principal)
        return [h.chunk_id for h in self.hits]

    def load_hits(self, ids, principal):
        self.받은_주체.append(principal)
        by_id = {h.chunk_id: h for h in self.hits}
        return [by_id[i] for i in ids if i in by_id]


def _hit(chunk_id=1, clearance=1, depts=(), code="2.6.1"):
    return PolicyHit(
        chunk_id=chunk_id,
        text=f"본문 {chunk_id}",
        doc_title="ISMS-P 인증기준 안내서",
        clause_code=code,
        required_clearance=clearance,
        allowed_departments=depts,
    )


def test_권한_안의_결과를_그대로_돌려준다():
    검색기 = 스텁검색기([_hit(1), _hit(2)])
    결과 = search_policy("네트워크 접근", 사원, 고정임베더(), 검색기)
    assert [h.chunk_id for h in 결과] == [1, 2]


def test_모든_검색_경로에_같은_주체를_넘긴다():
    """한 경로라도 다른 주체를 쓰면 그쪽으로 누출된다(spec 6.1)."""
    검색기 = 스텁검색기([_hit(1)])
    search_policy("질의", 사원, 고정임베더(), 검색기)
    assert 검색기.받은_주체, "검색기가 한 번도 안 불렸다"
    assert all(p == 사원 for p in 검색기.받은_주체)


def test_권한_밖_항목이_섞이면_예외가_난다():
    """검색기가 고장나 권한 밖 항목을 돌려주면 도구가 터진다.

    조용히 걸러내면 사후 필터링이 되고, 버그가 결과 개수 뒤에 숨는다.
    이 도구가 core.agent.policy.enforce 의 첫 프로덕션 호출자다.
    """
    검색기 = 스텁검색기([_hit(1), _hit(2, clearance=3)])
    with pytest.raises(AccessViolation):
        search_policy("질의", 사원, 고정임베더(), 검색기)


def test_k_를_검색에_전달한다():
    """정확한 값을 본다.

    `n >= 3` 만 보면 search_policy 가 k 를 통째로 무시하고 DEFAULT_K 를
    하드코딩해도 통과한다 — 이 테스트가 지키려던 것이 바로 그 전달이다.
    hybrid.search 가 후보를 k 의 CANDIDATE_MULTIPLIER 배로 잡으므로
    검색기가 받아야 할 값은 그 곱이다.
    """
    검색기 = 스텁검색기([_hit(1)])
    search_policy("질의", 사원, 고정임베더(), 검색기, k=3)
    assert 검색기.받은_k == [3 * CANDIDATE_MULTIPLIER]


def test_결과가_없으면_빈_리스트다():
    """볼 수 있는 것이 없는 것과 규칙이 깨진 것은 다르다."""
    검색기 = 스텁검색기([])
    assert search_policy("질의", 사원, 고정임베더(), 검색기) == []


def test_지나치게_큰_k_는_상한으로_깎인다():
    """모델이 k 를 크게 부르면 검색 한 번이 그만큼 증폭된다.

    hybrid.search 가 후보를 k 의 5배로 잡으므로, 상한이 없으면 허용된
    호출 8번이 각각 증폭된다 — 횟수만 묶고 작업량을 안 묶은 것이다.

    `n <= MAX_K * 5` 는 상한 아래의 아무 값이나 통과시킨다 — k 를 무시하는
    구현도 포함해서다. 깎인 결과가 정확히 MAX_K 인지를 본다.
    """
    from core.agent.policy import MAX_K

    검색기 = 스텁검색기([_hit(1)])
    search_policy("질의", 사원, 고정임베더(), 검색기, k=100000)
    assert 검색기.받은_k == [MAX_K * CANDIDATE_MULTIPLIER]


def test_음수나_0_인_k_도_안전하다():
    """하한은 정확히 1 이다 — 0 도, DEFAULT_K 도 아니다."""
    검색기 = 스텁검색기([_hit(1)])
    search_policy("질의", 사원, 고정임베더(), 검색기, k=0)
    assert 검색기.받은_k == [1 * CANDIDATE_MULTIPLIER]


def test_query_logs_가_limit_을_상한으로_깎는다():
    """모델이 준 값을 믿지 않는다 — search_policy 의 k 와 같은 이유다."""
    from core.agent.policy import MAX_LOG_LIMIT
    from core.agent.tools import query_logs

    받은 = []

    class 검색기:
        def query(self, principal, event_type, since, limit):
            받은.append(limit)
            return []

    query_logs(_주체(), 검색기(), limit=9999)
    assert 받은 == [MAX_LOG_LIMIT], "상한을 정확히 그 값으로 깎아야 한다"

    받은.clear()
    query_logs(_주체(), 검색기(), limit=0)
    assert 받은 == [1], "하한은 1 이다"


def test_권한_밖_이벤트가_섞여_있으면_예외가_난다():
    """조용히 걸러내면 사후 필터링이 되고, 버그가 개수 뒤에 숨는다.
    policy.enforce 가 hits 에 대해 하는 것과 같다.
    """
    from core.agent.policy import AccessViolation
    from core.agent.tools import query_logs

    class 새는검색기:
        def query(self, principal, event_type, since, limit):
            # raw 에 실제 내용을 담는다. 빈 문자열이면 아래 not in 단언이
            # 참·거짓과 무관하게 통과한다 — 스스로 통과하는 단언이 된다.
            return [_이벤트(id=77, required_clearance=3, raw="유령 계정 접속")]

    with pytest.raises(AccessViolation) as e:
        query_logs(Principal(department="개발팀", clearance=1), 새는검색기(), limit=10)
    메시지 = str(e.value)
    assert "77" in 메시지
    assert "유령" not in 메시지, "raw 본문이 예외 메시지에 담기면 안 된다"


def test_예외_메시지에_raw_도_호스트도_담기지_않는다():
    """AccessViolation 이 chunk_id 만 담는 것과 같은 원칙이다 —
    기록이나 오류가 우회 경로가 되면 안 된다.
    """
    from core.agent.policy import AccessViolation, enforce_events

    with pytest.raises(AccessViolation) as e:
        enforce_events([_이벤트(id=42, required_clearance=3, raw="비밀 내용", host="exec-fs-01")],
                       Principal(department="개발팀", clearance=1))
    메시지 = str(e.value)
    assert "42" in 메시지
    assert "비밀 내용" not in 메시지
    assert "exec-fs-01" not in 메시지

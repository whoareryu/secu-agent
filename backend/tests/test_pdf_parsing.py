import pytest

from adapters.parsing.pdf import chunk_clauses, split_clauses
from core.types import Chunk, Clause

# 실제 ISMS-P 안내서의 구조를 본뜬 텍스트.
# 조항 코드가 줄 앞에 오고, 본문이 뒤따르며, 조항 밖 텍스트(머리말)도 있다.
샘플 = """정보보호 및 개인정보보호 관리체계 인증기준 안내서

1.3.1 보호대책 구현
선정된 보호대책은 이행계획에 따라 효과적으로 구현하고, 이행 결과의
정확성 및 효과성 여부를 확인하여야 한다.

1.3.2 보호대책 공유
보호대책의 실제 운영 또는 시행할 부서 및 담당자를 파악하여 관련 내용을
공유하여야 한다.

2.6.1 네트워크 접근
네트워크에 대한 비인가 접근을 통제하기 위하여 네트워크 접근 통제
정책을 수립하고 이행하여야 한다.

2.11.3 이상행위 분석 및 모니터링
내외부에 의한 침해시도, 개인정보유출 시도, 부정행위 등 이상행위를
탐지할 수 있도록 주요 정보시스템, 응용프로그램, 네트워크, 보안시스템
등에서 발생한 네트워크 트래픽, 데이터 흐름, 이벤트 로그 등을 수집하여
분석 및 모니터링하여야 한다.
"""


def test_조항_코드로_분할한다():
    clauses = split_clauses(샘플)
    assert [c.code for c in clauses] == ["1.3.1", "1.3.2", "2.6.1", "2.11.3"]


def test_절_번호가_두_자리인_조항도_잡는다():
    # 정규식을 \d\.\d\.\d+ 로 쓰면 2.10·2.11·2.12 가 통째로 사라진다.
    # 실측에서 그렇게 16개를 잃었고, 그 안에 이 조항이 있었다.
    by_code = {c.code: c for c in split_clauses(샘플)}
    assert "2.11.3" in by_code
    assert by_code["2.11.3"].title == "이상행위 분석 및 모니터링"


def test_조항_제목을_뽑는다():
    by_code = {c.code: c for c in split_clauses(샘플)}
    assert by_code["1.3.1"].title == "보호대책 구현"
    assert by_code["2.6.1"].title == "네트워크 접근"


def test_조항_본문에_다음_조항이_섞이지_않는다():
    # 경계를 잘못 잡으면 인용이 엉뚱한 조항을 가리킨다.
    by_code = {c.code: c for c in split_clauses(샘플)}
    assert "보호대책 공유" not in by_code["1.3.1"].text
    assert "효과적으로 구현" in by_code["1.3.1"].text


def test_조항_앞_머리말은_버린다():
    # 표지·목차는 조항이 아니다.
    clauses = split_clauses(샘플)
    assert all("안내서" not in c.text or c.code.startswith("1.3") for c in clauses)


def test_조항이_없는_텍스트는_빈_리스트다():
    assert split_clauses("조항 코드가 하나도 없는 평범한 문단.") == []


# 실제 ISMS-P 안내서는 모든 조항 코드가 목차(제목만, 본문 거의 없음)와
# 본문(실제 조항 내용)에 각각 한 번씩 나온다. 실물에서는 목차가 항상
# 본문보다 먼저 오지만, 그 순서에 우연히 의존하는 구현("마지막 매치가
# 이긴다")도 "긴 본문이 이긴다"는 규칙과 똑같은 결과를 낼 수 있다.
# 그래서 두 코드를 반대 순서로 둔다 — 1.3.2 는 긴 본문이 먼저, 짧은
# 목차 항목이 나중에 오고, 1.3.1 은 그 반대다. "긴 쪽이 이긴다"만
# 두 경우 모두를 통과시킨다.
중복_샘플 = """1.3.2 보호대책 공유
보호대책의 실제 운영 또는 시행할 부서 및 담당자를 파악하여 관련 내용을
공유하여야 한다.

1.3.2 보호대책 공유

차례

1.3.1 보호대책 구현

본문

1.3.1 보호대책 구현
선정된 보호대책은 이행계획에 따라 효과적으로 구현하고, 이행 결과의
정확성 및 효과성 여부를 확인하여야 한다.
"""


def test_중복된_조항_코드는_등장_순서와_무관하게_본문이_긴_쪽이_이긴다():
    # 1.3.2: 긴 본문이 먼저, 짧은 목차 항목("차례")이 나중에 온다 —
    # "마지막 매치가 이긴다"로 구현하면 여기서 틀린다.
    # 1.3.1: 짧은 목차 항목("본문")이 먼저, 긴 본문이 나중에 온다 —
    # "첫 매치가 이긴다"로 구현하면 여기서 틀린다.
    clauses = split_clauses(중복_샘플)
    codes = [c.code for c in clauses]
    assert codes.count("1.3.1") == 1
    assert codes.count("1.3.2") == 1
    by_code = {c.code: c for c in clauses}
    assert "보호대책의 실제 운영" in by_code["1.3.2"].text
    assert by_code["1.3.2"].text != "차례"
    assert "선정된 보호대책은" in by_code["1.3.1"].text
    assert by_code["1.3.1"].text != "본문"


# 실제 ISMS-P 안내서는 마지막 조항(3.5.3) 바로 뒤에 "참고자료(가나다 순)"
# 표지로 시작하는 참고문헌 목록이 붙는다. 다음 조항 코드가 없으므로 표지를
# 찾지 못하면 그 목록까지 본문으로 삼켜, 3.5.3 인용이 규정이 아니라
# 참고문헌 제목을 인용하게 된다.
후주_샘플 = """3.5.3 이용내역 통지
개인정보처리자는 정보주체에게 개인정보 이용내역을 통지하여야 한다.

참고자료(가나다 순)
 가명정보 처리 가이드라인
 개인정보 손해배상책임 보장제도 안내서
"""


def test_마지막_조항_뒤_참고자료_목록은_본문에서_제외한다():
    clauses = split_clauses(후주_샘플)
    by_code = {c.code: c for c in clauses}
    assert "이용내역을 통지하여야" in by_code["3.5.3"].text
    assert "가명정보 처리 가이드라인" not in by_code["3.5.3"].text


def test_청크가_조항_코드를_들고_다닌다():
    chunks = chunk_clauses(split_clauses(샘플))
    assert all(isinstance(c, Chunk) for c in chunks)
    assert {c.clause_code for c in chunks} == {"1.3.1", "1.3.2", "2.6.1", "2.11.3"}


def test_짧은_조항은_청크_하나다():
    chunks = chunk_clauses([Clause(code="9.9.9", title="짧음", text="한 문장.")])
    assert len(chunks) == 1
    assert chunks[0].ordinal == 0


def test_긴_조항은_여러_청크로_쪼개진다():
    긴본문 = "가나다라마바사아자차카타파하 " * 200   # 약 2,800자
    chunks = chunk_clauses([Clause(code="9.9.9", title="김", text=긴본문)], max_chars=900)
    assert len(chunks) > 1
    assert all(len(c.text) <= 900 for c in chunks)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_청크가_겹쳐진다():
    # 문장이 청크 경계에서 잘리면 그 문장은 어느 쪽에서도 검색되지 않는다.
    긴본문 = "".join(f"{i}번째문장. " for i in range(300))
    chunks = chunk_clauses([Clause(code="9.9.9", title="김", text=긴본문)],
                           max_chars=500, overlap=100)
    assert len(chunks) >= 2
    # 앞 청크의 끝부분이 뒤 청크의 앞부분에 나타난다
    assert chunks[0].text[-50:] in chunks[1].text


def test_overlap가_max_chars_이상이면_예외를_던진다():
    # step = max_chars - overlap 가 0 이하면 시작 위치가 전진하지 않아
    # while 루프가 끝나지 않는다.
    with pytest.raises(ValueError):
        chunk_clauses(
            [Clause(code="9.9.9", title="김", text="가" * 5000)],
            max_chars=100,
            overlap=100,
        )

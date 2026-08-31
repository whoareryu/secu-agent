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

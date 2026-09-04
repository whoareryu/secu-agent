"""확장자 → 파서 디스패치. DB 도 모델도 필요 없다.

이 파일은 테스트가 하나도 없었다. 파이프라인의 **입구**인데, 여기서
갈라지는 세 갈래(pdf · md · 그 밖)가 전부 검증되지 않았다.

특히 조용한 실패가 나올 자리다 — 지원하지 않는 포맷을 예외 없이 넘기면
적재가 끝난 뒤에야 문서가 없다는 것을 안다. 모듈 독스트링이 그 이유를
적어 뒀는데, 그 결정을 지키는 테스트가 없었다.
"""

from pathlib import Path

import pytest

from adapters.parsing.loader import load, load_meta

_머리말 = """---
title: 시험용 규정
clearance: 2
departments: [개발팀]
---

## 1.1.1 첫 조항

첫 조항 본문이다.

## 1.1.2 둘째 조항

둘째 조항 본문이다.
"""


def test_md_는_조항과_청크로_갈린다(tmp_path: Path):
    p = tmp_path / "a.md"
    p.write_text(_머리말, encoding="utf-8")

    조항, 청크 = load(p)

    assert [c.code for c in 조항] == ["1.1.1", "1.1.2"]
    assert len(청크) == 2
    assert all(k.text.strip() for k in 청크), "빈 청크를 만들지 않는다"


def test_md_의_머리말이_메타로_읽힌다(tmp_path: Path):
    p = tmp_path / "a.md"
    p.write_text(_머리말, encoding="utf-8")

    메타 = load_meta(p)

    assert 메타["title"] == "시험용 규정"
    assert int(메타["clearance"]) == 2


def test_pdf_의_메타는_빈_딕셔너리다(tmp_path: Path):
    """PDF 는 스스로 권한을 들고 있지 않다 — 적재하는 사람이 CLI 로 준다.

    None 이 아니라 빈 딕셔너리인 것이 계약이다. pipeline/cli.py 의
    ingest-dir 이 `meta["title"]` 로 바로 꺼내므로, None 을 주면 그 자리가
    TypeError 가 된다.
    """
    assert load_meta(tmp_path / "없어도-된다.pdf") == {}


@pytest.mark.parametrize("이름", ["a.docx", "a.txt", "a.hwp", "a"])
def test_지원하지_않는_포맷은_예외다(tmp_path: Path, 이름: str):
    """조용히 건너뛰지 않는다. 넘기면 적재가 끝난 뒤에야 문서가 없다는 것을 안다.

    `.docx` 를 여기 넣어둔 이유가 있다 — db/schema.sql 의 doc_type CHECK 는
    'docx' 를 허용하는데 이 로더는 거부한다. 둘이 어긋나 있고, 어긋남을
    해소하는 쪽은 스키마가 아니라 이 예외다(DOCX 는 아직 범위 밖이다).
    """
    with pytest.raises(ValueError, match="지원하지 않는"):
        load(tmp_path / 이름)


def test_확장자_대문자도_같게_다룬다(tmp_path: Path):
    """`.MD` 로 저장된 파일이 지원하지 않는 포맷으로 떨어지면 안 된다."""
    p = tmp_path / "a.MD"
    p.write_text(_머리말, encoding="utf-8")

    조항, _ = load(p)

    assert [c.code for c in 조항] == ["1.1.1", "1.1.2"]
    assert load_meta(p)["title"] == "시험용 규정"

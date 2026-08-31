from eval.golden import DEFAULT_PATH, load


def test_골든셋이_서른_건이다():
    qs = load(DEFAULT_PATH)
    assert len(qs) == 30


def test_모든_질의가_정답_조항을_갖는다():
    # 정답이 빈 건이 있으면 그 건의 지표가 조용히 0 이 되어 평균을 끌어내린다.
    assert all(q.relevant for q in load(DEFAULT_PATH))


def test_질의가_조항_제목을_그대로_베끼지_않는다():
    """제목을 베끼면 키워드 검색이 지나치게 잘 맞아 지표가 부푼다."""
    베낀_제목 = {"네트워크 접근", "사용자 계정 관리", "이상행위 분석 및 모니터링"}
    for q in load(DEFAULT_PATH):
        assert q.query not in 베낀_제목


def test_권한이_필요한_질의가_섞여_있다():
    # 전부 전사 공개면 하네스가 principal 을 무시해도 지표가 같다.
    qs = load(DEFAULT_PATH)
    assert any(q.principal.clearance > 1 for q in qs)
    assert any(q.principal.department != "개발팀" for q in qs)

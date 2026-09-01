"""로그 적재.

미등록 호스트를 **거부한다** — 조용히 넘기지 않는다. 적재 시점에 시끄럽게
막는 것이 첫 번째 방어선이고, 조회 시점의 INNER JOIN 이 두 번째다
(보충 spec 3.2). 둘 다 필요하다.
"""

import pytest

from pipeline.ingest_logs import MissingHost, ingest_logs

pytestmark = pytest.mark.db


def test_미등록_호스트가_있으면_거부한다(db연결, tmp_path):
    로그 = tmp_path / "a.log"
    로그.write_text(
        "Sep  1 03:14:22 unknown-99 sshd[1]: Failed password for invalid user x "
        "from 1.2.3.4 port 1 ssh2\n",
        encoding="utf-8",
    )
    with db연결.cursor() as cur:
        cur.execute("TRUNCATE log_events RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE hosts RESTART IDENTITY CASCADE")
    db연결.commit()

    with pytest.raises(MissingHost, match="unknown-99"):
        ingest_logs(로그, year=2026, conn=db연결)


def test_거부하면_한_줄도_들어가지_않는다(db연결, tmp_path):
    """부분 적재가 되면 어디까지 들어갔는지 모른다."""
    로그 = tmp_path / "b.log"
    로그.write_text(
        "Sep  1 03:00:00 open-01 sshd[1]: Accepted publickey for a from 1.2.3.4 port 1 ssh2\n"
        "Sep  1 03:01:00 unknown-99 sshd[2]: Accepted publickey for b from 1.2.3.4 port 2 ssh2\n",
        encoding="utf-8",
    )
    with db연결.cursor() as cur:
        cur.execute("TRUNCATE log_events RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE hosts RESTART IDENTITY CASCADE")
        cur.execute(
            "INSERT INTO hosts (name, department, required_clearance) VALUES ('open-01','개발팀',1)"
        )
    db연결.commit()

    with pytest.raises(MissingHost):
        ingest_logs(로그, year=2026, conn=db연결)

    with db연결.cursor() as cur:
        cur.execute("SELECT count(*) FROM log_events")
        assert cur.fetchone()[0] == 0, "거부했는데 일부가 들어갔다"


def test_등록된_호스트만_있으면_적재한다(db연결, tmp_path):
    로그 = tmp_path / "c.log"
    로그.write_text(
        "Sep  1 03:00:00 open-01 sshd[1]: Accepted publickey for a from 1.2.3.4 port 1 ssh2\n"
        "알아볼 수 없는 줄\n"
        "Sep  1 03:01:00 open-01 sshd[2]: Failed password for invalid user b "
        "from 1.2.3.4 port 2 ssh2\n",
        encoding="utf-8",
    )
    with db연결.cursor() as cur:
        cur.execute("TRUNCATE log_events RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE hosts RESTART IDENTITY CASCADE")
        cur.execute(
            "INSERT INTO hosts (name, department, required_clearance) VALUES ('open-01','개발팀',1)"
        )
    db연결.commit()

    결과 = ingest_logs(로그, year=2026, conn=db연결)
    assert 결과.적재 == 2
    assert 결과.건너뜀 == 1, "파싱 안 되는 줄은 세어서 보고한다 — 조용히 버리지 않는다"


def test_두_번_적재해도_중복되지_않는다(db연결, tmp_path):
    """같은 파일을 다시 돌리는 일은 실제로 일어난다."""
    로그 = tmp_path / "d.log"
    로그.write_text(
        "Sep  1 03:00:00 open-01 sshd[1]: Accepted publickey for a from 1.2.3.4 port 1 ssh2\n",
        encoding="utf-8",
    )
    with db연결.cursor() as cur:
        cur.execute("TRUNCATE log_events RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE hosts RESTART IDENTITY CASCADE")
        cur.execute(
            "INSERT INTO hosts (name, department, required_clearance) VALUES ('open-01','개발팀',1)"
        )
    db연결.commit()

    ingest_logs(로그, year=2026, conn=db연결)
    ingest_logs(로그, year=2026, conn=db연결)

    with db연결.cursor() as cur:
        cur.execute("SELECT count(*) FROM log_events")
        assert cur.fetchone()[0] == 1

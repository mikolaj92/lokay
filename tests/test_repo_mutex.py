"""Hermetic tests for lokay.proc.repo_mutex (fixture ps text only)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from lokay.proc import repo_mutex

PID_CMD = """\
  14201 pi -p implement https://github.com/mikolaj92/lokay/issues/12 --approve --no-session
  14202 pi -p implement /Users/x/worktrees/mikolaj92__heimdall/ai__fix__3 --approve
  15000 python -m pytest tests/test_lokay.py
  15001 /opt/homebrew/bin/pi --cwd /Users/x/worktrees/acme__web/ai__fix__1 -p x
  15002 grep pi mikolaj92/lokay
  15003 pip install pi
  15004 /usr/local/bin/pihole
"""

AUX = """\
USER               PID  %CPU %MEM      VSZ    RSS   TT  STAT STARTED      TIME COMMAND
mikomac          22101   1.2  0.4 410012345  54321   ??  S     3:02PM   0:12.34 pi -p https://github.com/mikolaj92/lokay/issues/1 --approve
mikomac          22102   0.0  0.1 410000001   4321   ??  S     3:01PM   0:00.01 python -m lokay.proc.repo_mutex --repo mikolaj92/lokay
root                 1   0.0  0.0   167000  12000   ??  Ss    Aug12     0:02.00 /sbin/init
"""

TWO = """\
  31001 pi --cwd /wt/mikolaj92__lokay/ai__fix__8 -p one
  31002 /usr/local/bin/pi -p https://github.com/mikolaj92/lokay/issues/9
  31003 pi -p other /Users/x/worktrees/mikolaj92__heimdall/branch
"""

PREFIX = """\
  41001 pi -p https://github.com/mikolaj92/lokay-web/issues/4 --approve
  41002 pi --cwd /wt/mikolaj92__lokay-web/ai__fix__4 -p x
"""

ISSUE_TO_PR = """\
  42001 /opt/homebrew/bin/python -u -m lokay.compose.issue_to_pr --live --repo mikolaj92/lokay --issue 190
  42002 /opt/homebrew/bin/python -u -m lokay.compose.issue_to_pr --live --repo acme/other --issue 12
"""


def _gh_state(state: str):
    return type("Completed", (), {"returncode": 0, "stdout": f"{state}\n"})()


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_idle_when_empty():
    out = repo_mutex.inspect_mutex(repo="mikolaj92/lokay", ps_text="")
    assert out == {"ok": True, "busy": False}


def test_idle_when_header_only():
    out = repo_mutex.inspect_mutex(
        repo="mikolaj92/lokay",
        ps_text="  PID COMMAND\n",
    )
    assert out["ok"] is True
    assert out["busy"] is False
    assert "pids" not in out


def test_busy_when_github_url_in_pi_argv():
    out = repo_mutex.inspect_mutex(repo="mikolaj92/lokay", ps_text=PID_CMD)
    assert out == {"ok": True, "busy": True, "pids": [14201]}


def test_busy_when_worktree_owner_dunder_name():
    out = repo_mutex.inspect_mutex(repo="mikolaj92/heimdall", ps_text=PID_CMD)
    assert out == {"ok": True, "busy": True, "pids": [14202]}


def test_other_repo_is_idle():
    out = repo_mutex.inspect_mutex(repo="acme/other", ps_text=PID_CMD)
    assert out == {"ok": True, "busy": False}


def test_busy_when_live_issue_to_pr_has_repo_argument():
    with patch("lokay.proc.repo_mutex.subprocess.run", return_value=_gh_state("OPEN")):
        out = repo_mutex.inspect_mutex(repo="mikolaj92/lokay", ps_text=ISSUE_TO_PR)
    assert out == {"ok": True, "busy": True, "pids": [42001]}


def test_closed_issue_to_pr_does_not_hold_repo_mutex():
    with patch("lokay.proc.repo_mutex.subprocess.run", return_value=_gh_state("CLOSED")) as run:
        out = repo_mutex.inspect_mutex(repo="mikolaj92/lokay", ps_text=ISSUE_TO_PR)
    assert out == {"ok": True, "busy": False}
    run.assert_called_once()


def test_issue_to_pr_for_other_repo_is_idle():
    with patch("lokay.proc.repo_mutex.subprocess.run", return_value=_gh_state("OPEN")):
        out = repo_mutex.inspect_mutex(repo="acme/other", ps_text=ISSUE_TO_PR)
        assert out == {"ok": True, "busy": True, "pids": [42002]}
        out = repo_mutex.inspect_mutex(repo="mikolaj92/lokay", ps_text=ISSUE_TO_PR.splitlines()[1])
    assert out == {"ok": True, "busy": False}


def test_issue_to_pr_status_failure_keeps_mutex_busy():
    failed = type("Completed", (), {"returncode": 1, "stdout": ""})()
    with patch("lokay.proc.repo_mutex.subprocess.run", return_value=failed):
        out = repo_mutex.inspect_mutex(repo="mikolaj92/lokay", ps_text=ISSUE_TO_PR)
    assert out == {"ok": True, "busy": True, "pids": [42001]}


def test_quoted_fixture_repo_in_pi_prompt_is_not_busy():
    # A coding-slot prompt that quotes test JSON ("a/one") must not lock a/one.
    out = repo_mutex.inspect_mutex(
        repo="a/one",
        ps_text='  74431 pi -p Goal: ... working={"prs_by_repo": {"a/one": [{"number": 69}]}}\n',
    )
    assert out == {"ok": True, "busy": False}
    live = repo_mutex.inspect_mutex(
        repo="mikolaj92/lokay",
        ps_text="  74431 pi -p Goal: ... Repository: mikolaj92/lokay Issue: #135\n",
    )
    assert live == {"ok": True, "busy": True, "pids": [74431]}


def test_non_pi_mention_is_not_busy():
    # grep/python/pip/pihole mention strings but argv0 is not pi.
    out = repo_mutex.inspect_mutex(repo="mikolaj92/lokay", ps_text="\n".join(PID_CMD.splitlines()[2:]))
    assert out["busy"] is False


def test_full_path_pi_matches_worktree():
    out = repo_mutex.inspect_mutex(repo="acme/web", ps_text=PID_CMD)
    assert out == {"ok": True, "busy": True, "pids": [15001]}


def test_prefix_repo_does_not_match():
    idle = repo_mutex.inspect_mutex(repo="mikolaj92/lokay", ps_text=PREFIX)
    assert idle == {"ok": True, "busy": False}
    busy = repo_mutex.inspect_mutex(repo="mikolaj92/lokay-web", ps_text=PREFIX)
    assert busy["busy"] is True
    assert busy["pids"] == [41001, 41002]


def test_multiple_pi_pids_sorted():
    out = repo_mutex.inspect_mutex(repo="mikolaj92/lokay", ps_text=TWO)
    assert out == {"ok": True, "busy": True, "pids": [31001, 31002]}


def test_ps_aux_header_format():
    out = repo_mutex.inspect_mutex(repo="mikolaj92/lokay", ps_text=AUX)
    assert out == {"ok": True, "busy": True, "pids": [22101]}


def test_invalid_repo_fails_closed():
    try:
        repo_mutex.inspect_mutex(repo="not-a-repo", ps_text="")
    except ValueError as exc:
        assert "owner/name" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_cli_ps_file_idle(tmp_path: Path, capsys):
    ps_file = tmp_path / "ps.txt"
    ps_file.write_text("  PID COMMAND\n  1 /sbin/init\n", encoding="utf-8")
    code = repo_mutex.main(
        ["--repo", "mikolaj92/lokay", "--ps-file", str(ps_file)]
    )
    assert code == 0
    assert _payload(capsys) == {"ok": True, "busy": False}


def test_cli_ps_file_busy(tmp_path: Path, capsys):
    ps_file = tmp_path / "ps.txt"
    ps_file.write_text(PID_CMD, encoding="utf-8")
    code = repo_mutex.main(
        ["--repo", "mikolaj92/lokay", "--ps-file", str(ps_file)]
    )
    assert code == 0
    assert _payload(capsys) == {"ok": True, "busy": True, "pids": [14201]}


def test_cli_missing_ps_file_fails_closed(tmp_path: Path, capsys):
    missing = tmp_path / "absent.txt"
    code = repo_mutex.main(
        ["--repo", "mikolaj92/lokay", "--ps-file", str(missing)]
    )
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert "not found" in payload["error"]


def test_cli_invalid_repo_fails_closed(tmp_path: Path, capsys):
    ps_file = tmp_path / "ps.txt"
    ps_file.write_text("", encoding="utf-8")
    code = repo_mutex.main(["--repo", "lokay", "--ps-file", str(ps_file)])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert "owner/name" in payload["error"]

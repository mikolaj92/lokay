"""Negative audit findings: harvest switches main; next pass reseeds ready."""
from lokay.git_host_ff import fast_forward_origin_main
from lokay.proc.record_pass import _issues_leftover_remaining
from lokay.proc.walk_issue_leftover import queue
from lokay.runner import Runner
from test_host_ff import _pair, _git


def test_harvest_at_current_sha_still_switches_main(tmp_path):
    _, host = _pair(tmp_path)
    _git(host, "checkout", "-b", "ai/fix/harvest")
    (host / ".lokay" / "approach.md").write_text("harvest debris")
    result = fast_forward_origin_main(Runner(), host)
    assert result["already_current"] is True
    assert _git(host, "branch", "--show-current").stdout.strip() == "main"


def test_exhausted_pass_drops_snapshot_and_next_pass_admits_new_ready():
    remaining = _issues_leftover_remaining(
        {"result": {"leftover": 0, "leftover_issues": []}},
        {"leftover": 1, "leftover_issues": [{"repo": "o/r", "issue": 1}]},
        working={"occupied_repos": []},
    )
    assert "leftover_issues" not in remaining
    fresh = {"repo": "o/r", "issue": 2, "labels": ["ai:ready"], "assignees": []}
    assert queue([fresh], remaining, lokay="mikolaj92") == [fresh]

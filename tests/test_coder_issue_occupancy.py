"""Orphan-coder occupancy matches one ticket, not a prefix of another."""

from lokay.proc.issue_delivery_process import _coder_command_matches_issue


def test_issue_3_does_not_match_live_issue_39():
    live = "pi -p Goal: implement GitHub issue #39 in this worktree"
    assert _coder_command_matches_issue(live, 39)
    assert not _coder_command_matches_issue(live, 3)
    assert not _coder_command_matches_issue(live, 9)
    assert not _coder_command_matches_issue("", 39)

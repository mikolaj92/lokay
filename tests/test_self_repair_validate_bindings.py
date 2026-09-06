"""Exercise real bindings for the authored self-repair base selector."""

import pytest

from lokay.organ.self_repair_validate_boundary import handle_self_repair_validate


@pytest.mark.parametrize("base, route", [("abc123", "has_base"), ("", "no_base")])
def test_committed_need_preserves_candidate(base, route):
    candidate = {"ok": True, "worktree": "/tmp/candidate", "base_sha": base}
    result = handle_self_repair_validate(
        "select_self_repair_committed_need", {},
        {"check_self_repair_tracked_cached": candidate}, {},
    )
    assert result == {**candidate, "route": route}


def test_committed_check_reads_its_direct_graph_predecessor(tmp_path):
    import subprocess

    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()

    git("init", "-q")
    git("-c", "user.name=Test", "-c", "user.email=test@example.test",
        "commit", "--allow-empty", "-qm", "base")
    candidate = {"ok": True, "worktree": str(tmp_path), "base_sha": git("rev-parse", "HEAD")}
    result = handle_self_repair_validate(
        "check_self_repair_tracked_committed", {},
        {"select_self_repair_committed_need": candidate}, {},
    )
    assert result == {**candidate, "route": "valid", "error": ""}

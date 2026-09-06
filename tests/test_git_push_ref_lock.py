"""#1016: push retries ref-lock races; summarize never lies repaired without push."""

from __future__ import annotations

from lokay.git_push import is_ref_lock_error, push_branch
from lokay.proc.summarize_pr_repair import summarize
from lokay.runner import CommandResult, CommandSpec


class _FakeRunner:
    def __init__(self, outcomes: list[object]):
        self.outcomes = list(outcomes)
        self.calls = 0

    def run(self, spec, *, live: bool):
        return CommandResult(spec=spec, executed=True, returncode=0, stdout="deadbeef\n")

    def run_checked(self, spec, *, live: bool):
        self.calls += 1
        next_out = self.outcomes.pop(0)
        if isinstance(next_out, Exception):
            raise next_out
        return next_out


def test_is_ref_lock_error_detects_common_markers():
    assert is_ref_lock_error("error: cannot lock ref 'refs/heads/ai/fix/1'")
    assert is_ref_lock_error("fatal: Unable to create '/tmp/repo/.git/refs/heads/x.lock': File exists")
    assert not is_ref_lock_error("rejected (fetch first)")


def test_push_retries_ref_lock_then_succeeds():
    sleeps: list[float] = []
    lock = RuntimeError("fatal: cannot lock ref 'refs/heads/ai/fix/1': File exists")
    ok = CommandResult(
        spec=CommandSpec(argv=("git", "push")),
        executed=True,
        returncode=0,
    )
    runner = _FakeRunner([lock, ok])
    out = push_branch(
        runner,  # type: ignore[arg-type]
        __import__("pathlib").Path("/tmp/wt"),
        "ai/fix/1",
        live=True,
        attempts=3,
        sleep_fn=sleeps.append,
        sleep_seconds=0.1,
    )
    assert out["ok"] is True
    assert out["attempts"] == 2
    assert out["head_sha"] == "deadbeef"
    assert sleeps == [0.1]


def test_push_fail_closed_after_ref_lock_budget():
    lock = RuntimeError("error: cannot lock ref 'refs/heads/x'")
    runner = _FakeRunner([lock, lock, lock])
    out = push_branch(
        runner,  # type: ignore[arg-type]
        __import__("pathlib").Path("/tmp/wt"),
        "ai/fix/1",
        live=True,
        attempts=3,
        sleep_fn=lambda _s: None,
    )
    assert out["ok"] is False
    assert out["reason"] == "ref_lock"
    assert out["attempts"] == 3


def test_summarize_pr_repair_not_repaired_when_push_fails():
    out = summarize(
        final={"route": "publish"},
        push={"ok": False, "reason": "ref_lock", "error": "cannot lock ref"},
        repo="a/b",
        pr=9,
        branch="ai/fix/9",
    )
    assert out["ok"] is False
    assert out["result"]["repaired"] is False
    assert out["result"]["reason"] == "ref_lock"


def test_summarize_pr_repair_published_with_head_sha():
    out = summarize(
        final={"route": "publish"},
        push={"ok": True, "head_sha": "abc"},
        repo="a/b",
        pr=9,
        branch="ai/fix/9",
    )
    assert out["ok"] is True
    assert out["result"]["repaired"] is True
    assert out["result"]["head_sha"] == "abc"

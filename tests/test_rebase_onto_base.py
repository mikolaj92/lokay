"""rebase_onto_base: replay onto origin/main or fail closed. Never force-push."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from lokay.git_rebase import RebaseConflict, RebaseError, rebase_onto_base
from lokay.proc import rebase_onto_base as rebase_proc
from lokay.safety import SafetyError, validate_argv


def _result(argv, *, returncode=0, stdout="", stderr=""):
    return SimpleNamespace(
        spec=SimpleNamespace(argv=tuple(argv)),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class _RebaseRunner:
    def __init__(
        self,
        *,
        behind: str = "1",
        behind_rc: int = 0,
        rebase_rc: int = 0,
        fetch_rc: int = 0,
    ) -> None:
        self.behind = behind
        self.behind_rc = behind_rc
        self.rebase_rc = rebase_rc
        self.fetch_rc = fetch_rc
        self.calls: list[list[str]] = []

    def run(self, spec, *, live):
        argv = list(spec.argv)
        self.calls.append(argv)
        if argv[1:3] == ["fetch", "origin"]:
            return _result(argv, returncode=self.fetch_rc, stderr="fetch failed" if self.fetch_rc else "")
        if argv[1:3] == ["rev-list", "--count"] and str(argv[3]).startswith("HEAD..origin/"):
            return _result(argv, returncode=self.behind_rc, stdout=self.behind + "\n")
        if argv[1:2] == ["rebase"] and "--abort" not in argv:
            return _result(
                argv,
                returncode=self.rebase_rc,
                stderr="CONFLICT (content): merge conflict" if self.rebase_rc else "",
            )
        if argv[1:3] == ["rebase", "--abort"]:
            return _result(argv)
        return _result(argv)

    def run_checked(self, spec, *, live):
        result = self.run(spec, live=live)
        if result.returncode != 0:
            raise RuntimeError(f"command failed: {spec.argv}")
        return result


def test_planned_when_not_live(tmp_path):
    runner = _RebaseRunner()
    out = rebase_onto_base(runner, tmp_path, live=False)
    assert out["planned"] is True
    assert out["rebased"] is False
    assert runner.calls == []


def test_already_current_skips_rebase(tmp_path):
    runner = _RebaseRunner(behind="0")
    out = rebase_onto_base(runner, tmp_path, live=True)
    assert out["already_current"] is True
    assert out["rebased"] is False
    assert any(call[1:3] == ["fetch", "origin"] for call in runner.calls)
    assert not any(call[1] == "rebase" for call in runner.calls)


def test_behind_replays_onto_origin_main(tmp_path):
    runner = _RebaseRunner(behind="2")
    out = rebase_onto_base(runner, tmp_path, live=True)
    assert out["rebased"] is True
    assert out["behind"] == 2
    assert ["git", "rebase", "origin/main"] in runner.calls
    assert not any("--force" in call or "-f" in call for call in runner.calls)


def test_conflict_aborts_and_raises(tmp_path):
    runner = _RebaseRunner(behind="1", rebase_rc=1)
    with pytest.raises(RebaseConflict) as caught:
        rebase_onto_base(runner, tmp_path, live=True)
    assert caught.value.reason == "rebase_conflict"
    assert ["git", "rebase", "--abort"] in runner.calls


def test_fetch_failure_is_fail_closed(tmp_path):
    runner = _RebaseRunner(fetch_rc=128)
    with pytest.raises(RebaseError) as caught:
        rebase_onto_base(runner, tmp_path, live=True)
    assert caught.value.reason == "fetch_failed"
    assert not any(call[1] == "rebase" for call in runner.calls)


def test_unreadable_behind_is_fail_closed(tmp_path):
    runner = _RebaseRunner(behind="", behind_rc=128)
    with pytest.raises(RebaseError) as caught:
        rebase_onto_base(runner, tmp_path, live=True)
    assert caught.value.reason == "rebase_behind_unreadable"


def test_safety_still_forbids_force_push():
    with pytest.raises(SafetyError):
        validate_argv(["git", "push", "--force", "origin", "ai/fix/1-x"])
    validate_argv(["git", "rebase", "origin/main"])




def test_cli_factory_repo_still_rebases(tmp_path, monkeypatch, capsys):
    sentinel_runner = object()
    calls = []
    monkeypatch.setattr(rebase_proc, "runner", lambda: sentinel_runner)

    def record_rebase(run, worktree, *, live, base):
        calls.append((run, worktree, live, base))
        return {"planned": True, "rebased": False}

    monkeypatch.setattr(rebase_proc, "rebase_onto_base", record_rebase)

    assert rebase_proc.main(
        ["--repo", "mikolaj92/lokay", "--worktree", str(tmp_path)]
    ) == 0
    assert calls == [(sentinel_runner, tmp_path, False, "main")]
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "repo": "mikolaj92/lokay",
        "worktree": str(tmp_path),
        "planned": True,
        "rebased": False,
    }


def test_cli_conflict_maps_reason(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""
mode: live
github:
  assignee: t
  ready_label: ai:ready
  blocked_label: ai:blocked
  branch_prefix: ai/fix
  pr_labels: [ai:generated]
repos:
  - name: owner/repo
    clone_path: {tmp_path / "clone"}
executor:
  enabled: false
  agent: grok
merge:
  enabled: false
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(rebase_proc, "mutations_allowed", lambda **kw: True)

    def boom(*_a, **_kw):
        raise RebaseConflict("both modified src/x.py")

    monkeypatch.setattr(rebase_proc, "rebase_onto_base", boom)
    code = rebase_proc.main(
        [
            "--repo",
            "mikolaj92/lokay",
            "--worktree",
            str(tmp_path),
            "--live",
            "--config",
            str(cfg),
        ]
    )
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert code == 1
    assert payload["ok"] is False
    assert payload["reason"] == "rebase_conflict"

from __future__ import annotations

import json

import pytest

from lokay.proc import push_branch




def test_lokay_repo_still_pushes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sentinel_runner = object()
    calls: list[tuple[object, object, str, bool]] = []
    monkeypatch.setattr(push_branch, "runner", lambda: sentinel_runner)

    def record_push(run: object, worktree, branch: str, *, live: bool) -> None:
        calls.append((run, worktree, branch, live))

    monkeypatch.setattr(push_branch, "push_branch", record_push)

    assert (
        push_branch.main(
            [
                "--repo",
                "mikolaj92/lokay",
                "--worktree",
                str(tmp_path),
                "--branch",
                "ai/fix/494-x",
            ]
        )
        == 0
    )
    assert calls == [(sentinel_runner, tmp_path, "ai/fix/494-x", False)]
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "planned": True,
        "repo": "mikolaj92/lokay",
        "branch": "ai/fix/494-x",
        "worktree": str(tmp_path),
    }

from __future__ import annotations

import json

import pytest

from lokay.proc import push_branch


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_product_repo_skips_without_git_or_preflight(
    repo: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("product repositories must not run git or preflight")

    monkeypatch.setattr(push_branch, "load_cfg", fail_if_called)
    monkeypatch.setattr(push_branch, "mutations_allowed", fail_if_called)
    monkeypatch.setattr(push_branch, "runner", fail_if_called)

    assert (
        push_branch.main(
            [
                "--live",
                "--repo",
                repo,
                "--worktree",
                str(tmp_path),
                "--branch",
                "ai/fix/494-x",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "planned": False,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
        "branch": "ai/fix/494-x",
        "worktree": str(tmp_path),
    }


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

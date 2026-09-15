"""The mini lokay creates worktrees only for its Lokay delivery lane."""

import json

import pytest

from lokay.code import github as github_code
from lokay.proc import worktree_add


@pytest.fixture
def config_path(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        f"""
mode: live
github:
  assignee: t
  ready_label: ai:ready
  blocked_label: ai:blocked
  branch_prefix: ai/fix
  pr_labels: [ai:generated]
repos:
  - name: mikolaj92/lokay
    clone_path: {tmp_path / "lokay"}
  - name: mikolaj92/Temida
    clone_path: {tmp_path / "Temida"}
  - name: mikolaj92/takt
    clone_path: {tmp_path / "takt"}
executor:
  enabled: false
  agent: pi
merge:
  enabled: false
worktrees:
  root: {tmp_path / "worktrees"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    return path




def test_factory_repo_still_creates_worktree(config_path, tmp_path, monkeypatch, capsys):
    expected = tmp_path / "worktrees" / "lokay"
    (tmp_path / "lokay").mkdir()
    calls = []

    def ensure(*args, **kwargs):
        calls.append((args, kwargs))
        return expected

    monkeypatch.setattr(github_code, "ensure_worktree", ensure)
    monkeypatch.setattr(
        worktree_add,
        "mutations_allowed",
        lambda *, live_flag, cfg: live_flag and cfg.mode == "live",
    )

    code = worktree_add.main(
        [
            "--config",
            str(config_path),
            "--repo",
            "mikolaj92/lokay",
            "--branch",
            "ai/fix/461-x",
            "--live",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert len(calls) == 1
    assert calls[0][0][2].name == "mikolaj92/lokay"
    assert calls[0][1]["live"] is True
    assert payload["worktree"] == str(expected)
    assert payload["route"] == "ready"
    assert "skipped" not in payload


def test_missing_clone_is_classified_ready_route(config_path, monkeypatch, capsys):
    monkeypatch.setattr(
        worktree_add,
        "mutations_allowed",
        lambda *, live_flag, cfg: live_flag and cfg.mode == "live",
    )
    code = worktree_add.main(
        [
            "--config",
            str(config_path),
            "--repo",
            "mikolaj92/Temida",
            "--branch",
            "ai/fix/5180-x",
            "--live",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ok"] is True
    assert payload["route"] == "missing"
    assert payload["reason"] == "clone_path_missing"


def test_live_repair_main_resolves_and_verifies_the_exact_pr_head(
    tmp_path, monkeypatch, capsys
):
    from types import SimpleNamespace

    from lokay import gh_prs, git_worktree
    from lokay.runner import CommandResult

    head = "a" * 40
    clone = tmp_path / "clone"
    clone.mkdir()
    worktree = tmp_path / "repair"
    repo = SimpleNamespace(name="acme/demo", clone_path=clone)
    cfg = SimpleNamespace(repos=[repo])

    class Runner:
        def run(self, spec, *, live):
            if "rev-parse" in spec.argv:
                return CommandResult(spec, live, 0, stdout=head)
            if "status" in spec.argv:
                return CommandResult(spec, live, 0, stdout="")
            raise AssertionError(f"unexpected command: {spec.argv}")

    command_runner = Runner()
    calls = []
    monkeypatch.setattr(worktree_add, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(worktree_add, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(worktree_add, "runner", lambda: command_runner)
    monkeypatch.setattr(
        git_worktree,
        "ensure_repair_worktree",
        lambda *_args, **_kwargs: worktree,
    )
    monkeypatch.setattr(
        gh_prs,
        "gh_json",
        lambda *_args, **_kwargs: calls.append(True)
        or {
            "headRefOid": head,
            "headRepository": {"nameWithOwner": "acme/demo"},
        },
    )

    code = worktree_add.main(
        [
            "--repo", "acme/demo", "--branch", "ai/fix/42-demo",
            "--pr", "84", "--repair-start-head-sha", head, "--live",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["route"] == "ready"
    assert payload["repair_start_head_sha"] == head
    assert payload["worktree_head_sha"] == head
    assert payload["repair_start_head_sha"] == head
    assert len(calls) == 2

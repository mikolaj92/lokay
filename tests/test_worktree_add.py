"""The mini mill creates worktrees only for its Lokay delivery lane."""

import json

import pytest

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


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_product_repo_skips_before_preflight_or_creating_worktree(
    config_path, repo, monkeypatch, capsys
):
    monkeypatch.setattr(
        worktree_add,
        "mutations_allowed",
        lambda **_kwargs: pytest.fail("must not run preflight for a product repo"),
    )
    monkeypatch.setattr(
        worktree_add,
        "ensure_worktree",
        lambda *_args, **_kwargs: pytest.fail("must not create a product worktree"),
    )

    code = worktree_add.main(
        [
            "--config",
            str(config_path),
            "--repo",
            repo,
            "--branch",
            "ai/fix/461-x",
            "--live",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload == {
        "ok": True,
        "planned": False,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
        "branch": "ai/fix/461-x",
    }


def test_lokay_repo_still_creates_worktree(config_path, tmp_path, monkeypatch, capsys):
    expected = tmp_path / "worktrees" / "lokay"
    calls = []

    def ensure(*args, **kwargs):
        calls.append((args, kwargs))
        return expected

    monkeypatch.setattr(worktree_add, "ensure_worktree", ensure)
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
    assert "skipped" not in payload

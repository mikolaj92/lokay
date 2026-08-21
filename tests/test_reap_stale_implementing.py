from pathlib import Path
from types import SimpleNamespace
import os
import time

from lokay.passkit import io as pass_io
from lokay.proc import reap_stale_implementing


def test_reap_stale_implementing_skips_lokay_outside_survey_scope(tmp_path, monkeypatch):
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "live": True,
            "repos": ["mikolaj92/lokay"],
            "survey_repos": ["other/hot"],
        },
    )
    pass_io.write_json(pass_io.working_path(pass_dir), {"actions": []})
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
  - name: mikolaj92/lokay
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
    (tmp_path / "clone").mkdir()

    def _boom(*a, **k):
        raise AssertionError("Lokay outside survey scope must not be listed")

    monkeypatch.setattr(reap_stale_implementing, "list_labeled_issues", _boom)
    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=str(pass_dir),
        config_path=str(cfg),
        live=True,
    )
    assert out["reaped_count"] == 0


def test_reap_stale_implementing_lists_only_lokay(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    repo_names = [
        "mikolaj92/Temida",
        "mikolaj92/takt",
        "mikolaj92/app-factory",
        "mikolaj92/lokay",
    ]
    repos_yaml = "\n".join(
        f"  - name: {name}\n    clone_path: {tmp_path / name.split('/')[-1]}"
        for name in repo_names
    )
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
{repos_yaml}
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
    for name in repo_names:
        (tmp_path / name.split("/")[-1]).mkdir()
    listed_repos = []

    def _list(_runner, _cfg, repo, *, label, live):
        listed_repos.append(repo.name)
        if label == "ai:in-progress":
            return [SimpleNamespace(number=443)]
        return []

    monkeypatch.setattr(reap_stale_implementing, "list_labeled_issues", _list)

    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=False,
    )

    assert out["ok"] is True
    assert out["reaped_count"] == 1
    assert out["reaped"][0]["repo"] == "mikolaj92/lokay"
    assert set(listed_repos) == {"mikolaj92/lokay"}


def test_stale_empty_probe_writes_stamp(tmp_path, monkeypatch):
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
  - name: mikolaj92/lokay
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
    (tmp_path / "clone").mkdir()
    monkeypatch.setattr(reap_stale_implementing, "list_labeled_issues", lambda *_a, **_k: [])
    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )
    assert out["reaped_count"] == 0
    assert (tmp_path / "reap-stale-implementing.stamp").is_file()


def test_stale_skips_github_when_recent_empty_stamp(tmp_path, monkeypatch):
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
  - name: mikolaj92/lokay
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
    (tmp_path / "clone").mkdir()
    stamp = tmp_path / "reap-stale-implementing.stamp"
    stamp.write_text("1", encoding="utf-8")
    before = stamp.stat().st_mtime

    def boom(*_a, **_k):
        raise AssertionError("recent empty leftover cache must not list GitHub")

    monkeypatch.setattr(reap_stale_implementing, "list_labeled_issues", boom)
    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )
    assert out["skipped"] is True
    assert out["reason"] == "recent_empty"
    assert out["reaped_count"] == 0
    assert stamp.stat().st_mtime == before


def test_pytest_does_not_skip_leftover_cache_github_lists_using_the_mill_stamp(
    tmp_path, monkeypatch
):
    mill = tmp_path / ".lokay"
    mill.mkdir()
    stamp = mill / "reap-stale-implementing.stamp"
    stamp.write_text("1", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(
        "PYTEST_CURRENT_TEST",
        "test_pytest_does_not_skip_leftover_cache_github_lists_using_the_mill_stamp",
    )
    assert reap_stale_implementing.stale_recently_empty(stamp) is False
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
  - name: mikolaj92/lokay
    clone_path: {tmp_path / "clone"}
executor:
  enabled: false
  agent: grok
merge:
  enabled: false
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {mill / "state.jsonl"}
""",
        encoding="utf-8",
    )
    (tmp_path / "clone").mkdir()
    listed: list[str] = []
    monkeypatch.setattr(
        reap_stale_implementing,
        "list_labeled_issues",
        lambda *_a, **_k: listed.append("gh") or [],
    )
    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )
    assert out.get("skipped") is not True
    assert listed
    hermetic = tmp_path / "reap-stale-implementing.stamp"
    hermetic.write_text("1", encoding="utf-8")
    assert reap_stale_implementing.stale_recently_empty(hermetic) is True
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "proc"
        / "reap_stale_implementing.py"
    )
    assert "Pytest must not skip leftover-cache GitHub lists using the mill stamp." in src.read_text(
        encoding="utf-8"
    )


def test_stale_probes_when_empty_stamp_expired(tmp_path, monkeypatch):
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
  - name: mikolaj92/lokay
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
    (tmp_path / "clone").mkdir()
    stamp = tmp_path / "reap-stale-implementing.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - reap_stale_implementing.STALE_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    monkeypatch.setattr(reap_stale_implementing, "list_labeled_issues", lambda *_a, **_k: [])
    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )
    assert out.get("skipped") is not True
    assert out["reaped_count"] == 0
    assert stamp.is_file()
    assert stamp.stat().st_mtime >= old + reap_stale_implementing.STALE_TTL_SECONDS


def test_stale_reap_clears_empty_stamp(tmp_path, monkeypatch):
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
  - name: mikolaj92/lokay
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
    (tmp_path / "clone").mkdir()
    stamp = tmp_path / "reap-stale-implementing.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - reap_stale_implementing.STALE_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    monkeypatch.setattr(
        reap_stale_implementing,
        "list_labeled_issues",
        lambda *_a, **k: [SimpleNamespace(number=443)] if k.get("label") == "ai:in-progress" else [],
    )
    monkeypatch.setattr(
        reap_stale_implementing,
        "run_proc",
        lambda *_a, **_k: {"ok": True, "stage": "ready", "applied": True},
    )
    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )
    assert out["reaped_count"] == 1
    assert not stamp.exists()

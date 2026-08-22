from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace

from lokay.models import Issue
from lokay.proc import ready_hygiene
from lokay.proc.ready_hygiene import run_ready_hygiene


def _issue(number: int, labels: list[str]) -> Issue:
    return Issue(repo="mikolaj92/lokay", number=number, title="x", body="", labels=labels, assignees=["mikolaj92"], url="")


def test_ready_hygiene_removes_only_orphan_ready(monkeypatch):
    cfg = SimpleNamespace(
        ready_label="ai:ready",
        mode="live",
        active_repos=lambda: [SimpleNamespace(name="mikolaj92/lokay")],
    )
    removed = []
    monkeypatch.setattr("lokay.proc.ready_hygiene.load_cfg", lambda _args: cfg)
    monkeypatch.setattr("lokay.proc.ready_hygiene.mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr("lokay.proc.ready_hygiene.runner", lambda *_args: object())
    monkeypatch.setattr(
        "lokay.proc.ready_hygiene.list_labeled_issues",
        lambda *_args, **_kwargs: [_issue(1, ["ai:ready"]), _issue(2, ["ai:ready", "work:ready"])],
    )
    monkeypatch.setattr(
        "lokay.proc.ready_hygiene.remove_issue_labels",
        lambda _run, repo, number, labels, *, live: removed.append((repo, number, labels, live)),
    )

    out = run_ready_hygiene(config_path=None, live=True)

    assert out["cleaned_count"] == 1
    assert removed == [("mikolaj92/lokay", 1, ["ai:ready"], True)]


def test_hygiene_empty_probe_writes_stamp(tmp_path, monkeypatch):
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
    monkeypatch.setattr("lokay.proc.ready_hygiene.mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr("lokay.proc.ready_hygiene.list_labeled_issues", lambda *_a, **_k: [])
    monkeypatch.setattr("lokay.proc.ready_hygiene.remove_issue_labels", lambda *_a, **_k: None)
    out = run_ready_hygiene(config_path=str(cfg), live=True)
    assert out["cleaned_count"] == 0
    assert (tmp_path / "ready-hygiene.stamp").is_file()


def test_hygiene_skips_github_when_recent_empty_stamp(tmp_path, monkeypatch):
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
    stamp = tmp_path / "ready-hygiene.stamp"
    stamp.write_text("1", encoding="utf-8")
    before = stamp.stat().st_mtime
    monkeypatch.setattr("lokay.proc.ready_hygiene.mutations_allowed", lambda **_kwargs: True)

    def boom(*_a, **_k):
        raise AssertionError("recent empty leftover ready must not list GitHub")

    monkeypatch.setattr("lokay.proc.ready_hygiene.list_labeled_issues", boom)
    out = run_ready_hygiene(config_path=str(cfg), live=True)
    assert out["skipped"] is True
    assert out["reason"] == "recent_empty"
    assert out["cleaned_count"] == 0
    assert stamp.stat().st_mtime == before


def test_fresh_leftover_ready_skip_does_not_require_healthy(tmp_path, monkeypatch):
    """Fresh leftover-ready skip does not require healthy. Hosted leftover-ready parks still do."""
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
    stamp = tmp_path / "ready-hygiene.stamp"
    stamp.write_text("1", encoding="utf-8")

    def boom(**_kwargs):
        raise AssertionError("fresh leftover-ready skip does not require healthy")

    monkeypatch.setattr("lokay.proc.ready_hygiene.mutations_allowed", boom)

    def list_boom(*_a, **_k):
        raise AssertionError("recent empty leftover ready must not list GitHub")

    monkeypatch.setattr("lokay.proc.ready_hygiene.list_labeled_issues", list_boom)
    out = run_ready_hygiene(config_path=str(cfg), live=True)
    assert out["skipped"] is True
    assert out["reason"] == "recent_empty"
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "ready_hygiene.py"
    assert "Fresh leftover-ready skip does not require healthy." in src.read_text(
        encoding="utf-8"
    )


def test_idle_leftover_ready_skip_outlives_leftover_probe(tmp_path, monkeypatch):
    """Idle leftover-ready skip outlives leftover-probe. Hosted factory_pass stays at 300s."""
    from lokay.proc import ready_hygiene as hygiene

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
    stamp = tmp_path / "ready-hygiene.stamp"
    stamp.write_text("1", encoding="utf-8")
    leftover_age = time.time() - 301
    os.utime(stamp, (leftover_age, leftover_age))
    listed: list[int] = []

    def fake_list(*_a, **_k):
        listed.append(1)
        return []

    monkeypatch.setattr("lokay.proc.ready_hygiene.mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr("lokay.proc.ready_hygiene.list_labeled_issues", fake_list)
    monkeypatch.setattr("lokay.proc.ready_hygiene.remove_issue_labels", lambda *_a, **_k: None)
    monkeypatch.delenv("LOKAY_LEFTOVER_PROBE_GH_OK", raising=False)
    hosted = run_ready_hygiene(config_path=str(cfg), live=True)
    assert hosted.get("skipped") is not True
    assert listed == [1]
    leftover_age = time.time() - 301
    os.utime(stamp, (leftover_age, leftover_age))
    listed.clear()
    monkeypatch.setenv("LOKAY_LEFTOVER_PROBE_GH_OK", "1")
    idle = run_ready_hygiene(config_path=str(cfg), live=True)
    assert idle["skipped"] is True
    assert idle["reason"] == "recent_empty"
    assert listed == []
    assert stamp.stat().st_mtime == leftover_age
    assert hygiene.hygiene_recently_empty(stamp) is False
    assert hygiene.hygiene_recently_empty(
        stamp, ttl=hygiene.IDLE_HYGIENE_TTL_SECONDS
    ) is True
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "ready_hygiene.py"
    assert "Idle leftover-ready skip outlives leftover-probe." in src.read_text(
        encoding="utf-8"
    )


def test_pytest_does_not_skip_leftover_ready_github_lists_using_the_mill_stamp(
    tmp_path, monkeypatch
):
    mill = tmp_path / ".lokay"
    mill.mkdir()
    stamp = mill / "ready-hygiene.stamp"
    stamp.write_text("1", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(
        "PYTEST_CURRENT_TEST",
        "test_pytest_does_not_skip_leftover_ready_github_lists_using_the_mill_stamp",
    )
    from lokay.proc import ready_hygiene as hygiene

    assert hygiene.hygiene_recently_empty(stamp) is False
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
    monkeypatch.setattr("lokay.proc.ready_hygiene.mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(
        "lokay.proc.ready_hygiene.list_labeled_issues",
        lambda *_a, **_k: listed.append("gh") or [],
    )
    out = run_ready_hygiene(config_path=str(cfg), live=True)
    assert out.get("skipped") is not True
    assert listed == ["gh"]
    hermetic = tmp_path / "ready-hygiene.stamp"
    hermetic.write_text("1", encoding="utf-8")
    assert hygiene.hygiene_recently_empty(hermetic) is True
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "ready_hygiene.py"
    assert "Pytest must not skip leftover-ready GitHub lists using the mill stamp." in src.read_text(
        encoding="utf-8"
    )


def test_hygiene_probes_when_empty_stamp_expired(tmp_path, monkeypatch):
    import os
    import time
    from lokay.proc import ready_hygiene as hygiene

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
    stamp = tmp_path / "ready-hygiene.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - hygiene.HYGIENE_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    monkeypatch.setattr("lokay.proc.ready_hygiene.mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr("lokay.proc.ready_hygiene.list_labeled_issues", lambda *_a, **_k: [])
    out = run_ready_hygiene(config_path=str(cfg), live=True)
    assert out.get("skipped") is not True
    assert out["cleaned_count"] == 0
    assert stamp.is_file()
    assert stamp.stat().st_mtime >= old + hygiene.HYGIENE_TTL_SECONDS


def test_hygiene_clean_clears_empty_stamp(tmp_path, monkeypatch):
    import os
    import time
    from lokay.proc import ready_hygiene as hygiene

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
    stamp = tmp_path / "ready-hygiene.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - hygiene.HYGIENE_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    monkeypatch.setattr("lokay.proc.ready_hygiene.mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(
        "lokay.proc.ready_hygiene.list_labeled_issues",
        lambda *_a, **_k: [_issue(1, ["ai:ready"])],
    )
    monkeypatch.setattr("lokay.proc.ready_hygiene.remove_issue_labels", lambda *_a, **_k: None)
    out = run_ready_hygiene(config_path=str(cfg), live=True)
    assert out["cleaned_count"] == 1
    assert not stamp.exists()


def test_hygiene_idle_leftover_ready_runs_when_live(tmp_path, monkeypatch):
    """Idle daemon_cycle skip still runs leftover-ready."""
    from lokay.proc import ready_hygiene as hygiene

    called: list[dict] = []

    def fake_run(**kwargs):
        called.append(kwargs)
        return {"ok": True, "cleaned_count": 0}

    monkeypatch.setattr(hygiene, "run_ready_hygiene", fake_run)
    hygiene.hygiene_idle_leftover_ready(
        config_path=str(tmp_path / "config.yaml"), live=True
    )
    assert called == [
        {"config_path": str(tmp_path / "config.yaml"), "live": True}
    ]
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "ready_hygiene.py"
    assert "Idle daemon_cycle skip still runs leftover-ready." in src.read_text(
        encoding="utf-8"
    )


def test_hygiene_idle_leftover_ready_skips_when_not_live(tmp_path, monkeypatch):
    from lokay.proc import ready_hygiene as hygiene

    def boom(**_k):
        raise AssertionError("not-live skip does not run leftover-ready")

    monkeypatch.setattr(hygiene, "run_ready_hygiene", boom)
    hygiene.hygiene_idle_leftover_ready(
        config_path=str(tmp_path / "missing.yaml"), live=False
    )


def test_hygiene_idle_leftover_ready_oserror_cannot_stall(tmp_path, monkeypatch):
    from lokay.proc import ready_hygiene as hygiene

    def boom(**_k):
        raise OSError("config unreadable")

    monkeypatch.setattr(hygiene, "run_ready_hygiene", boom)
    hygiene.hygiene_idle_leftover_ready(
        config_path=str(tmp_path / "missing.yaml"), live=True
    )

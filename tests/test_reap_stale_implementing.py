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

    def _list(_runner, _cfg, repo, *, label, live, **_kwargs):
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
    assert out["reaped_count"] == 0
    assert out["reaped"][0]["repo"] == "mikolaj92/lokay"
    assert out["reaped"][0]["planned"] is True
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

    def health_boom(**_kwargs):
        raise AssertionError("fresh leftover-cache skip does not require healthy")

    monkeypatch.setattr(reap_stale_implementing, "mutations_allowed", health_boom)
    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )
    assert out["skipped"] is True
    assert out["reason"] == "recent_empty"
    assert out["reaped_count"] == 0
    assert stamp.stat().st_mtime == before
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "proc"
        / "reap_stale_implementing.py"
    )
    assert "Fresh leftover-cache skip does not require healthy." in src.read_text(
        encoding="utf-8"
    )


def test_fresh_leftover_cache_skip_is_not_applied(tmp_path, monkeypatch):
    """Fresh leftover-cache skip is not applied."""
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

    def boom(*_a, **_k):
        raise AssertionError("recent empty leftover cache must not list GitHub")

    monkeypatch.setattr(reap_stale_implementing, "list_labeled_issues", boom)

    def health_boom(**_kwargs):
        raise AssertionError("fresh leftover-cache skip does not require healthy")

    monkeypatch.setattr(reap_stale_implementing, "mutations_allowed", health_boom)
    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )
    assert out["skipped"] is True
    assert out["reason"] == "recent_empty"
    assert out["applied"] is False
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "proc"
        / "reap_stale_implementing.py"
    )
    assert "Fresh leftover-cache skip is not applied." in src.read_text(encoding="utf-8")


def test_hosted_leftover_cache_parks_require_healthy(tmp_path, monkeypatch):
    """Fresh leftover-cache skip does not require healthy. Hosted leftover-cache parks do."""
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
    gated: list[bool] = []

    def allow(**_kwargs):
        gated.append(True)
        return True

    monkeypatch.setattr(reap_stale_implementing, "mutations_allowed", allow)
    monkeypatch.setattr(
        reap_stale_implementing,
        "list_labeled_issues",
        lambda *_a, **k: [SimpleNamespace(number=443)]
        if k.get("label") == "ai:in-progress"
        else [],
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
    assert gated == [True]
    assert out["reaped_count"] == 1
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "proc"
        / "reap_stale_implementing.py"
    )
    assert "Fresh leftover-cache skip does not require healthy." in src.read_text(
        encoding="utf-8"
    )
    assert "Hosted leftover-cache parks do." in src.read_text(encoding="utf-8")


def test_unhealthy_leftover_cache_parks_do_not_clear_stamp(tmp_path, monkeypatch):
    """Unhealthy leftover-cache parks do not clear the stamp."""
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

    def reject(**_kwargs):
        return False

    def unexpected_stage(*_a, **_k):
        raise AssertionError("unhealthy leftover-cache parks must not stage")

    monkeypatch.setattr(reap_stale_implementing, "mutations_allowed", reject)
    monkeypatch.setattr(
        reap_stale_implementing,
        "list_labeled_issues",
        lambda *_a, **k: [SimpleNamespace(number=443)]
        if k.get("label") == "ai:in-progress"
        else [],
    )
    monkeypatch.setattr(reap_stale_implementing, "run_proc", unexpected_stage)
    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )
    assert out["reaped_count"] == 0
    assert out["reaped"][0]["planned"] is True
    assert out["planned"] is True
    assert stamp.is_file()
    assert stamp.stat().st_mtime == old
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "proc"
        / "reap_stale_implementing.py"
    )
    assert "Unhealthy leftover-cache parks do not clear the stamp." in src.read_text(
        encoding="utf-8"
    )
    assert "Unhealthy leftover-cache parks are planned." in src.read_text(
        encoding="utf-8"
    )


def test_leftover_cache_reaped_count_excludes_planned(tmp_path, monkeypatch):
    """Leftover-cache reaped_count excludes planned parks."""
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
    monkeypatch.setattr(reap_stale_implementing, "mutations_allowed", lambda **_k: False)
    monkeypatch.setattr(
        reap_stale_implementing,
        "list_labeled_issues",
        lambda *_a, **k: [SimpleNamespace(number=443)]
        if k.get("label") == "ai:in-progress"
        else [],
    )
    monkeypatch.setattr(
        reap_stale_implementing,
        "run_proc",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("unhealthy leftover-cache parks must not stage")
        ),
    )
    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )
    assert out["reaped_count"] == 0
    assert out["reaped"][0]["planned"] is True
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "proc"
        / "reap_stale_implementing.py"
    )
    assert "Leftover-cache reaped_count excludes planned parks." in src.read_text(
        encoding="utf-8"
    )


def test_hosted_leftover_cache_reports_applied(tmp_path, monkeypatch):
    """Hosted leftover-cache reports applied."""
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
    monkeypatch.setattr(
        reap_stale_implementing,
        "list_labeled_issues",
        lambda *_a, **k: [SimpleNamespace(number=443)]
        if k.get("label") == "ai:in-progress"
        else [],
    )
    monkeypatch.setattr(reap_stale_implementing, "mutations_allowed", lambda **_k: False)
    monkeypatch.setattr(
        reap_stale_implementing,
        "run_proc",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("unhealthy leftover-cache parks must not stage")
        ),
    )
    unhealthy = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )
    assert unhealthy["applied"] is False
    assert unhealthy["planned"] is True
    monkeypatch.setattr(reap_stale_implementing, "mutations_allowed", lambda **_k: True)
    monkeypatch.setattr(
        reap_stale_implementing,
        "run_proc",
        lambda *_a, **_k: {"ok": True, "stage": "ready", "applied": True},
    )
    healthy = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )
    assert healthy["applied"] is True
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "proc"
        / "reap_stale_implementing.py"
    )
    assert "Hosted leftover-cache reports applied." in src.read_text(encoding="utf-8")


def test_idle_leftover_cache_skip_outlives_leftover_probe(tmp_path, monkeypatch):
    """Idle leftover-cache skip outlives leftover-probe. Hosted factory_pass stays at 300s."""
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
    leftover_age = time.time() - 301
    os.utime(stamp, (leftover_age, leftover_age))
    listed: list[int] = []

    def fake_list(*_a, **_k):
        listed.append(1)
        return []

    monkeypatch.setattr(reap_stale_implementing, "list_labeled_issues", fake_list)
    monkeypatch.delenv("LOKAY_LEFTOVER_PROBE_GH_OK", raising=False)
    hosted = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )
    assert hosted.get("skipped") is not True
    assert listed
    leftover_age = time.time() - 301
    os.utime(stamp, (leftover_age, leftover_age))
    listed.clear()
    monkeypatch.setenv("LOKAY_LEFTOVER_PROBE_GH_OK", "1")
    idle = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )
    assert idle["skipped"] is True
    assert idle["reason"] == "recent_empty"
    assert listed == []
    assert stamp.stat().st_mtime == leftover_age
    assert reap_stale_implementing.stale_recently_empty(stamp) is False
    assert reap_stale_implementing.stale_recently_empty(
        stamp, ttl=reap_stale_implementing.IDLE_STALE_TTL_SECONDS
    ) is True
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "proc"
        / "reap_stale_implementing.py"
    )
    assert "Idle leftover-cache skip outlives leftover-probe." in src.read_text(
        encoding="utf-8"
    )


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


def test_leftover_cache_rate_limit_does_not_stamp_empty(tmp_path, monkeypatch):
    """Leftover-cache rate limit does not stamp empty."""
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
    stamp = tmp_path / "leftover-cache.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - reap_stale_implementing.STALE_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    monkeypatch.setattr(
        reap_stale_implementing,
        "list_labeled_issues",
        lambda *_a, **_k: (_ for _ in ()).throw(
            RuntimeError("HTTP 429: API rate limit exceeded")
        ),
    )
    monkeypatch.setattr(
        reap_stale_implementing,
        "mutations_allowed",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("failed probe must not check mutation health")
        ),
    )

    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )

    assert out["probe_failed"] is True
    assert out["reaped_count"] == 0
    assert stamp.stat().st_mtime == old
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "reap_stale_implementing.py"
    assert "Leftover-cache rate limit does not stamp empty." in src.read_text(
        encoding="utf-8"
    )


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
    monkeypatch.setattr(
        reap_stale_implementing, "mutations_allowed", lambda **_kwargs: True
    )
    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )
    assert out["reaped_count"] == 1
    assert not stamp.exists()


def test_reap_idle_leftover_cache_runs_when_live(tmp_path, monkeypatch):
    """Idle daemon_cycle skip still runs leftover-cache."""
    called: list[dict] = []

    def fake_run(**kwargs):
        called.append(kwargs)
        return {"ok": True, "reaped_count": 0}

    monkeypatch.setattr(
        reap_stale_implementing, "run_reap_stale_implementing", fake_run
    )
    reap_stale_implementing.reap_idle_leftover_cache(
        config_path=str(tmp_path / "config.yaml"), live=True
    )
    assert called == [
        {
            "pass_dir": None,
            "config_path": str(tmp_path / "config.yaml"),
            "live": True,
        }
    ]
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "proc"
        / "reap_stale_implementing.py"
    )
    assert "Idle daemon_cycle skip still runs leftover-cache." in src.read_text(
        encoding="utf-8"
    )


def test_reap_idle_leftover_cache_skips_when_not_live(tmp_path, monkeypatch):
    def boom(**_k):
        raise AssertionError("not-live skip does not run leftover-cache")

    monkeypatch.setattr(
        reap_stale_implementing, "run_reap_stale_implementing", boom
    )
    reap_stale_implementing.reap_idle_leftover_cache(
        config_path=str(tmp_path / "missing.yaml"), live=False
    )


def test_reap_idle_leftover_cache_oserror_cannot_stall(tmp_path, monkeypatch):
    def boom(**_k):
        raise OSError("config unreadable")

    monkeypatch.setattr(
        reap_stale_implementing, "run_reap_stale_implementing", boom
    )
    reap_stale_implementing.reap_idle_leftover_cache(
        config_path=str(tmp_path / "missing.yaml"), live=True
    )

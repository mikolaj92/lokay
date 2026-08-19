from pathlib import Path
from lokay.passkit import io as pass_io
from lokay.proc import reap_stale_implementing


def test_reap_stale_implementing_skips_repos_outside_survey_scope(tmp_path, monkeypatch):
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {"live": True, "repos": ["owner/cold"], "survey_repos": ["other/hot"]},
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
  - name: owner/cold
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
        raise AssertionError("cold repo must not be listed")

    monkeypatch.setattr(reap_stale_implementing, "list_labeled_issues", _boom)
    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=str(pass_dir),
        config_path=str(cfg),
        live=True,
    )
    assert out["reaped_count"] == 0


def test_reap_stale_implementing_skips_rate_limited_repo(tmp_path, monkeypatch):
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
  - name: owner/exhausted
    clone_path: {tmp_path / "exhausted"}
  - name: owner/healthy
    clone_path: {tmp_path / "healthy"}
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
    (tmp_path / "exhausted").mkdir()
    (tmp_path / "healthy").mkdir()
    listed_repos = []

    def _list(_runner, _cfg, repo, **_kwargs):
        listed_repos.append(repo.name)
        if repo.name == "owner/exhausted":
            raise RuntimeError("GraphQL: API rate limit exceeded (HTTP 429)")
        return []

    monkeypatch.setattr(reap_stale_implementing, "list_labeled_issues", _list)

    out = reap_stale_implementing.run_reap_stale_implementing(
        pass_dir=None,
        config_path=str(cfg),
        live=True,
    )

    assert out["ok"] is True
    assert out["reaped_count"] == 0
    assert "owner/healthy" in listed_repos

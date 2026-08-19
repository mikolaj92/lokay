from types import SimpleNamespace

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

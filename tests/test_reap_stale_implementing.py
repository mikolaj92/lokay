"""Semantics of minimal stale implementation-stage recovery processes."""

import os, time
from pathlib import Path
from types import SimpleNamespace
from lokay.passkit import io as pass_io
from lokay.proc import stale_implementing_stamp as stamp


def _config(tmp_path):
    path = tmp_path / "config.yaml"
    clone = tmp_path / "clone"
    clone.mkdir(exist_ok=True)
    path.write_text(f"""mode: live
github:
  assignee: t
  ready_label: ai:ready
  blocked_label: ai:blocked
  branch_prefix: ai/fix
  pr_labels: [ai:generated]
repos:
  - name: mikolaj92/lokay
    clone_path: {clone}
executor:
  enabled: false
  agent: grok
merge:
  enabled: false
worktrees:
  root: {tmp_path/'wt'}
state:
  path: {tmp_path/'state.jsonl'}
""")
    return str(path)


def test_recent_empty_stamp_skips_probe(tmp_path):
    from lokay.proc.prepare_stale_implementing_reap import prepare

    cfg = _config(tmp_path)
    (tmp_path / stamp.STALE_STAMP_NAME).write_text("1")
    out = prepare(pass_dir=None, config_path=cfg, slot_count=30)
    assert out["route"] == "recent_empty"


def test_expired_stamp_requires_probe(tmp_path):
    from lokay.proc.prepare_stale_implementing_reap import prepare

    cfg = _config(tmp_path)
    path = tmp_path / stamp.STALE_STAMP_NAME
    path.write_text("1")
    old = time.time() - stamp.STALE_TTL_SECONDS - 1
    os.utime(path, (old, old))
    assert prepare(pass_dir=None, config_path=cfg, slot_count=30)["route"] == "probe"


def test_repo_outside_survey_scope_is_explicit(tmp_path):
    from lokay.proc.prepare_stale_implementing_reap import prepare
    from lokay.proc.select_stale_repo_slot import select

    cfg = _config(tmp_path)
    pd = tmp_path / "pass"
    pd.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pd),
        {"repos": ["mikolaj92/lokay"], "survey_repos": ["other/hot"]},
    )
    pass_io.write_json(pass_io.working_path(pd), {"actions": []})
    assert (
        select(prepare(pass_dir=str(pd), config_path=cfg, slot_count=30), slot=1)[
            "route"
        ]
        == "outside_scope"
    )


def test_rate_limit_probe_is_failed_not_empty(tmp_path, monkeypatch):
    from lokay.proc.list_stale_implementing_issues import fetch

    cfg = _config(tmp_path)
    monkeypatch.setattr(
        "lokay.proc.list_stale_implementing_issues.list_labeled_issues",
        lambda *_a, **_k: (_ for _ in ()).throw(
            RuntimeError("HTTP 429: API rate limit exceeded")
        ),
    )
    out = fetch(
        {"repo": "mikolaj92/lokay"}, config_path=cfg, live=True, label="ai:in-progress"
    )
    assert out["route"] == "failed"


def test_repo_probe_deduplicates_issue_across_labels():
    from lokay.proc.reduce_stale_repo_probe import reduce_state

    item = {"repo": "a/one", "issue": 2, "label": "ai:in-progress"}
    out = reduce_state(
        {"route": "repo", "repo": "a/one"},
        [
            {"route": "listed", "issues": [item]},
            {"route": "listed", "issues": [{**item, "label": "ai:repairing"}]},
        ],
    )
    assert out["issues"] == [item]


def test_probe_overflow_is_fail_closed():
    from lokay.proc.reduce_stale_implementing_probe import reduce_state

    rows = [
        {
            "route": "probed",
            "issues": [{"repo": "a/one", "issue": i} for i in range(31)],
        }
    ]
    out = reduce_state(prepared={}, rows=rows, candidate_slots=30)
    assert out["ok"] is False and "exceed authored slots" in out["error"]


def test_plan_only_candidate_is_not_counted_reaped():
    from lokay.proc.reduce_stale_reap_effects import reduce_state

    out = reduce_state(
        probe={"probed": True},
        gate={"apply": False},
        rows=[
            {"route": "plan", "repo": "a/one", "issue": 2, "label": "ai:in-progress"}
        ],
    )
    assert out["reaped_count"] == 0 and out["reaped"][0]["planned"] is True


def test_applied_candidate_is_counted():
    from lokay.proc.reduce_stale_reap_effects import reduce_state

    out = reduce_state(
        probe={"probed": True},
        gate={"apply": True},
        rows=[
            {
                "route": "applied",
                "repo": "a/one",
                "issue": 2,
                "staged": {"ok": True, "applied": True},
            }
        ],
    )
    assert out["reaped_count"] == 1


def test_empty_success_touches_stamp(tmp_path):
    from lokay.proc.update_stale_empty_stamp import update

    path = tmp_path / stamp.STALE_STAMP_NAME
    update(
        {
            "stamp": str(path),
            "probed": True,
            "probe_failed": False,
            "reaped": [],
            "apply": False,
        }
    )
    assert path.is_file()


def test_failed_probe_does_not_touch_stamp(tmp_path):
    from lokay.proc.update_stale_empty_stamp import update

    path = tmp_path / stamp.STALE_STAMP_NAME
    update(
        {
            "stamp": str(path),
            "probed": True,
            "probe_failed": True,
            "reaped": [],
            "apply": False,
        }
    )
    assert not path.exists()


def test_applied_reap_clears_old_empty_stamp(tmp_path):
    from lokay.proc.update_stale_empty_stamp import update

    path = tmp_path / stamp.STALE_STAMP_NAME
    path.write_text("1")
    update(
        {
            "stamp": str(path),
            "probed": True,
            "probe_failed": False,
            "reaped": [{"issue": 2}],
            "apply": True,
        }
    )
    assert not path.exists()


def test_idle_facade_runs_only_live(monkeypatch):
    from lokay.proc import reap_stale_implementing as facade

    calls = []
    monkeypatch.setattr(
        facade, "run_reap_stale_implementing", lambda **kw: calls.append(kw)
    )
    facade.reap_idle_leftover_cache(config_path="x", live=False)
    facade.reap_idle_leftover_cache(config_path="x", live=True)
    assert calls == [{"pass_dir": None, "config_path": "x", "live": True}]

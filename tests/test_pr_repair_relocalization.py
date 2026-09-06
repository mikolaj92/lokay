"""PR repair reconciles scope before each post-agent diff gate."""

import pytest

from test_issue_triage_fala import base_effector, run_graph
from test_pr_repair_fala import defaults


@pytest.mark.parametrize("test_repair", [False, True])
def test_repair_relocalizes_before_diff(tmp_path, test_repair):
    trace = tmp_path / "trace"
    body = base_effector(defaults() + f"""
if a=='validate_initial_repair':v['route']='valid'
if a=='select_initial_repair':v.update(route='repaired',evidence_kind='none')
if a=='finalize_repair_result':v.update(route='repaired')
if a=='select_repair_test':v['route']={'fail' if test_repair else 'pass'!r}
if a=='select_test_repair_result':v['route']={'repaired' if test_repair else 'not_applicable'!r}
if a=='finalize_repair_tests':v['route']='publish'
if a in {{'relocalize_off_goal','assert_real_diff'}}:
    with Path({str(trace)!r}).open('a') as f:f.write(a+'\\n')
""")
    result = run_graph(tmp_path, body, "repair-scope", path_id="pr_repair")
    events = trace.read_text().splitlines()
    expected = ["relocalize_off_goal", "assert_real_diff"] * (2 if test_repair else 1)
    assert events == [*expected, "assert_real_diff"]
    states = {k: v["status"] for k, v in result["effector_results"].items()}
    assert states["relocalize_test_repair"] == ("succeeded" if test_repair else "skipped")


@pytest.mark.parametrize("repair_mode,expected", [(True, "@{upstream}"), (False, "origin/main")])
def test_relocalization_uses_delivery_baseline(monkeypatch, repair_mode, expected):
    from lokay.organ.implement import handle_implement
    from lokay.proc import relocalize_off_goal_subflow

    observed = {}

    def run(**kwargs):
        observed.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(relocalize_off_goal_subflow, "run", run)
    ctx = dict(cfg=None, live=True, repo="a/b", issue_number=None,
               repair_mode=repair_mode, branch="ai/fix/79")
    handle_implement("relocalize_off_goal", {},
                     {"worktree_add": {"worktree": "/tmp/repair"}}, ctx)
    assert observed["extra_inputs"]["base"] == expected
    assert observed["extra_inputs"]["repair_mode"] is repair_mode

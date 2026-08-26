"""Contracts for minimal pass-plan processes."""

from lokay.passkit import io as pass_io


def test_plan_pass_subflow_uses_handful_of_ticks():
    from lokay.proc.plan_pass_subflow import run
    import inspect

    source = inspect.getsource(run)
    assert "max_ticks=16" in source
    assert "max_ticks=64" not in source


def test_reduce_honors_global_triage_budget():
    from lokay.proc.reduce_pass_plan import reduce_state

    out = reduce_state(
        prepared={"triage_budget": 1, "skipped_repos": []},
        fragments=[
            {"triage": [{"repo": "a/one", "issue": 1}]},
            {
                "triage": [{"repo": "a/two", "issue": 2}],
                "closeout": [{"pr": 3}],
                "implement": [{"number": 4}],
            },
        ],
        working={"actions": []},
    )
    assert out["plan"]["triage_targets"] == [{"repo": "a/one", "issue": 1}] and out[
        "plan"
    ]["closeout_targets"] == [{"pr": 3}]


def test_catalog_fail_closed_when_prepare_failed():
    from lokay.proc.plan_catalog import run

    out = run({"ok": False, "error": "planning catalog exceeds authored slots"}, pass_dir="unused")
    assert out["ok"] is False and "exceeds authored slots" in out["error"]


def test_catalog_builds_small_catalog_and_reduces(tmp_path):
    from lokay.proc.plan_catalog import run
    from lokay.proc.prepare_pass_plan import prepare

    path = tmp_path / "pass"
    path.mkdir()
    pass_io.write_json(
        pass_io.begin_path(path),
        {
            "repos": ["a/one", "a/two"],
            "live": True,
            "triage_budget": 1,
            "stuck_path": "",
            "stuck": {},
        },
    )
    pass_io.write_json(
        pass_io.working_path(path),
        {"actions": []},
    )
    pass_io.write_json(
        pass_io.survey_path(path),
        {
            "prs_by_repo": {"a/one": [], "a/two": []},
            "inbox_issues_by_repo": {
                "a/one": [{"number": 1}],
                "a/two": [{"number": 2}],
            },
            "ready_by_repo": {},
            "pr_survey_failed": [],
        },
    )
    prepared = prepare(pass_dir=str(path), slot_count=30)
    out = run(prepared, pass_dir=str(path))
    assert out["ok"] is True
    assert out["plan"]["triage_targets"] == [{"repo": "a/one", "issue": 1}]
    assert out["plan"]["triage_budget_remaining"] == 0


def test_persist_writes_plan_and_actions(tmp_path):
    from lokay.proc.persist_pass_plan import persist

    path = tmp_path / "pass"
    path.mkdir()
    pass_io.write_json(pass_io.working_path(path), {"actions": []})
    out = persist(
        pass_dir=str(path),
        reduced={
            "plan": {
                "triage_targets": [],
                "closeout_targets": [],
                "implement_candidates": [],
            },
            "actions": [{"step": "x"}],
        },
    )
    assert out["triage_count"] == 0 and pass_io.read_json(pass_io.working_path(path))[
        "actions"
    ] == [{"step": "x"}]

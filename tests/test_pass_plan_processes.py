"""Contracts for minimal pass-plan processes."""

from lokay.passkit import io as pass_io


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

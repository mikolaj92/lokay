"""Contracts for minimal implementation-selection processes."""

from lokay.passkit import io as pass_io


def workspace(tmp_path, repos=("a/one",)):
    path = tmp_path / "pass"
    path.mkdir()
    pass_io.write_json(
        pass_io.begin_path(path),
        {
            "repos": list(repos),
            "live": True,
            "issue_budget": 1,
            "executor_enabled": True,
            "stuck_path": str(tmp_path / "stuck.json"),
        },
    )
    pass_io.write_json(
        pass_io.working_path(path),
        {
            "actions": [],
            "remaining_ready": 1,
            "ready_by_repo": {"a/one": [{"number": 7}]},
            "prs_by_repo": {},
            "pr_survey_failed": [],
            "occupied_repos": [],
        },
    )
    return path


def test_prepare_and_slot_are_bounded(tmp_path):
    from lokay.proc.prepare_implementation_selection import prepare
    from lokay.proc.select_implementation_repo_slot import select

    path = workspace(tmp_path)
    prepared = prepare(pass_dir=str(path), slot_count=30)
    assert (
        select(prepared, slot=1)["repo"] == "a/one"
        and select(prepared, slot=2)["route"] == "empty"
    )


def test_eligibility_is_closed_physical_gate(tmp_path):
    from lokay.proc.prepare_implementation_selection import prepare
    from lokay.proc.inspect_implementation_eligibility import inspect

    path = workspace(tmp_path)
    prepared = prepare(pass_dir=str(path), slot_count=30)
    out = inspect(
        pass_dir=str(path), prepared=prepared, selected={"repo": "a/one", "slot": 1}
    )
    assert out["route"] == "eligible" and out["implementable"][0]["number"] == 7


def test_reduce_selects_first_eligible_and_removes_blocked():
    from lokay.proc.reduce_implementation_selection import reduce_state

    out = reduce_state(
        prepared={"route": "select", "issue_budget": 1},
        results=[
            {
                "route": "ineligible",
                "repo": "a/one",
                "reason": "stuck_or_no_ready",
                "blocked": [{"number": 7}],
            },
            {"route": "eligible", "repo": "a/two"},
        ],
        working={
            "actions": [],
            "remaining_ready": 2,
            "ready_by_repo": {"a/one": [{"number": 7}], "a/two": [{"number": 8}]},
        },
    )
    assert (
        out["clean_repos"] == ["a/two"]
        and out["ready_by_repo"]["a/one"] == []
        and out["remaining_ready"] == 1
    )

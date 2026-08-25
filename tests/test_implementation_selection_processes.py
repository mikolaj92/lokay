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


def test_oil_is_ineligible_when_product_queue(tmp_path):
    from lokay.proc.inspect_implementation_eligibility import inspect
    from lokay.proc.prepare_implementation_selection import prepare

    path = workspace(tmp_path, repos=("mikolaj92/lokay", "a/product"))
    pass_io.write_json(
        pass_io.begin_path(path),
        {
            "repos": ["mikolaj92/lokay", "a/product"],
            "live": True,
            "issue_budget": 1,
            "executor_enabled": True,
            "incident_repo": "mikolaj92/lokay",
            "stuck_path": str(tmp_path / "stuck.json"),
        },
    )
    pass_io.write_json(
        pass_io.working_path(path),
        {
            "actions": [],
            "remaining_ready": 2,
            "ready_by_repo": {
                "mikolaj92/lokay": [{"number": 1}],
                "a/product": [{"number": 2}],
            },
            "prs_by_repo": {},
            "pr_survey_failed": [],
            "occupied_repos": [],
        },
    )
    prepared = prepare(pass_dir=str(path), slot_count=30)
    oil = inspect(
        pass_dir=str(path),
        prepared=prepared,
        selected={"repo": "mikolaj92/lokay", "slot": 1},
    )
    product = inspect(
        pass_dir=str(path),
        prepared=prepared,
        selected={"repo": "a/product", "slot": 2},
    )
    assert oil["route"] == "ineligible" and oil["reason"] == "product_lane"
    assert product["route"] == "eligible"


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
        and out["lane"] == "product"
    )


def _self() -> str:
    return "mikolaj92/lokay"


def test_reduce_product_and_oil_selects_product():
    from lokay.proc.reduce_implementation_selection import reduce_state

    out = reduce_state(
        prepared={
            "route": "select",
            "issue_budget": 1,
            "self_repo": _self(),
            "product_queue": True,
        },
        results=[
            {"route": "eligible", "repo": _self()},
            {"route": "eligible", "repo": "a/product"},
        ],
        working={
            "actions": [],
            "remaining_ready": 2,
            "ready_by_repo": {
                _self(): [{"number": 1}],
                "a/product": [{"number": 2}],
            },
        },
    )
    assert out["clean_repos"] == ["a/product"] and out["lane"] == "product"


def test_reduce_oil_only_selects_oil():
    from lokay.proc.reduce_implementation_selection import reduce_state

    out = reduce_state(
        prepared={
            "route": "select",
            "issue_budget": 1,
            "self_repo": _self(),
            "product_queue": False,
        },
        results=[{"route": "eligible", "repo": _self()}],
        working={
            "actions": [],
            "remaining_ready": 1,
            "ready_by_repo": {_self(): [{"number": 1}]},
        },
    )
    assert out["clean_repos"] == [_self()] and out["lane"] == "oil"


def test_reduce_empty_is_idle():
    from lokay.proc.reduce_implementation_selection import reduce_state

    out = reduce_state(
        prepared={
            "route": "select",
            "issue_budget": 1,
            "self_repo": _self(),
            "product_queue": False,
        },
        results=[{"route": "ineligible", "repo": "a/one", "reason": "no_ready"}],
        working={"actions": [], "remaining_ready": 0, "ready_by_repo": {}},
    )
    assert out["clean_repos"] == [] and out["lane"] == "idle"


def test_reduce_does_not_fall_through_to_oil_when_product_queue():
    from lokay.proc.reduce_implementation_selection import reduce_state

    out = reduce_state(
        prepared={
            "route": "select",
            "issue_budget": 1,
            "self_repo": _self(),
            "product_queue": True,
        },
        results=[
            {"route": "ineligible", "repo": "a/product", "reason": "occupied"},
            {"route": "eligible", "repo": _self()},
        ],
        working={
            "actions": [],
            "remaining_ready": 2,
            "ready_by_repo": {
                "a/product": [{"number": 2}],
                _self(): [{"number": 1}],
            },
        },
    )
    assert out["clean_repos"] == [] and out["lane"] == "product"

"""PR-first order is authored only in the factory Fala."""

from lokay.graph_run import describe_package


def test_factory_authors_departments_in_canon_order():
    path = next(p for p in describe_package()["paths"] if p["id"] == "factory_pass")
    ids = [n["id"] for n in path["nodes"]]
    conduction = {n["id"]: n["conduction"] for n in path["nodes"]}
    assert "select_issue_triage_department" in ids
    assert "select_executor_department" in ids
    assert "select_pr_triage_department" in ids
    assert ids.index("select_issue_triage_department") < ids.index("select_executor_department")
    assert ids.index("select_executor_department") < ids.index("select_pr_triage_department")
    assert "reap_stale_worktrees" not in conduction["select_pr_triage_department"]
    assert "reap_stale_worktrees" not in conduction["select_issue_triage_department"]


def test_tick_is_only_a_factory_fala_facade():
    import inspect
    from lokay.compose import tick

    src = inspect.getsource(tick)
    assert (
        "compose_factory_pass" in src
        and "run_survey_prs" not in src
        and "run_plan_pass" not in src
    )

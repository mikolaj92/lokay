"""PR-first order is authored only in the factory Fala."""

from lokay.graph_run import describe_package


def test_factory_authors_pr_closeout_beside_implementation_not_as_gate():
    path = next(p for p in describe_package()["paths"] if p["id"] == "factory_pass")
    ids = [n["id"] for n in path["nodes"]]
    conduction = {n["id"]: n["conduction"] for n in path["nodes"]}
    assert "prs" in ids
    assert "issues" in ids
    assert ids.index("prs") < ids.index("issues")
    assert "reap_stale_worktrees" not in conduction["prs"]
    assert "reap_stale_worktrees" not in conduction["issues"]


def test_tick_is_only_a_factory_fala_facade():
    import inspect
    from lokay.compose import tick

    src = inspect.getsource(tick)
    assert (
        "compose_factory_pass" in src
        and "run_survey_prs" not in src
        and "run_plan_pass" not in src
    )

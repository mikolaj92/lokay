"""PR-first order is authored only in the factory Fala."""

from lokay.graph_run import describe_package


def test_factory_authors_pr_closeout_beside_implementation_not_as_gate():
    path = next(p for p in describe_package()["paths"] if p["id"] == "factory_pass")
    ids = [n["id"] for n in path["nodes"]]
    conduction = {n["id"]: n["conduction"] for n in path["nodes"]}
    assert "closeout_prs" in ids
    assert "closeout_prs" not in conduction["select_implement"]
    assert ids.index("select_implement") < ids.index("dispatch_implement")
    assert ids.index("select_implement") < ids.index("closeout_prs")


def test_tick_is_only_a_factory_fala_facade():
    import inspect
    from lokay.compose import tick

    src = inspect.getsource(tick)
    assert (
        "compose_factory_pass" in src
        and "run_survey_prs" not in src
        and "run_plan_pass" not in src
    )

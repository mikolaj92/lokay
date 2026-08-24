"""PR-first order is authored only in the factory Fala."""

from lokay.graph_run import describe_package


def test_factory_authors_pr_closeout_before_implementation_selection():
    path = next(p for p in describe_package()["paths"] if p["id"] == "factory_pass")
    ids = [n["id"] for n in path["nodes"]]
    assert (
        ids.index("closeout_prs")
        < ids.index("select_implement")
        < ids.index("dispatch_implement")
    )


def test_tick_is_only_a_factory_fala_facade():
    import inspect
    from lokay.compose import tick

    src = inspect.getsource(tick)
    assert (
        "compose_factory_pass" in src
        and "run_survey_prs" not in src
        and "run_plan_pass" not in src
    )

"""Contracts for minimal direct product entry atoms."""


def test_product_entry_classifier_is_closed():
    from lokay.proc.classify_product_entry_preflight import classify

    assert classify({"ok": True})["route"] == "product"
    assert classify({"ok": False})["route"] == "terminal"


def test_compose_run_routing_is_delegated_to_authored_entry():
    import inspect

    from lokay.compose.run import _compose_run

    source = inspect.getsource(_compose_run)
    assert "preflight.get" not in source and "product_pass_budget_subflow" not in source

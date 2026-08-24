"""Read authored graph identifiers without running a graph."""


def describe() -> dict:
    try:
        from lokay.graph_run import describe_package

        graphs = [p["id"] for p in describe_package().get("paths") or []]
        return {"ok": True, "graphs": graphs}
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "graphs": [], "description_error": str(exc)}

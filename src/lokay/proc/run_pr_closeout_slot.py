"""Run one closeout_pr child for an authored repository slot. No loop."""

from lokay.proc.closeout_pr_subflow import run as run_one


def run(selected: dict, *, config_path: str | None, live: bool) -> dict:
    if selected.get("route") != "closeout":
        return {"ok": True, "route": "empty", "slot": selected.get("slot")}
    nested = run_one(selected=selected, config_path=config_path, live=live)
    # Always ok so Fala can record the nested failure. Reduce fail-closes.
    return {"ok": True, "result": nested if isinstance(nested, dict) else {}}

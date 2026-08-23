"""Run the authored SHA-bound PR-triage sub-Fala once."""

from lokay.compose.pr_triage import compose_pr_triage


def triage(gate: dict, *, config_path: str | None) -> dict:
    item = gate["inspected"]
    out = compose_pr_triage(
        config_path=config_path,
        repo=item["repo"],
        pr_number=item["pr_number"],
        branch=item["head"],
        live=True,
    )
    return {"ok": True, "triage": out}

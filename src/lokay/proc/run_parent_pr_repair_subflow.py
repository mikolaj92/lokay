"""Parent NODE slot: invoke `pr_repair` after an authored sieve verdict."""

from __future__ import annotations

from typing import Any

from lokay.compose.pr_repair import compose_pr_repair


def run(selected: dict[str, Any], *, config_path: str | None, live: bool) -> dict[str, Any]:
    result = compose_pr_repair(
        config_path=config_path,
        repo=str(selected["repo"]),
        pr_number=int(selected["pr"]),
        branch=str(selected["branch"]),
        review=dict(selected.get("review") or {}),
        live=live,
    )
    return {"ok": True, "route": "completed", "repair": result}

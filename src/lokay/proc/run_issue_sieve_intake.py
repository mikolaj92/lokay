"""Sieve child: intake check. Zero code. Zero PR."""

from lokay.proc.intake_check_subflow import run as run_intake


def run(selected: dict, *, config_path: str | None, live: bool) -> dict:
    if str(selected.get("route") or "") != "intake":
        return {
            "ok": True,
            "route": "skip",
            "reason": str(selected.get("reason") or "not_intake"),
        }
    return run_intake(
        config_path=config_path,
        live=live,
        repo=str(selected.get("repo") or ""),
        issue=int(selected.get("issue") or 0),
        check=str(selected.get("reason") or "intake"),
    )

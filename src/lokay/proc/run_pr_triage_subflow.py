"""NODE slot: launch child Fala `pr_triage`. Do not implement that subgraph here."""

from lokay.graph_run import run_path

# Named slot for the PR sieve only. The parent `prs` graph consumes its
# verdict and may invoke the separate `pr_repair` department afterwards.
CHILD_PATH = "pr_triage"


def run(target: dict, *, config_path: str | None, live: bool) -> dict:
    result = run_path(
        path_id=CHILD_PATH,
        repo=str(target["repo"]),
        pr=int(target["pr"]),
        branch=str(target["branch"]),
        config_path=config_path,
        live=live,
    )
    review = result.get("review") if isinstance(result.get("review"), dict) else {}
    return {
        "ok": True,
        **target,
        "route": "completed",
        "triage": {
            "repairable": bool(result.get("repairable")),
            "reason": result.get("reason"),
            "review": review,
            "merged": bool(result.get("merged")),
            "waiting": bool(result.get("waiting")),
        },
    }

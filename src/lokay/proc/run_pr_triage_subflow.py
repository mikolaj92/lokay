"""NODE slot: launch child Fala `pr_triage`. Do not implement that subgraph here."""

from lokay.graph_run import run_path

# Named slot for a separate NODE agent. That agent owns `pr_triage` (and
# nested `pr_repair`). This prs NODE only starts the child path.
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
    return {"ok": True, **target, "route": "completed", "triage": result}

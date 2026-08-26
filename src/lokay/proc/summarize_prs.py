"""Receipt for one PRs child pass."""


def summarize(picked: dict, triage_run: dict) -> dict:
    return {
        "ok": True,
        "result": {
            "pr": picked.get("pr"),
            "repo": picked.get("repo"),
            "route": picked.get("route") or "none",
            "triaged": triage_run.get("route"),
        },
    }

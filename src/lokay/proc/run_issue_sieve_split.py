"""Sieve child: issue_split. Marks/children only. No ai/fix branch."""

from lokay.proc.issue_split_subflow import invoke


def run(selected: dict, *, config_path: str | None, live: bool) -> dict:
    if str(selected.get("route") or "") != "split":
        return {
            "ok": True,
            "route": "skip",
            "reason": str(selected.get("reason") or "not_split"),
        }
    return invoke(
        config_path=config_path,
        repo=str(selected.get("repo") or ""),
        issue=int(selected.get("issue") or 0),
        decision={"reason": str(selected.get("reason") or "agent_split")},
        live=live,
    )

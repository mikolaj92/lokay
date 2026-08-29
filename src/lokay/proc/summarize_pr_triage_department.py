"""PR sieve receipt. Review + merge. Repair is a verdict, not a child start."""


def summarize(picked: dict, triage_run: dict, verdict: dict) -> dict:
    chosen = dict(verdict or {})
    triage = chosen.get("triage") if isinstance(chosen.get("triage"), dict) else {}
    if not triage:
        blob = triage_run.get("triage") if isinstance(triage_run.get("triage"), dict) else {}
        triage = dict(blob)
    return {
        "ok": True,
        "department": "pr_triage",
        "route": chosen.get("route") or triage_run.get("route") or picked.get("route") or "none",
        "verdict": chosen.get("verdict") or "none",
        "repo": chosen.get("repo") or picked.get("repo"),
        "pr": chosen.get("pr") or picked.get("pr"),
        "branch": chosen.get("branch") or picked.get("branch"),
        "triage": {
            "repairable": bool(triage.get("repairable") or chosen.get("repairable")),
            "reason": triage.get("reason") or chosen.get("reason"),
            "review": dict(triage.get("review") or {}),
            "merged": bool(triage.get("merged") or chosen.get("merged")),
            "waiting": bool(triage.get("waiting") or chosen.get("waiting")),
        },
        "repair_started": False,
    }

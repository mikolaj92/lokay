"""Select one of two explicit ready-label probes for one repository."""


def select(repo: dict, previous: dict, *, slot: int) -> dict:
    labels = list(repo.get("labels") or [])
    if (
        repo.get("route") != "labels"
        or previous.get("route") == "failed"
        or slot < 1
        or slot > len(labels)
    ):
        return {
            "ok": True,
            "route": "done" if repo.get("route") == "labels" else "empty",
            "slot": slot,
            "repo": str(repo.get("repo") or ""),
        }
    return {
        "ok": True,
        "route": "probe",
        "slot": slot,
        "repo": repo["repo"],
        "label": labels[slot - 1],
    }

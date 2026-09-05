"""Physically validate the authoritative localization candidate paths."""

from lokay.localize import _norm_rel


def validate(
    request: dict, inspected: dict, candidate: dict, agent_request: dict
) -> dict:
    tree = set(inspected.get("tree") or [])
    extras = [_norm_rel(x) for x in request.get("extras") or [] if _norm_rel(x)]
    raw = [_norm_rel(x) for x in candidate.get("paths") or [] if _norm_rel(x)]
    source = str(candidate.get("source") or "deterministic")
    # Existing files/directories are valid. A new file is also valid when its
    # parent directory already exists; localization is an edit boundary, not a
    # ban on creating the implementation requested by the ticket.
    def belongs_to_tree(path: str) -> bool:
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        return path in tree or bool(parent and parent in tree and "." in path.rsplit("/", 1)[-1])

    accepted = [
        x for x in dict.fromkeys([*extras, *raw]) if belongs_to_tree(x)
    ]
    return {
        "ok": True,
        "route": "write" if accepted else "terminal",
        "paths": accepted,
        "seed_paths": candidate.get("seed_paths") or [],
        "matched_tokens": candidate.get("matched_tokens") or [],
        "notes": candidate.get("notes") or [],
        "source": source,
        "reason": "empty_paths" if not accepted else "",
    }

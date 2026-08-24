"""Build one deterministic localization candidate from seed and tree facts."""

from pathlib import Path

from lokay.localize import build_localization


def build(request: dict) -> dict:
    loc = build_localization(
        worktree=(
            Path(request["worktree"]) if Path(request["worktree"]).is_dir() else None
        ),
        seed_text=request["seed"],
        extra_paths=request["extras"],
        max_paths=request["max_paths"],
    )
    return {
        "ok": True,
        "route": "candidate",
        "paths": list(loc.paths),
        "seed_paths": list(loc.seed_paths),
        "matched_tokens": list(loc.matched_tokens),
        "notes": list(loc.notes),
        "source": loc.source,
    }

"""Read one existing localization evidence fact."""

from pathlib import Path

from lokay.localize import load_existing_localize_paths, walk_repo_tree


def inspect(request: dict) -> dict:
    root = Path(request["worktree"])
    return {
        "ok": True,
        "worktree_exists": root.is_dir(),
        "existing": list(
            load_existing_localize_paths(
                root if root.is_dir() else None,
                issue=request.get("issue"),
            )
        ),
        "tree": list(walk_repo_tree(root)) if root.is_dir() else [],
    }

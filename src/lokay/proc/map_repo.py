"""Map one checkout before triage or coding. Empty when ripwire is absent."""

from __future__ import annotations

from pathlib import Path

from lokay.ripwire import ranked_paths, repo_map, task_from_issue

_MEMORY_ROOTS = (".lokay/memory", ".lokay/skills", ".lokay/lessons")
_FEATURE_MAP = ".lokay/memory/feature-map.md"


def memory_evidence(worktree: str) -> dict:
    """Committed memory files, or nothing. Never invent a map."""
    root = Path(worktree) if worktree else None
    files: list[str] = []
    if root is not None and root.is_dir():
        for rel in _MEMORY_ROOTS:
            base = root / rel
            if not base.is_dir():
                continue
            files.extend(
                path.relative_to(root).as_posix()
                for path in sorted(base.rglob("*.md"))
                if path.is_file()
            )
    feature = root / _FEATURE_MAP if root is not None else None
    text = ""
    if feature is not None and feature.is_file():
        text = feature.read_text(encoding="utf-8")
    return {"memory": sorted(files), "feature_map": text}


def map_repo(
    *,
    worktree: str = "",
    title: str = "",
    body: str = "",
) -> dict:
    task = task_from_issue(title, body)
    text = repo_map(worktree, task=task)
    paths = list(ranked_paths(worktree, task=task, raw=text))
    evidence = memory_evidence(worktree)
    return {
        "ok": True,
        "route": "mapped" if text else "empty",
        "map": text,
        "paths": paths,
        "source": "ripwire" if text else "missing",
        "memory": evidence["memory"],
        "feature_map": evidence["feature_map"],
    }

"""Optional ripwire map of a checkout. Empty when the binary is missing."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

_MAX_CHARS = 12_000
_MAX_PATHS = 24
_TIMEOUT_SECONDS = 20
_PATH_ATTR = re.compile(r'\bp="(\./[^"]+)"')


def repo_map(worktree: Path | str | None, *, task: str = "") -> str:
    """Return a ripwire map, or empty when the tool or checkout is absent."""
    root = Path(worktree) if worktree else None
    if root is None or not root.is_dir():
        return ""
    binary = shutil.which("ripwire")
    if not binary:
        return ""
    argv = [binary, str(root)]
    needle = str(task or "").strip()
    if needle:
        argv.append(f"--for={needle}")
    try:
        proc = subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()[:_MAX_CHARS]


def ranked_paths(
    worktree: Path | str | None,
    *,
    task: str = "",
    limit: int = _MAX_PATHS,
    raw: str | None = None,
) -> tuple[str, ...]:
    """Existing checkout paths mentioned in a ripwire map. Empty when missing."""
    root = Path(worktree) if worktree else None
    text = raw if raw is not None else repo_map(root, task=task)
    if root is None or not text:
        return ()
    cap = max(1, int(limit or _MAX_PATHS))
    found: list[str] = []
    for match in _PATH_ATTR.finditer(text):
        rel = match.group(1).removeprefix("./")
        if not rel or ".." in rel.split("/"):
            continue
        if not (root / rel).exists():
            continue
        found.append(rel)
        if len(found) >= cap:
            break
    return tuple(dict.fromkeys(found))


def task_from_issue(title: str, body: str | None = None) -> str:
    text = " ".join(part.strip() for part in (title, body or "") if str(part).strip())
    return " ".join(text.split())[:240]

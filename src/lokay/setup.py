from __future__ import annotations

import os
from pathlib import Path
from subprocess import TimeoutExpired

from lokay.build import child_env
from lokay.run import run_process
from lokay.state import rounds_append


def prepare_dependencies(worktree: Path, repo: dict, issue: int) -> None:
    if "setup" in repo:
        commands = [(worktree, repo["setup"])] if repo["setup"] else []
    else:
        commands = []
        for directory, dirs, files in os.walk(worktree):
            path = Path(directory)
            depth = len(path.relative_to(worktree).parts)
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "node_modules") if depth < 2 else []
            for lock, argv in (("uv.lock", ["uv", "sync", "--frozen"]),
                               ("package-lock.json", ["npm", "ci"])):
                if lock in files:
                    commands.append((path, argv))
    for cwd, argv in commands:
        try:
            proc = run_process(argv, cwd=cwd, env=child_env(dict(os.environ)), timeout=600)
            log = f"exit={proc.returncode}\n{proc.stdout or ''}{proc.stderr or ''}"
        except (OSError, TimeoutExpired) as exc:
            log = f"failed: {exc}"
        rounds_append(repo["name"], issue, f"Setup: {cwd.relative_to(worktree)}: {argv}\n{log[-3000:]}")

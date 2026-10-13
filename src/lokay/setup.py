from __future__ import annotations

import os
import shutil
from pathlib import Path
from subprocess import TimeoutExpired

from lokay.build import child_env, generated_cleanup
from lokay.run import run_process
from lokay.state import rounds_append


def prepare_dependencies(worktree: Path, repo: dict, issue: int) -> dict:
    if "setup" in repo:
        commands = [(worktree, repo["setup"])] if repo["setup"] else []
    else:
        commands = []
        for directory, dirs, files in os.walk(worktree):
            path = Path(directory)
            depth = len(path.relative_to(worktree).parts)
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "node_modules") if depth < 2 else []
            for lock, argv in (("uv.lock", ["uv", "sync", "--frozen", "--all-extras"]),
                               ("package-lock.json", ["npm", "ci"])):
                if lock in files:
                    commands.append((path, argv))
    logs = []
    failed = []
    with generated_cleanup(worktree):
        for cwd, argv in commands:
            venv = cwd / ".venv"

            def remove_venv():
                if venv.is_symlink() or venv.is_file():
                    venv.unlink()
                elif venv.exists():
                    shutil.rmtree(venv)

            ok = False
            try:
                python = venv / "bin/python"
                if (venv.exists() or venv.is_symlink()) and not (python.is_file() and os.access(python, os.X_OK)):
                    remove_venv()
                env = child_env(dict(os.environ))
                env["UV_PROJECT_ENVIRONMENT"] = str(venv.absolute())
                proc = run_process(argv, cwd=cwd, env=env, timeout=600)
                log = f"exit={proc.returncode}\n{proc.stdout or ''}{proc.stderr or ''}"
                if proc.returncode != 0 and "not a valid Python environment" in log:
                    remove_venv()
                    proc = run_process(argv, cwd=cwd, env=env, timeout=600)
                    log += f"\nRetry:\nexit={proc.returncode}\n{proc.stdout or ''}{proc.stderr or ''}"
                ok = proc.returncode == 0
            except (OSError, TimeoutExpired) as exc:
                log = f"failed: {exc}"
            log = f"Setup: {cwd.relative_to(worktree)}: {argv}\n{log}"
            logs.append(log)
            if not ok:
                failed.append({"warstwa": "setup", "plik": "", "log": log})
            rounds_append(repo["name"], issue, log[-3000:])
    return {"log": "\n".join(logs), "failed": failed}

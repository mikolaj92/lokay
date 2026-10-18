from __future__ import annotations

import os
import shutil
from pathlib import Path
from lokay.effects.pi import TimeoutExpired

from lokay.build import generated_cleanup
from lokay.effects.git import git
from lokay.effects.pi import pi_env, run_process
from lokay.store import rounds_append


def remove_venv(worktree: Path, venv: Path) -> None:
    if venv.is_symlink() or not venv.is_dir():
        return
    if not git(worktree, "--literal-pathspecs", "ls-files", "--", venv.relative_to(worktree).as_posix()):
        shutil.rmtree(venv)


def repair_venvs(worktree: Path) -> None:
    for directory, dirs, files in os.walk(worktree):
        path = Path(directory)
        depth = len(path.relative_to(worktree).parts)
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "node_modules") if depth < 3 else []
        if depth and "pyproject.toml" not in files:
            continue
        venv = path / ".venv"
        if venv.is_symlink() or not venv.is_dir():
            continue
        try:
            proc = run_process([str(venv.absolute() / "bin/python"), "-c", ""], cwd=path, timeout=10)
            if proc.returncode == 0:
                continue
        except (OSError, TimeoutExpired):
            pass
        remove_venv(worktree, venv)


def prepare_dependencies(worktree: Path, repo: dict, issue: int) -> dict:
    if "setup" in repo:
        commands = [(worktree, repo["setup"])] if repo["setup"] else []
    else:
        commands = []
        for directory, dirs, files in os.walk(worktree):
            path = Path(directory)
            depth = len(path.relative_to(worktree).parts)
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "node_modules") if depth < 2 else []
            for lock, argv in (("uv.lock", ["uv", "sync", "--locked", "--all-extras"]),
                               ("package-lock.json", ["npm", "ci"])):
                if lock in files:
                    commands.append((path, argv))
    logs = []
    failed = []
    with generated_cleanup(worktree) as drifted:
        repair_venvs(worktree)
        for cwd, argv in commands:
            venv = cwd / ".venv"
            ok = False
            try:
                env = pi_env(dict(os.environ), worktree)
                try:
                    env["UV_PROJECT_ENVIRONMENT"] = str(venv.absolute())
                    env["UV_LOCKED"] = "1"
                    proc = run_process(argv, cwd=cwd, env=env, timeout=3600)
                    log = f"exit={proc.returncode}\n{proc.stdout or ''}{proc.stderr or ''}"
                    if proc.returncode != 0 and "not a valid Python environment" in log:
                        repair_venvs(worktree)
                        proc = run_process(argv, cwd=cwd, env=env, timeout=3600)
                        log += f"\nRetry:\nexit={proc.returncode}\n{proc.stdout or ''}{proc.stderr or ''}"
                    if proc.returncode == 0 and (venv / "bin" / "playwright").exists():
                        proc = run_process([str(venv / "bin" / "playwright"), "install", "chromium"],
                                           cwd=cwd, env=env, timeout=3600)
                        log += f"\nexit={proc.returncode}\n{proc.stdout or ''}{proc.stderr or ''}"
                    ok = proc.returncode == 0
                finally:
                    shutil.rmtree(env["LOKAY_STATE_DIR"], ignore_errors=True)
            except (OSError, TimeoutExpired) as exc:
                log = f"failed: {exc}"
            log = f"Setup: {cwd.relative_to(worktree)}: {argv}\n{log}"
            logs.append(log)
            if not ok:
                failed.append({"warstwa": "setup", "plik": "", "log": log})
            rounds_append(repo["name"], issue, log[-3000:])
    logs.extend(f"lockfile drift: {name}" for name in drifted)
    return {"log": "\n".join(logs), "failed": failed}

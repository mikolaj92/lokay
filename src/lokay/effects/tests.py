from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

UV_CACHE_DIR = (Path(tempfile.gettempdir()) / "lokay-uv-cache").resolve()

def executed_tests(log: str) -> int:
    patterns = (
        r"(\d+) passed",
        r"^Ran (\d+) tests?",
        r"Executed (\d+) tests?",
        r"Test run with (\d+) tests?",
        r"(?:^#|ℹ) pass (\d+)",
        r"Tests:\s+(\d+) passed",
        r"replay: (\d+)/\d+ transitions ok",
    )
    return sum(int(match) for pattern in patterns for match in re.findall(pattern, log, re.MULTILINE))


def check_uv_lock(cwd: Path) -> tuple[str, str]:
    from subprocess import TimeoutExpired
    from lokay.effects.pi import run_process

    env = {**os.environ, "UV_OFFLINE": "1"}
    for offline in (True, False):
        if not offline:
            env.pop("UV_OFFLINE", None)
        try:
            proc = run_process(["uv", "lock", "--check"], cwd=cwd, timeout=60, env=env, record=True)
        except (OSError, TimeoutExpired) as exc:
            return "unknown", f"uv lock checks unavailable: {exc}"
        if proc.returncode == 0:
            return "pass", "uv lock checks passed"
        log = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        if re.search(r"lockfile[^\n]*needs to be updated", log, re.IGNORECASE):
            return "fail", "uv.lock is out of date with pyproject.toml: run `uv lock`"
        unavailable = re.search(
            r"offline mode|network connectivity is disabled|not (?:found|available) in (?:the )?cache"
            r"|not found in (?:the )?package cache|failed to (?:fetch|download|connect)"
            r"|network (?:is unreachable|error)|unable to (?:fetch|download|connect)"
            r"|connection (?:refused|reset)|dns error",
            log, re.IGNORECASE)
        if not offline or not unavailable:
            return "unknown", "uv lock checks unavailable: " + log[-1000:]
    return "unknown", "uv lock checks unavailable"


def base_tests_on_head(worktree: Path, sha: str, paths: list[str], config: dict, issue: int) -> dict:
    from lokay.effects.git import base_branch, git
    from lokay.setup import prepare_dependencies

    base = git(worktree, "merge-base", sha, f"origin/{base_branch(worktree)}")
    with tempfile.TemporaryDirectory(prefix="lokay-base-tests-") as temporary:
        tmp = Path(temporary) / "checkout"
        git(worktree, "worktree", "add", "--detach", str(tmp), sha)
        try:
            git(tmp, "checkout", base, "--", *paths)
            prepare_dependencies(tmp, config, issue)
            return local_ci(sha, [config["test"]], tmp, timeout=config.get("test_timeout", 600))
        finally:
            git(worktree, "worktree", "remove", "--force", str(tmp))


def local_ci(sha: str, tests: list[list[str]], cwd, timeout: int = 600) -> dict:
    from subprocess import CompletedProcess, TimeoutExpired
    from lokay.effects.pi import run_process
    from lokay.effects.git import git_try
    from lokay.build import generated_cleanup

    cache = UV_CACHE_DIR
    env = {**os.environ, "UV_CACHE_DIR": str(cache), "UV_LOCKED": "1"}

    def execute(argv):
        if any(re.search(r"(?:^|[\s;|&])(?:--cache-dir(?:=|\s|$)|UV_CACHE_DIR=)", arg)
               for arg in argv):
            return CompletedProcess(argv, 1, "", "configured command must not override UV_CACHE_DIR or --cache-dir"), False
        try:
            root = Path(cwd).resolve()
            if any((path / ".git").exists() or (path / ".git").is_symlink()
                   for path in (root, *root.parents)):
                code, out, err = git_try(root, "rev-parse", "--show-toplevel", timeout=30)
                if code:
                    return CompletedProcess(argv, 1, "", err or out or "git rev-parse failed"), False
                top = out.strip()
                if not top or not Path(top).is_absolute():
                    return CompletedProcess(argv, 1, "", "git returned an invalid repository top-level"), False
                root = Path(top).resolve()
            if cache.is_relative_to(root):
                return CompletedProcess(argv, 1, "", f"UV_CACHE_DIR must be outside repository or cwd: {cache}"), False
            timed_out = False
            with generated_cleanup(Path(cwd)) as drifted:
                try:
                    proc = run_process(argv, cwd=cwd, timeout=timeout, env=env, record=True)
                except TimeoutExpired:
                    proc = CompletedProcess(argv, 1, "", f"tests timed out after {timeout} s")
                    timed_out = True
                except OSError as exc:
                    proc = CompletedProcess(argv, 1, "", str(exc))
            if drifted:
                proc.stderr = (proc.stderr or "") + "\n" + "\n".join(
                    f"lockfile drift: {name}" for name in drifted)
            return proc, timed_out
        except TimeoutExpired:
            return CompletedProcess(argv, 1, "", f"tests timed out after {timeout} s"), True
        except OSError as exc:
            return CompletedProcess(argv, 1, "", str(exc)), False

    def did_run(proc):
        log = (proc.stdout or "") + (proc.stderr or "")
        markers = ("collected 0 items", "no tests ran", "error: failed to", "no solution found",
                   "modulenotfounderror", "command not found", "no such file or directory")
        if "LOKAY_TEST_CWD=" in log:
            segments = re.split(r"^LOKAY_TEST_CWD=.+$", log, flags=re.MULTILINE)[1:]
            if not all(did_run(CompletedProcess(proc.args, 0, segment, "")) for segment in segments):
                return False
        return (proc.returncode == 0
                and not re.search(r"\b0 passed\b", log)
                and not any(marker in log.lower() for marker in markers))

    failed = []
    notes = []
    logs = []
    tested_cwds = set()
    for argv in tests:
        proc, timed_out = execute(argv)
        log = (proc.stdout or "") + (proc.stderr or "")
        ran = did_run(proc)
        if not ran:
            retry, retry_timed_out = execute(argv)
            retry_log = (retry.stdout or "") + (retry.stderr or "")
            flaky = did_run(retry)
            ran = flaky
            item = {"warstwa": " ".join(argv), "plik": "", "linia": None,
                    "sha": sha, "flaky": flaky, "log": log + "\nRetry:\n" + retry_log,
                    "timeout": timeout if timed_out or retry_timed_out else None}
            (notes if flaky else failed).append(item)
            log = item["log"]
        if ran:
            directories = re.findall(r"^LOKAY_TEST_CWD=(.+)$", log, re.MULTILINE)
            tested_cwds.update(str(Path(path).resolve()) for path in directories or [cwd])
        logs.append(log)
    return {"result": "red" if failed else "green", "sha": sha,
            "tested": bool(tested_cwds), "tested_cwds": sorted(tested_cwds),
            "failed": failed, "notes": notes, "log": "\n".join(logs),
            "executed": sum(executed_tests(log) for log in logs)}

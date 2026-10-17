from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

def local_ci(sha: str, tests: list[list[str]], cwd, timeout: int = 600) -> dict:
    from subprocess import CompletedProcess, TimeoutExpired
    from lokay.effects.pi import run_process
    from lokay.build import generated_cleanup

    cache = (Path(tempfile.gettempdir()) / "lokay-uv-cache").resolve()
    env = {**os.environ, "UV_CACHE_DIR": str(cache)}

    def execute(argv):
        if cache.is_relative_to(Path(cwd).resolve()):
            return CompletedProcess(argv, 1, "", f"UV_CACHE_DIR must be outside cwd: {cache}"), False
        if any(re.search(r"(?:^|[\s;|&])(?:--cache-dir(?:=|\s|$)|UV_CACHE_DIR=)", arg)
               for arg in argv):
            return CompletedProcess(argv, 1, "", "configured command must not override UV_CACHE_DIR or --cache-dir"), False
        try:
            with generated_cleanup(Path(cwd)):
                return run_process(argv, cwd=cwd, timeout=timeout, env=env), False
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
        summary = re.search(
            r"\b[1-9]\d* passed\b|\bRan [1-9]\d* tests?\b|\bExecuted [1-9]\d* tests?\b"
            r"|\btests? [1-9]\d*\b|\breplay: ([1-9]\d*)/\1 transitions ok\b|\b\w+ tests passed\b", log)
        return (proc.returncode == 0 and summary is not None
                and not re.search(r"\b0 passed\b", log)
                and not any(marker in log.lower() for marker in markers))

    failed = []
    notes = []
    logs = []
    tested_cwds = set()
    if not tests:
        notes.append({"warstwa": "tests", "plik": "", "log": "no tests configured"})
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
            "failed": failed, "notes": notes, "log": "\n".join(logs)}

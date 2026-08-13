"""Atomic: is a live Pi already running for this repo?

One job: inspect a process listing (live ``ps``, or ``--ps-file`` fixture text)
and report whether ``owner/name`` already has a Pi. Mutex: one live Pi per repo.

JSON: ``{busy: false}`` or ``{busy: true, pids: [...]}``.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from lokay.envelope import emit_exit, err, ok

_REPO_RE = re.compile(r"^([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)$")
_NAME_CHAR = r"[A-Za-z0-9._-]"
_PS_ARGV = (
    ("ps", "-axww", "-o", "pid=,command="),
    ("ps", "-axww", "-o", "pid=,args="),
    ("ps", "auxww"),
)


def parse_repo(raw: str) -> str:
    text = (raw or "").strip()
    if not _REPO_RE.fullmatch(text):
        raise ValueError("repo must be owner/name")
    return text


def _is_header(line: str) -> bool:
    fields = {part.upper() for part in line.split()}
    return "PID" in fields and bool(fields & {"COMMAND", "CMD", "ARGS"})


def _parse_line(line: str) -> tuple[int, str] | None:
    parts = line.split()
    if len(parts) < 2:
        return None
    if parts[0].isdigit():
        pid = int(parts[0])
        command = line[line.find(parts[0]) + len(parts[0]) :].strip()
        return (pid, command) if command else None
    if parts[1].isdigit():
        pid = int(parts[1])
        command = " ".join(parts[10:]) if len(parts) > 10 else " ".join(parts[2:])
        return (pid, command) if command else None
    return None


def parse_ps(text: str) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or _is_header(line):
            continue
        parsed = _parse_line(line)
        if parsed is None:
            continue
        rows.append(parsed)
    return rows


def _is_pi_command(command: str) -> bool:
    argv0 = command.split(None, 1)[0].strip("\"'") if command.strip() else ""
    return argv0.rsplit("/", 1)[-1] == "pi"



def _is_issue_to_pr_command(command: str) -> bool:
    return "lokay.compose.issue_to_pr" in command or "lokay-issue-to-pr" in command


def _holds_repo(command: str, repo: str) -> bool:
    if not _mentions_repo(command, repo):
        return False
    return _is_pi_command(command) or _is_issue_to_pr_command(command)

def _mentions_repo(command: str, repo: str) -> bool:
    owner, name = repo.split("/", 1)
    for needle in (f"{owner}/{name}", f"{owner}__{name}"):
        pat = rf"(?<!{_NAME_CHAR}){re.escape(needle)}(?!{_NAME_CHAR})"
        if re.search(pat, command):
            return True
    return False


def pids_for_repo(ps_text: str, repo: str) -> list[int]:
    found: list[int] = []
    seen: set[int] = set()
    for pid, command in parse_ps(ps_text):
        if pid <= 0 or pid in seen:
            continue
        if _holds_repo(command, repo):
            seen.add(pid)
            found.append(pid)
    found.sort()
    return found


def inspect_mutex(*, repo: str, ps_text: str) -> dict:
    pids = pids_for_repo(ps_text, parse_repo(repo))
    if pids:
        return ok(busy=True, pids=pids)
    return ok(busy=False)


def _read_ps_file(path: str) -> str:
    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError(f"ps-file not found: {path}")
    return file.read_text(encoding="utf-8", errors="replace")


def _live_ps_text() -> str:
    last = "ps failed"
    for argv in _PS_ARGV:
        try:
            completed = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            last = str(exc)
            continue
        if completed.returncode == 0:
            return completed.stdout or ""
        last = (completed.stderr or completed.stdout or last).strip() or last
    raise RuntimeError(last)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-repo-mutex")
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument(
        "--ps-file",
        default="",
        help="fixture ps(1) text (omit to inspect live processes)",
    )
    args = parser.parse_args(argv)
    try:
        ps_text = _read_ps_file(args.ps_file) if args.ps_file else _live_ps_text()
        return emit_exit(inspect_mutex(repo=str(args.repo), ps_text=ps_text))
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))


if __name__ == "__main__":
    raise SystemExit(main())

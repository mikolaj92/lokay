"""Atomic: is a live coder already running for this repo?

One job: inspect a process listing (live ``ps``, or ``--ps-file`` fixture text)
and report whether ``owner/name`` already has a Pi or issue-to-PR process.
Mutex: one live coder per repo.

JSON: ``{busy: false}`` or ``{busy: true, pids: [...]}``.
"""

from __future__ import annotations

import argparse
import re
import shlex
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



def _command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        # A process command can contain an incomplete quoted prompt. Keep
        # mutex inspection useful for the rest of the argv rather than
        # treating an unparsable ps row as a live holder.
        return command.split()


def _is_issue_to_pr_command(command: str) -> bool:
    tokens = _command_tokens(command)
    for index, token in enumerate(tokens):
        if token == "lokay.compose.issue_to_pr":
            return index > 0 and tokens[index - 1] == "-m"
        if token.rsplit("/", 1)[-1] == "lokay-issue-to-pr":
            return True
    return False


def _mentions_issue_to_pr_repo(command: str, repo: str) -> bool:
    tokens = _command_tokens(command)
    for index, token in enumerate(tokens):
        if token == "--repo" and index + 1 < len(tokens):
            if tokens[index + 1] == repo:
                return True
        elif token.startswith("--repo=") and token.removeprefix("--repo=") == repo:
            return True
    return False


def _holds_repo(command: str, repo: str) -> bool:
    if _is_issue_to_pr_command(command):
        return _mentions_issue_to_pr_repo(command, repo)
    return _is_pi_command(command) and _mentions_repo(command, repo)


def _mentions_repo(command: str, repo: str) -> bool:
    # Bare ``owner/name`` inside a quoted fixture/prompt is not a hold.
    # Live Pi/issue_to_pr mention a repo via worktree slug, GitHub URL,
    # ``--repo``, or the mill ``Repository:`` line.
    owner, name = repo.split("/", 1)
    slash = f"{owner}/{name}"
    slug = f"{owner}__{name}"
    patterns = (
        rf"(?<!{_NAME_CHAR}){re.escape(slug)}(?!{_NAME_CHAR})",
        rf"(?:github\.com[/:]|git@github\.com:){re.escape(slash)}(?!{_NAME_CHAR})",
        rf"--repo(?:=|\s+){re.escape(slash)}(?!{_NAME_CHAR})",
        rf"Repository:\s*`?{re.escape(slash)}`?(?!{_NAME_CHAR})",
    )
    return any(re.search(pat, command) for pat in patterns)


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

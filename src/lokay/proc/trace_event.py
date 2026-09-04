"""One job: append one lokay-step JSON line to the operator trace log.

Default path ``~/.lokay/trace.jsonl`` (override with ``--file``). Each line is
``{ts, atom, repo, issue, ok, error}`` so an operator can see which atom ran
and where the lokay stuck.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok


def default_trace_path() -> Path:
    return Path.home() / ".lokay" / "trace.jsonl"


def resolve_trace_path(file: str | Path | None) -> Path:
    if file is None or str(file).strip() == "":
        return default_trace_path()
    return Path(str(file)).expanduser()


def build_event(
    *,
    atom: str,
    repo: str | None = None,
    issue: int | None = None,
    step_ok: bool = True,
    error: str | None = None,
) -> dict[str, Any]:
    repo_s = str(repo).strip() if repo is not None else ""
    err_s = str(error).strip() if error is not None else ""
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "atom": str(atom).strip(),
        "repo": repo_s or None,
        "issue": int(issue) if issue is not None else None,
        "ok": bool(step_ok),
        "error": err_s or None,
    }


def append_trace_line(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def run_trace_event(
    *,
    atom: str,
    repo: str | None = None,
    issue: int | None = None,
    step_ok: bool = True,
    error: str | None = None,
    file: str | Path | None = None,
) -> dict[str, Any]:
    name = str(atom or "").strip()
    if not name:
        return err("atom required")
    path = resolve_trace_path(file)
    event = build_event(
        atom=name, repo=repo, issue=issue, step_ok=step_ok, error=error
    )
    try:
        append_trace_line(path, event)
    except OSError as exc:
        return err(str(exc), file=str(path))
    return ok(file=str(path), event=event)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-trace-event")
    parser.add_argument("--atom", required=True, help="atom / lokay-step name")
    parser.add_argument("--repo", help="owner/name")
    parser.add_argument("--issue", type=int, help="issue number")
    status = parser.add_mutually_exclusive_group()
    status.add_argument(
        "--ok",
        dest="step_ok",
        action="store_true",
        help="step succeeded (default)",
    )
    status.add_argument(
        "--fail",
        dest="step_ok",
        action="store_false",
        help="step failed",
    )
    parser.set_defaults(step_ok=True)
    parser.add_argument("--error", help="failure / stuck text")
    parser.add_argument(
        "--file",
        help="JSONL path (default: ~/.lokay/trace.jsonl)",
    )
    args = parser.parse_args(argv)
    return emit_exit(
        run_trace_event(
            atom=str(args.atom),
            repo=args.repo,
            issue=args.issue,
            step_ok=bool(args.step_ok),
            error=args.error,
            file=args.file,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

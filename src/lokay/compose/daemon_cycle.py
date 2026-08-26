"""Fala-owned daemon cycle: product mill, stall quorum, and recovery conduction."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
from typing import Any

from lokay.config import load_config
from lokay.envelope import err, mill_glance
from lokay.fala_journal import rotate_mill_fala_journals
from lokay.graph_run import run_path
from lokay.preflight import trusted_fala_manifest


def finalize_daemon_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Lift mill glance fields and drop bulky orchestration details.

    The journal stays on disk. Launchd stdout must not inherit a multi-MiB
    JSON line when Fala wraps a productive mill in ``ok: false``.
    """
    out = dict(payload)
    glance = mill_glance(out)
    if str(glance.get("health") or "") == "progress":
        out["health"] = "progress"
    if "progress" not in out and glance.get("progress") is not None:
        out["progress"] = glance["progress"]
    remaining = glance.get("remaining")
    if isinstance(remaining, dict) and remaining and "remaining" not in out:
        out["remaining"] = remaining
    for key in ("fala", "terminal", "steps", "last"):
        out.pop(key, None)
    return out


class _PassCeiling(BaseException):
    """Interrupt orchestration without terminating its detached workers."""


def remaining_from_inflight_working(state_dir: Path) -> dict[str, Any] | None:
    """Remaining from this cycle's working.json. Never last-pass."""
    try:
        dirs = [path for path in state_dir.glob("factory-pass-*") if path.is_dir()]
    except OSError:
        return None
    dirs.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    for path in dirs:
        try:
            working = json.loads((path / "working.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(working, dict):
            continue
        issues = dict(working.get("inbox_issues_by_repo") or {})
        listed = sum(len(rows or []) for rows in issues.values())
        inbox = listed if listed else int(working.get("remaining_inbox") or 0)
        ready_by = dict(working.get("ready_by_repo") or {})
        ready = sum(len(rows or []) for rows in ready_by.values()) or int(
            working.get("remaining_ready") or 0
        )
        inbox_counts = dict(working.get("inbox_by_repo") or {})
        by_repo = []
        for repo in sorted({*issues, *ready_by, *inbox_counts}):
            by_repo.append(
                {
                    "repo": repo,
                    "inbox": len(issues.get(repo) or [])
                    or int(inbox_counts.get(repo) or 0),
                    "ready": len(ready_by.get(repo) or []),
                }
            )
        return {
            "inbox": inbox,
            "ready": ready,
            "ready_with_open_pr": int(working.get("remaining_ready_with_pr") or 0),
            "open_ai_prs": int(working.get("remaining_prs") or 0),
            "survey_errors": int(working.get("survey_errors") or 0),
            "by_repo": by_repo,
        }
    return None


def compose_daemon_cycle(
    *,
    config_path: str,
    max_passes: int = 8,
    pass_ceiling_seconds: float = 180,
) -> dict[str, Any]:
    ceiling = max(0.001, float(pass_ceiling_seconds))
    previous_handler = signal.getsignal(signal.SIGALRM)
    ceiling_expired = False

    def ceiling_reached(_signum: int, _frame: Any) -> None:
        nonlocal ceiling_expired
        ceiling_expired = True
        raise _PassCeiling

    signal.signal(signal.SIGALRM, ceiling_reached)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, ceiling)
    try:
        try:
            try:
                rotate_mill_fala_journals()
            except OSError as exc:
                return err(str(exc), reason="journal_rotate")
            return finalize_daemon_payload(
                run_path(
                    path_id="daemon_cycle",
                    repo="__lokay_daemon__",
                    config_path=config_path,
                    live=True,
                    package_path=str(trusted_fala_manifest()),
                    db_path=Path.home() / ".lokay" / "fala" / "daemon-cycle",
                    extra_inputs={"max_passes": max(1, int(max_passes))},
                )
            )
        except _PassCeiling:
            pass
        except Exception:
            # Native Fala/Mojo may translate the signal exception into a plain
            # (sometimes message-less) Exception. Only classify it as the
            # ceiling when our alarm actually fired.
            if not ceiling_expired:
                raise

        # Workers started by issue-to-PR are detached. Do not signal them when
        # releasing the daemon/launchd slot for the next tick.
        payload = {
            "ok": False,
            "health": "pass_ceiling",
            "reason": "pass_ceiling",
            "pass_ceiling_seconds": ceiling,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        try:
            receipt = load_config(config_path).state_path.parent / "last-pass.json"
        except (OSError, ValueError, FileNotFoundError):
            receipt = Path.home() / ".lokay" / "last-pass.json"
        inflight = remaining_from_inflight_working(receipt.parent)
        if inflight is not None:
            payload["remaining"] = inflight
            payload["remaining_source"] = "inflight_working"
        try:
            receipt.parent.mkdir(parents=True, exist_ok=True)
            temporary = receipt.with_name(f".{receipt.name}.{os.getpid()}.tmp")
            temporary.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            temporary.replace(receipt)
        except OSError:
            pass
        return payload
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer != (0.0, 0.0):
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)

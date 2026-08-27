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
from lokay.pass_receipt import read_pass_receipt
from lokay.proc.classify_leftover_remaining import remaining_from_receipt
from lokay.proc.merge_leftover_remaining import merge_remaining
from lokay.proc.record_inflight_remaining import remaining_from_inflight_working


def ceiling_remaining(state_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Merge last-pass remaining with inflight working. Never replace with empty."""
    last_pass = remaining_from_receipt(
        read_pass_receipt(path=state_dir / "last-pass.json")
    )
    inflight = remaining_from_inflight_working(state_dir)
    if inflight is not None:
        return merge_remaining(last_pass, inflight), "inflight_working"
    if last_pass:
        return last_pass, None
    return None, None


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
        remaining, remaining_source = ceiling_remaining(receipt.parent)
        if remaining is not None:
            payload["remaining"] = remaining
            if remaining_source:
                payload["remaining_source"] = remaining_source
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

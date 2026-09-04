"""Fala-owned daemon cycle: product lokay, stall quorum, and recovery conduction."""

from __future__ import annotations

from pathlib import Path
import signal
from typing import Any

from lokay.envelope import err, lokay_glance
from lokay.fala_journal import maintain_lokay_fala_journals, wrapper_journal_dir
from lokay.graph_run import run_path
from lokay.preflight import trusted_fala_manifest
from lokay.pass_receipt import read_pass_receipt
from lokay.proc.classify_leftover_remaining import (
    remaining_from_receipt,
    remaining_has_inbox,
)
from lokay.proc.merge_leftover_remaining import merge_remaining
from lokay.proc.record_inflight_remaining import remaining_from_inflight_working
from lokay.proc.write_pass_ceiling_receipt import write as write_pass_ceiling_receipt


def ceiling_remaining(
    state_dir: Path, *, since: float | None = None
) -> tuple[dict[str, Any] | None, str | None]:
    """Merge last-pass remaining with inflight working. Never replace with empty.

    ``since`` keeps only factory-pass dirs from this tick. A leftover directory
    from an earlier cycle is resume context, not inflight remaining.
    """
    last_pass = remaining_from_receipt(
        read_pass_receipt(path=state_dir / "last-pass.json")
    )
    inflight = remaining_from_inflight_working(state_dir, since=since)
    if inflight is not None:
        return merge_remaining(last_pass, inflight), "inflight_working"
    if last_pass and remaining_has_inbox(last_pass):
        return last_pass, None
    return None, None


def finalize_daemon_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Lift lokay glance fields and drop bulky orchestration details.

    The journal stays on disk. Launchd stdout must not inherit a multi-MiB
    JSON line when Fala wraps a productive lokay in ``ok: false``.
    """
    out = dict(payload)
    glance = lokay_glance(out)
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
                maintain_lokay_fala_journals()
            except Exception as exc:
                return err(str(exc), reason="journal_rotate")
            return finalize_daemon_payload(
                run_path(
                    path_id="daemon_cycle",
                    repo="__lokay_daemon__",
                    config_path=config_path,
                    live=True,
                    package_path=str(trusted_fala_manifest()),
                    db_path=wrapper_journal_dir("daemon_cycle"),
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
        # releasing the daemon/launchd slot for the next tick. Keep a this-tick
        # idle/progress receipt; do not let SIGALRM erase record_pass.
        return write_pass_ceiling_receipt(config_path, ceiling)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer != (0.0, 0.0):
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)

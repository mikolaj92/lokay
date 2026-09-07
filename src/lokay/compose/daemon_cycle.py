"""Fala-owned daemon cycle: product lokay, stall quorum, and recovery conduction."""

from __future__ import annotations

from pathlib import Path
import os
import signal
from typing import Any, Mapping

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


def finalize_daemon_payload(
    payload: dict[str, Any],
    *,
    config_path: str | None = None,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Lift lokay glance fields and drop bulky orchestration details.

    The journal stays on disk. Launchd stdout must not inherit a multi-MiB
    JSON line when Fala wraps a productive lokay in ``ok: false``.

    When ``ok`` is false, persist a short fail-run digest beside last-pass
    before stripping bulky Fala fields (never raises).
    """
    out = dict(payload)
    # Only when caller supplied a state target (compose passes config_path).
    # Bare finalize() in unit tests must not clobber ~/.lokay.
    if out.get("ok") is False and (state_dir is not None or config_path):
        try:
            from lokay.fail_digest import resolve_state_dir, write_digest

            target = state_dir if state_dir is not None else resolve_state_dir(config_path)
            write_digest(target, out)
        except Exception:
            pass
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



DEFAULT_PASS_CEILING_SECONDS = 2400.0


def resolve_pass_ceiling_seconds(
    explicit: float | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> float:
    """Same ceiling as LaunchAgent / lokay-service.sh (default 2400, never silent 180)."""
    if explicit is not None:
        try:
            value = float(explicit)
        except (TypeError, ValueError):
            value = DEFAULT_PASS_CEILING_SECONDS
        return max(0.001, value)
    source = env if env is not None else os.environ
    raw = str(source.get("LOKAY_PASS_CEILING_SECONDS") or "").strip()
    if not raw:
        return DEFAULT_PASS_CEILING_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_PASS_CEILING_SECONDS
    if value < 0.001:
        return DEFAULT_PASS_CEILING_SECONDS
    return value


def compose_daemon_cycle(
    *,
    config_path: str,
    max_passes: int = 8,
    pass_ceiling_seconds: float | None = None,
) -> dict[str, Any]:
    ceiling = resolve_pass_ceiling_seconds(pass_ceiling_seconds)
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
                ),
                config_path=config_path,
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

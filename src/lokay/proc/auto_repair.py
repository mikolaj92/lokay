"""Parent step (1): self_repair only when the last receipt is not moving.

Moving-forward (issue→PR→merge) passes through. Leftover exceed-slots /
leftover-probe / pass_ceiling / daemon_exec preflight are skip, never
recovery_mill. Repair does not replace steps 2–4.
"""

from __future__ import annotations

from pathlib import Path

from lokay.pass_receipt import read_pass_receipt
from lokay.proc.classify_auto_repair import classify


def run(*, config_path: str | None, live: bool) -> dict:
    from lokay.organ.common import _run_atom_main
    from lokay.proc.factory_begin_subflow import run as begin_factory
    from lokay.proc.host_ff import main as host_ff_main

    host_args = ["--config", str(config_path or "")]
    if live:
        host_args.append("--live")
    host = _run_atom_main(host_ff_main, host_args)
    if not isinstance(host, dict):
        host = {}
    begin = begin_factory(config_path=config_path, live=live)
    if not isinstance(begin, dict):
        begin = {}
    last_pass = None
    try:
        state = Path(str(begin.get("state_path") or "")).expanduser()
        if state.parent.is_dir():
            last_pass = read_pass_receipt(path=state.parent / "last-pass.json")
    except (OSError, TypeError, ValueError):
        last_pass = None
    decision = classify(begin, last_pass)
    repaired = {"ok": True, "skipped": True, "reason": decision.get("reason")}
    if decision.get("route") == "repair":
        from lokay.proc.run_initial_self_repair import run as run_repair

        preflight = begin.get("preflight") if isinstance(begin.get("preflight"), dict) else {}
        repaired = run_repair(preflight, config_path=str(config_path or ""))
    return {
        "ok": True,
        "route": "pass",
        "pass_dir": str(begin.get("pass_dir") or ""),
        "health": begin.get("health") or decision.get("health"),
        "self_repair": decision,
        "repair": repaired,
        "host_ff": host,
        "begin": begin,
    }

"""Composer: run ticks until true idle or budget exhausted.

Continuous miller for the factory: keep calling compose_tick until idle,
stall, or max_passes. Does not sleep/poll forever — one fire runs a bounded
pass budget (external schedulers re-invoke mill/tick).
"""

from __future__ import annotations

import argparse
from typing import Any

from lokay.compose.tick import compose_tick
from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import add_config_live, load_cfg


def compose_mill(
    *,
    config_path: str | None,
    live: bool,
    max_passes: int = 8,
) -> dict[str, Any]:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    if live and cfg.mode != "live":
        return err("refusing --live while config mode is not live")

    max_passes = max(1, int(max_passes))
    results: list[dict[str, Any]] = []
    total_progress = 0

    for i in range(max_passes):
        tick = compose_tick(config_path=config_path, live=live)
        results.append(
            {
                "pass": i + 1,
                "ok": tick.get("ok"),
                "health": tick.get("health"),
                "idle": tick.get("idle"),
                "progress": tick.get("progress"),
                "remaining": tick.get("remaining"),
                "error": tick.get("error"),
            }
        )
        total_progress += int(tick.get("progress") or 0)

        if tick.get("idle"):
            return ok(
                mode=cfg.mode,
                live=live,
                idle=True,
                health="idle",
                passes=i + 1,
                max_passes=max_passes,
                progress=total_progress,
                results=results,
                last=tick,
            )

        # Survey-only: one pass is enough to know work remains.
        if not live:
            return {
                **tick,
                "mill": True,
                "passes": 1,
                "max_passes": max_passes,
                "progress": total_progress,
                "results": results,
            }

        if tick.get("health") == "stall":
            return err(
                "mill stalled: actionable work remains but no progress",
                mode=cfg.mode,
                live=live,
                idle=False,
                health="stall",
                passes=i + 1,
                max_passes=max_passes,
                progress=total_progress,
                results=results,
                last=tick,
            )

        # Live pass made zero progress but not idle (e.g. waiting on CI).
        if int(tick.get("progress") or 0) == 0:
            return ok(
                mode=cfg.mode,
                live=live,
                idle=False,
                health=tick.get("health") or "waiting",
                passes=i + 1,
                max_passes=max_passes,
                progress=total_progress,
                results=results,
                last=tick,
                note="stopped: zero progress this pass (waiting or blocked)",
            )

    # Budget exhausted with work still present.
    last = results[-1] if results else {}
    return err(
        "mill budget exhausted before idle",
        mode=cfg.mode,
        live=live,
        idle=False,
        health="budget_exhausted",
        passes=max_passes,
        max_passes=max_passes,
        progress=total_progress,
        results=results,
        remaining=last.get("remaining"),
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-mill")
    add_config_live(p)
    p.add_argument(
        "--max-passes",
        type=int,
        default=8,
        help="stop after N tick passes even if not idle (default 8)",
    )
    args = p.parse_args(argv)
    return emit_exit(
        compose_mill(
            config_path=args.config,
            live=bool(args.live),
            max_passes=int(args.max_passes),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

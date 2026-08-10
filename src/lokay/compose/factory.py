"""Parent Fala composition for one complete Lokay factory pass.

The parent owns top-level pass ordering and invokes ``factory_tick`` as a
subprocess effector.  The tick selects work and starts the existing child Fala
paths, each in the separate child journal configured by ``graph_run``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from lokay.compose.tick import compose_tick
from lokay.envelope import emit_exit
from lokay.graph_run import run_path
from lokay.proc._common import add_config_live


def compose_factory_pass(
    *,
    config_path: str | None,
    live: bool,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run one parent Fala pass; child workflow paths use another journal."""
    if __import__("os").environ.get("LOKAY_OFFLINE", "").strip() in {"1", "true", "yes"}:
        return compose_tick(config_path=config_path, live=live)
    parent_db = Path(db_path) if db_path else Path.home() / ".lokay" / "fala" / "factory"
    result = run_path(
        path_id="factory_pass",
        repo="__lokay_factory__",
        config_path=config_path,
        live=live,
        db_path=parent_db,
    )
    result.update(kind="factory_pass", engine="fala", planned=not live)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-factory-pass")
    add_config_live(parser)
    parser.add_argument("--db-dir", help="parent Fala journal directory")
    args = parser.parse_args(argv)
    return emit_exit(
        compose_factory_pass(
            config_path=args.config,
            live=bool(args.live),
            db_path=args.db_dir,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

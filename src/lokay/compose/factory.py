"""Parent Fala composition for one complete Lokay factory pass.

The parent path ``factory_pass`` owns pass order (begin → PRs → issues →
receipt). Leftover work-copy cleanup is a sibling child; a failed cleanup
is a classified route and does not gate PRs or issue-to-PR.
Python only fail-closes offline, then invokes ``graph_run.run_path``.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err
from lokay.graph_run import run_path
from lokay.proc._common import add_config_live


def _offline() -> bool:
    return os.environ.get("LOKAY_OFFLINE", "").strip() in {"1", "true", "yes"}


def compose_factory_pass(
    *,
    config_path: str | None,
    live: bool,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run one parent Fala pass; child workflow paths use another journal."""
    if live and _offline():
        # Fail closed: a production --live mill must not skip Fala.
        return err(
            "live mill cannot skip Fala (LOKAY_OFFLINE is set)",
            health="offline",
            live=True,
            offline=True,
            engine="fala",
            kind="factory_pass",
        )
    if _offline():
        return {
            "ok": True,
            "health": "offline",
            "offline": True,
            "live": False,
            "planned": True,
            "kind": "factory_pass",
            "engine": "fala",
        }
    parent_db = (
        Path(db_path) if db_path else Path.home() / ".lokay" / "fala" / "factory"
    )
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

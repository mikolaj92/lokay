"""One job: remove leftover ai:ready when work:ready is absent.

After an empty leftover-ready probe, skip that GitHub list for 300s.
Missing stamp always probes. Skip does not refresh the stamp.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

from lokay.operator_stamps import is_operator_stamp
from lokay.envelope import emit_exit, err
from lokay.proc._common import add_config_live

WORK_READY_LABEL = "work:ready"
HYGIENE_TTL_SECONDS = 300
IDLE_HYGIENE_TTL_SECONDS = 900
HYGIENE_STAMP_NAME = "ready-hygiene.stamp"


def hygiene_stamp_path(cfg: Any) -> Path | None:
    """Stamp lives beside lokay state. Missing path means always probe."""
    path = getattr(cfg, "state_path", None)
    if not path:
        return None
    return Path(path).expanduser().parent / HYGIENE_STAMP_NAME






def hygiene_recently_empty(
    stamp: Path | None, *, now: float | None = None, ttl: int | None = None
) -> bool:
    if stamp is None:
        return False
    # Pytest must not skip leftover-ready GitHub lists using the lokay stamp.
    if os.environ.get("PYTEST_CURRENT_TEST") and is_operator_stamp(stamp, HYGIENE_STAMP_NAME):
        return False
    try:
        age = (now if now is not None else time.time()) - stamp.stat().st_mtime
    except OSError:
        return False
    limit = HYGIENE_TTL_SECONDS if ttl is None else ttl
    return 0 <= age < limit






def run_ready_hygiene(*, config_path: str | None, live: bool) -> dict[str, Any]:
    from lokay.proc.ready_hygiene_subflow import run

    return run(config_path=config_path, live=live)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-ready-hygiene")
    add_config_live(parser)
    args = parser.parse_args(argv)
    try:
        payload = run_ready_hygiene(config_path=args.config, live=bool(args.live))
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(payload)


if __name__ == "__main__":
    raise SystemExit(main())

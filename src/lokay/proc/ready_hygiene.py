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

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import (
    is_github_rate_limit_error,
    list_labeled_issues,
    remove_issue_labels,
)
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner

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


def lokay_hygiene_stamp_path() -> Path:
    """Operator lokay leftover-ready stamp beside last-pass / state.jsonl."""
    return Path.home() / ".lokay" / HYGIENE_STAMP_NAME


def _is_operator_lokay_hygiene_stamp(stamp: Path) -> bool:
    lokay = lokay_hygiene_stamp_path()
    try:
        return stamp.expanduser().resolve() == lokay.resolve()
    except OSError:
        return stamp.expanduser() == lokay


def hygiene_recently_empty(
    stamp: Path | None, *, now: float | None = None, ttl: int | None = None
) -> bool:
    if stamp is None:
        return False
    # Pytest must not skip leftover-ready GitHub lists using the lokay stamp.
    if os.environ.get("PYTEST_CURRENT_TEST") and _is_operator_lokay_hygiene_stamp(stamp):
        return False
    try:
        age = (now if now is not None else time.time()) - stamp.stat().st_mtime
    except OSError:
        return False
    limit = HYGIENE_TTL_SECONDS if ttl is None else ttl
    return 0 <= age < limit


def _touch_hygiene_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


def _clear_hygiene_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.unlink()
    except OSError:
        pass


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

"""CLI: read stdin JSON envelope, write fail digest beside state dir."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from lokay.fail_digest import resolve_state_dir, write_digest


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    config_path = None
    state_dir = None
    i = 0
    while i < len(args):
        if args[i] == "--config" and i + 1 < len(args):
            config_path = args[i + 1]
            i += 2
            continue
        if args[i] == "--state-dir" and i + 1 < len(args):
            state_dir = Path(args[i + 1])
            i += 2
            continue
        i += 1
    raw = sys.stdin.read().strip()
    if not raw:
        return 0
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        envelope = {"ok": False, "error": raw[:800]}
    target = state_dir if state_dir is not None else resolve_state_dir(config_path)
    path = write_digest(target, envelope)
    if path is not None:
        sys.stdout.write(str(path) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

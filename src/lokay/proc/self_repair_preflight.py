"""Atomic: validate the activated recovery in a fresh uv subprocess."""

from __future__ import annotations

import argparse
import json
import os
import subprocess

from lokay.envelope import emit_exit, err, ok


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-self-repair-preflight")
    p.add_argument("--config", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--commit", required=True)
    args = p.parse_args(argv)
    env = {
        **os.environ,
        "LOKAY_SELF_REPAIR_VALIDATION": "1",
        "LOKAY_DISABLE_HEALTH_LEASE_ISSUE": "1",
    }
    checked = subprocess.run(
        [
            "uv", "run", "--project", args.project, "lokay-preflight",
            "--config", args.config, "--no-repair", "--validate-inherited-lease",
        ],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
        timeout=300, check=False, env=env,
    )
    try:
        health = json.loads((checked.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        health = {}
    if checked.returncode != 0 or health.get("ok") is not True:
        return emit_exit(err("activated self-repair failed fresh preflight", commit=args.commit))
    return emit_exit(ok(validated=True, restart_required=True, commit=args.commit, health="healthy"))


if __name__ == "__main__":
    raise SystemExit(main())

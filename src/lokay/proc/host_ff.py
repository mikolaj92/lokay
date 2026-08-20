"""One job: mill host checkout is origin/main (fetch + ff-only) or fail-closed.

Does not overwrite the skip-worktree host catalog (``repos.mikolaj92.yaml`` on mini).
Product files such as ``config.yaml`` follow origin/main. Never ``reset --hard``.
Product ``issue_to_pr`` must not run on stale mill code.

This is host maintenance (not a GitHub product mutation): ``--live`` means
fetch + ff-only. It does not take the mill health lease, so the LaunchAgent
can sync before ``lokay-daemon`` issues one.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.git_host_ff import CANONICAL_REPO, fast_forward_origin_main
from lokay.proc._common import add_config_live, load_cfg, runner


def resolve_checkout(args: argparse.Namespace) -> Path | None:
    if getattr(args, "checkout", None):
        return Path(str(args.checkout)).expanduser().resolve()
    env_root = os.environ.get("LOKAY_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    try:
        cfg = load_cfg(args)
    except Exception:  # noqa: BLE001
        return None
    for repo in cfg.active_repos():
        if repo.name == CANONICAL_REPO and (repo.clone_path / ".git").exists():
            return repo.clone_path.resolve()
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-host-ff")
    add_config_live(parser)
    parser.add_argument(
        "--checkout",
        help="mill host git checkout (default: LOKAY_ROOT or lokay clone)",
    )
    args = parser.parse_args(argv)
    checkout = resolve_checkout(args)
    if checkout is None:
        if not args.live:
            return emit_exit(
                ok(planned=True, updated=False, reason="host_checkout_missing")
            )
        return emit_exit(
            err(
                "mill checkout unavailable",
                reason="host_checkout_missing",
                health="host_behind",
            )
        )
    if not args.live:
        return emit_exit(
            ok(
                planned=True,
                checkout=str(checkout),
                updated=False,
                health="planned",
            )
        )
    try:
        result = fast_forward_origin_main(runner(), checkout)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(
            err(
                str(exc),
                reason="host_behind",
                health="host_behind",
                checkout=str(checkout),
            )
        )
    return emit_exit(
        ok(
            planned=False,
            checkout=str(checkout),
            health="current",
            **result,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

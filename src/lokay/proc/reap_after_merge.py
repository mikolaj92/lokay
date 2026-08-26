"""Parent step (3): after merge, delete leftover worktrees. Leftover overflow is skip."""

from __future__ import annotations


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    from lokay.proc.leftover_closeout_subflow import run as leftover_closeout
    from lokay.proc.reap_stale_worktrees_subflow import run as reap_worktrees

    leftover = leftover_closeout(config_path=config_path, live=live)
    if not leftover.get("ok"):
        from lokay.proc.leftover_catalog import skip

        leftover = skip(
            reason=str(leftover.get("reason") or leftover.get("error") or "leftover_failed")
        )
    reaped = reap_worktrees(
        pass_dir=pass_dir, config_path=config_path, live=live
    )
    return {
        "ok": True,
        "route": "skip" if leftover.get("skipped") else "reaped",
        "pass_dir": pass_dir,
        "leftover": leftover,
        "reap_stale_worktrees": reaped,
    }

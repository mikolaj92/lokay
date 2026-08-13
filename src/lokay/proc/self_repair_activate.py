"""Atomic: activate the exact recovery commit in the canonical checkout."""

from __future__ import annotations

import argparse
import subprocess

from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed

REPO = "mikolaj92/lokay"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-self-repair-activate")
    add_config_live(p)
    p.add_argument("--commit", required=True)
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    repo = next((r for r in cfg.active_repos() if r.name == REPO), None)
    if repo is None:
        return emit_exit(err("canonical Lokay checkout unavailable"))
    if not live:
        return emit_exit(ok(planned=True, activated=False, commit=args.commit))
    try:
        status = subprocess.run(
            ["git", "-C", str(repo.clone_path), "status", "--porcelain"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if status.returncode or status.stdout.strip():
            # Do not undo a push that already landed on origin/main.
            contains = subprocess.run(
                ["git", "-C", str(repo.clone_path), "merge-base", "--is-ancestor", args.commit, "origin/main"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if contains.returncode == 0:
                return emit_exit(
                    ok(
                        planned=False,
                        activated=False,
                        published=True,
                        reason="dirty_tree",
                        path=str(repo.clone_path),
                        commit=args.commit,
                    )
                )
            raise RuntimeError("canonical Lokay checkout is not clean")
        for command in (
            ["git", "-C", str(repo.clone_path), "fetch", "origin", "main"],
            ["git", "-C", str(repo.clone_path), "merge", "--ff-only", args.commit],
        ):
            done = subprocess.run(command, stdin=subprocess.DEVNULL, timeout=300, check=False)
            if done.returncode:
                raise RuntimeError("exact recovery commit activation failed")
        head = subprocess.run(
            ["git", "-C", str(repo.clone_path), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if head.returncode or head.stdout.strip() != args.commit:
            raise RuntimeError("exact recovery commit not activated")
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(ok(planned=False, activated=True, path=str(repo.clone_path), commit=args.commit))


if __name__ == "__main__":
    raise SystemExit(main())

"""Clone missing managed repos with gh (scope stays in catalog; fill local trees)."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, ok
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.source import load_code


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-repos-clone-missing")
    add_config_live(p)
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    r = runner()
    planned: list[dict] = []
    cloned: list[dict] = []
    failed: list[dict] = []

    for repo in cfg.active_repos():
        if repo.clone_path.exists():
            continue
        entry = {"name": repo.name, "clone_path": str(repo.clone_path)}
        if not live:
            planned.append(entry)
            continue
        try:
            contract = load_code(repo, runner=r, config=cfg, live=True)
            contract.repo.clone()
            cloned.append(entry)
        except Exception as exc:  # noqa: BLE001
            failed.append({**entry, "stderr": str(exc)[-500:]})

    payload = ok(
        planned=not live,
        missing_before=len(planned) + len(cloned) + len(failed),
        planned_clones=planned,
        cloned=cloned,
        failed=failed,
    )
    if failed:
        payload["ok"] = False
        payload["error"] = f"{len(failed)} clone(s) failed"
    return emit_exit(payload)


if __name__ == "__main__":
    raise SystemExit(main())

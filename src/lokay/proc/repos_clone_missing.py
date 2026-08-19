"""Clone missing managed repos with gh (scope stays in catalog; fill local trees)."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.runner import gh_spec


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
        if repo.name != "mikolaj92/lokay":
            continue
        if repo.clone_path.exists():
            continue
        entry = {"name": repo.name, "clone_path": str(repo.clone_path)}
        if not live:
            planned.append(entry)
            continue
        repo.clone_path.parent.mkdir(parents=True, exist_ok=True)
        result = r.run(
            gh_spec(
                [
                    "repo",
                    "clone",
                    repo.name,
                    str(repo.clone_path),
                ],
                timeout_seconds=600,
            ),
            live=True,
        )
        if result.returncode == 0:
            cloned.append(entry)
        else:
            failed.append(
                {
                    **entry,
                    "stderr": (result.stderr or "")[-500:],
                }
            )

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

"""One job: strip leftover in-flight cache; restore ai:ready.\n\nWalk only survey_scope (hot + rotated cold). A 29-repo ``gh issue list``\nfor every ledger label eats the 5–10 min implement slot.\n"""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import list_labeled_issues
from lokay.passkit.hot import survey_scope
from lokay.passkit.support import run_proc
from lokay.passkit.working import load_begin_working
from lokay.proc import stage_label as p_stage
from lokay.proc._common import add_config_live, load_cfg, runner
from lokay.stage_ledger import LEDGER_ACTIVE_LABELS


def run_reap_stale_implementing(
    *, pass_dir: str | None, config_path: str | None, live: bool
) -> dict[str, Any]:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    cfg_flag = ["--config", config_path] if config_path else []
    live_flag = ["--live"] if live else []
    reaped: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    scope = None
    if pass_dir:
        begin, _working = load_begin_working(pass_dir)
        scope = survey_scope(begin)
    for repo in cfg.active_repos():
        if scope is not None and repo.name not in scope:
            continue
        for label in sorted(LEDGER_ACTIVE_LABELS):
            issues = list_labeled_issues(
                runner(cfg), cfg, repo, label=label, live=live
            )
            for issue in issues:
                num = int(issue.number)
                key = (repo.name, num)
                if key in seen:
                    continue
                seen.add(key)
                if live:
                    staged = run_proc(
                        p_stage.main,
                        [
                            *cfg_flag,
                            *live_flag,
                            "--repo",
                            repo.name,
                            "--issue",
                            str(num),
                            "--stage",
                            "ready",
                        ],
                    )
                else:
                    staged = {"ok": True, "planned": True, "stage": "ready"}
                reaped.append(
                    {
                        "repo": repo.name,
                        "issue": num,
                        "label": label,
                        **staged,
                    }
                )
    return ok(
        planned=not live,
        reaped=reaped,
        kept=[],
        reaped_count=len(reaped),
        pass_dir=pass_dir or "",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-reap-stale-implementing")
    add_config_live(p)
    p.add_argument("--pass-dir", default="")
    args = p.parse_args(argv)
    try:
        payload = run_reap_stale_implementing(
            pass_dir=str(args.pass_dir or "") or None,
            config_path=args.config,
            live=bool(args.live),
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(payload)


if __name__ == "__main__":
    raise SystemExit(main())

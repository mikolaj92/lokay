"""One job: strip leftover in-flight cache; restore ai:ready.

This mini-mill owns only Lokay's delivery lane. Product repositories may share
its config, but querying every ledger label on them eats the implement slot.
After an empty leftover-cache probe, skip those GitHub lists for 300s.
Missing stamp always probes. Skip does not refresh the stamp.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import is_github_rate_limit_error, list_labeled_issues
from lokay.passkit.hot import survey_scope
from lokay.passkit.support import run_proc
from lokay.passkit.working import load_begin_working
from lokay.proc import stage_label as p_stage
from lokay.proc._common import add_config_live, load_cfg, runner
from lokay.stage_ledger import LEDGER_ACTIVE_LABELS


MINI_MILL_REPO = "mikolaj92/lokay"
STALE_TTL_SECONDS = 300
STALE_STAMP_NAME = "reap-stale-implementing.stamp"


def stale_stamp_path(cfg: Any) -> Path | None:
    """Stamp lives beside mill state. Missing path means always probe."""
    path = getattr(cfg, "state_path", None)
    if not path:
        return None
    return Path(path).expanduser().parent / STALE_STAMP_NAME


def stale_recently_empty(stamp: Path | None, *, now: float | None = None) -> bool:
    if stamp is None:
        return False
    try:
        age = (now if now is not None else time.time()) - stamp.stat().st_mtime
    except OSError:
        return False
    return 0 <= age < STALE_TTL_SECONDS


def _touch_stale_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


def _clear_stale_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.unlink()
    except OSError:
        pass


def run_reap_stale_implementing(
    *, pass_dir: str | None, config_path: str | None, live: bool
) -> dict[str, Any]:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    stamp = stale_stamp_path(cfg)
    if stale_recently_empty(stamp):
        return ok(
            planned=not live,
            reaped=[],
            kept=[],
            reaped_count=0,
            pass_dir=pass_dir or "",
            skipped=True,
            reason="recent_empty",
        )
    cfg_flag = ["--config", config_path] if config_path else []
    live_flag = ["--live"] if live else []
    reaped: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    scope = None
    if pass_dir:
        begin, _working = load_begin_working(pass_dir)
        scope = survey_scope(begin)
    probed = False
    probe_failed = False
    for repo in cfg.active_repos():
        if repo.name != MINI_MILL_REPO:
            continue
        if scope is not None and repo.name not in scope:
            continue
        probed = True
        repo_issues: list[tuple[str, Any]] = []
        for label in sorted(LEDGER_ACTIVE_LABELS):
            try:
                issues = list_labeled_issues(
                    runner(cfg), cfg, repo, label=label, live=live
                )
            except RuntimeError as exc:
                if is_github_rate_limit_error(exc):
                    probe_failed = True
                    repo_issues = []
                    break
                raise
            repo_issues.extend((label, issue) for issue in issues)
        for label, issue in repo_issues:
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
    if probed and not probe_failed:
        if reaped:
            _clear_stale_stamp(stamp)
        else:
            _touch_stale_stamp(stamp)
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

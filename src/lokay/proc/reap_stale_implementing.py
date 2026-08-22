"""One job: strip leftover in-flight cache; restore ai:ready.

This mini-mill owns only Lokay's delivery lane. Product repositories may share
its config, but querying every ledger label on them eats the implement slot.
After an empty leftover-cache probe, skip those GitHub lists for 300s.
Missing stamp always probes. Skip does not refresh the stamp.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import is_github_rate_limit_error, list_labeled_issues
from lokay.passkit.hot import survey_scope
from lokay.passkit.support import run_proc
from lokay.passkit.working import load_begin_working
from lokay.proc import stage_label as p_stage
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.stage_ledger import LEDGER_ACTIVE_LABELS


MINI_MILL_REPO = "mikolaj92/lokay"
STALE_TTL_SECONDS = 300
IDLE_STALE_TTL_SECONDS = 900
STALE_STAMP_NAME = "reap-stale-implementing.stamp"


def stale_stamp_path(cfg: Any) -> Path | None:
    """Stamp lives beside mill state. Missing path means always probe."""
    path = getattr(cfg, "state_path", None)
    if not path:
        return None
    return Path(path).expanduser().parent / STALE_STAMP_NAME


def mill_stale_stamp_path() -> Path:
    """Operator mill leftover-cache stamp beside last-pass / state.jsonl."""
    return Path.home() / ".lokay" / STALE_STAMP_NAME


def _is_operator_mill_stale_stamp(stamp: Path) -> bool:
    mill = mill_stale_stamp_path()
    try:
        return stamp.expanduser().resolve() == mill.resolve()
    except OSError:
        return stamp.expanduser() == mill


def stale_recently_empty(
    stamp: Path | None, *, now: float | None = None, ttl: int | None = None
) -> bool:
    if stamp is None:
        return False
    # Pytest must not skip leftover-cache GitHub lists using the mill stamp.
    if os.environ.get("PYTEST_CURRENT_TEST") and _is_operator_mill_stale_stamp(stamp):
        return False
    try:
        age = (now if now is not None else time.time()) - stamp.stat().st_mtime
    except OSError:
        return False
    limit = STALE_TTL_SECONDS if ttl is None else ttl
    return 0 <= age < limit


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
    # Idle leftover-cache skip outlives leftover-probe.
    # Hosted factory_pass stays at 300s. Leftover-probe host still lists when stamp is missing.
    idle_ttl = (
        IDLE_STALE_TTL_SECONDS
        if os.environ.get("LOKAY_LEFTOVER_PROBE_GH_OK") == "1"
        else None
    )
    if stale_recently_empty(stamp, ttl=idle_ttl):
        # Fresh leftover-cache skip is not applied.
        # Leftover-cache skip reports probe_failed.
        return ok(
            planned=not live,
            applied=False,
            reaped=[],
            kept=[],
            reaped_count=0,
            pass_dir=pass_dir or "",
            skipped=True,
            reason="recent_empty",
            probe_failed=False,
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
    apply = False
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
                    runner(cfg),
                    cfg,
                    repo,
                    label=label,
                    live=live,
                    raise_on_rate_limit=True,
                )
            except RuntimeError as exc:
                if is_github_rate_limit_error(exc):
                    probe_failed = True
                    repo_issues = []
                    break
                raise
            repo_issues.extend((label, issue) for issue in issues)
        # Fresh leftover-cache skip does not require healthy. Hosted leftover-cache parks do.
        apply = mutations_allowed(live_flag=live, cfg=cfg) if repo_issues else False
        for label, issue in repo_issues:
            num = int(issue.number)
            key = (repo.name, num)
            if key in seen:
                continue
            seen.add(key)
            if apply:
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
        if reaped and apply:
            _clear_stale_stamp(stamp)
        elif not reaped:
            _touch_stale_stamp(stamp)
        # Unhealthy leftover-cache parks do not clear the stamp.
        # Unhealthy leftover-cache parks are planned.
    removed = [row for row in reaped if not row.get("planned")]
    # Leftover-cache reaped_count excludes planned parks.
    # Hosted leftover-cache reports applied.
    # Leftover-cache rate limit does not stamp empty.
    return ok(
        planned=not apply if reaped else not live,
        applied=apply,
        probe_failed=probe_failed,
        reaped=reaped,
        kept=[],
        reaped_count=len(removed),
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


def reap_idle_leftover_cache(*, config_path: str | None, live: bool = True) -> None:
    """Idle daemon_cycle skip still runs leftover-cache. OSError cannot stall."""
    if not live:
        return
    try:
        run_reap_stale_implementing(
            pass_dir=None, config_path=config_path, live=True
        )
    except OSError:
        return


if __name__ == "__main__":
    raise SystemExit(main())

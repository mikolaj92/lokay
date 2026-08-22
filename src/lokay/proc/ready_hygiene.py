"""One job: remove leftover ai:ready when work:ready is absent.

After an empty leftover-ready probe, skip that GitHub list for 300s.
Missing stamp always probes. Skip does not refresh the stamp.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import list_labeled_issues, remove_issue_labels
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner

MINI_MILL_REPO = "mikolaj92/lokay"
WORK_READY_LABEL = "work:ready"
HYGIENE_TTL_SECONDS = 300
IDLE_HYGIENE_TTL_SECONDS = 900
HYGIENE_STAMP_NAME = "ready-hygiene.stamp"


def hygiene_stamp_path(cfg: Any) -> Path | None:
    """Stamp lives beside mill state. Missing path means always probe."""
    path = getattr(cfg, "state_path", None)
    if not path:
        return None
    return Path(path).expanduser().parent / HYGIENE_STAMP_NAME


def mill_hygiene_stamp_path() -> Path:
    """Operator mill leftover-ready stamp beside last-pass / state.jsonl."""
    return Path.home() / ".lokay" / HYGIENE_STAMP_NAME


def _is_operator_mill_hygiene_stamp(stamp: Path) -> bool:
    mill = mill_hygiene_stamp_path()
    try:
        return stamp.expanduser().resolve() == mill.resolve()
    except OSError:
        return stamp.expanduser() == mill


def hygiene_recently_empty(
    stamp: Path | None, *, now: float | None = None, ttl: int | None = None
) -> bool:
    if stamp is None:
        return False
    # Pytest must not skip leftover-ready GitHub lists using the mill stamp.
    if os.environ.get("PYTEST_CURRENT_TEST") and _is_operator_mill_hygiene_stamp(stamp):
        return False
    try:
        age = (now if now is not None else time.time()) - stamp.stat().st_mtime
    except OSError:
        return False
    limit = HYGIENE_TTL_SECONDS if ttl is None else ttl
    return 0 <= age < limit


def _touch_hygiene_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


def _clear_hygiene_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.unlink()
    except OSError:
        pass


def run_ready_hygiene(*, config_path: str | None, live: bool) -> dict[str, Any]:
    args = argparse.Namespace(config=config_path, live=live)
    cfg = load_cfg(args)
    stamp = hygiene_stamp_path(cfg)
    # Fresh leftover-ready skip does not require healthy. Hosted leftover-ready parks still do.
    # Idle leftover-ready skip outlives leftover-probe.
    # Hosted factory_pass stays at 300s. Leftover-probe host still lists when stamp is missing.
    idle_ttl = (
        IDLE_HYGIENE_TTL_SECONDS
        if os.environ.get("LOKAY_LEFTOVER_PROBE_GH_OK") == "1"
        else None
    )
    if hygiene_recently_empty(stamp, ttl=idle_ttl):
        # Fresh leftover-ready skip is not applied.
        return ok(
            planned=not live,
            applied=False,
            cleaned=[],
            cleaned_count=0,
            skipped=True,
            reason="recent_empty",
        )
    apply = mutations_allowed(live_flag=live, cfg=cfg)
    cleaned: list[dict[str, Any]] = []
    probed = False
    for repo in cfg.active_repos():
        if repo.name != MINI_MILL_REPO:
            continue
        probed = True
        # Unhealthy leftover-ready still lists GitHub. Hosted leftover-ready parks still do.
        issues = list_labeled_issues(
            runner(cfg), cfg, repo, label=cfg.ready_label, live=live
        )
        for issue in issues:
            if WORK_READY_LABEL in issue.labels:
                continue
            remove_issue_labels(
                runner(cfg), repo.name, issue.number, [cfg.ready_label], live=apply
            )
            cleaned.append({"repo": repo.name, "issue": issue.number})
    if apply and probed:
        if cleaned:
            _clear_hygiene_stamp(stamp)
        else:
            _touch_hygiene_stamp(stamp)
    return ok(planned=not apply, applied=apply, cleaned=cleaned, cleaned_count=len(cleaned))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-ready-hygiene")
    add_config_live(parser)
    args = parser.parse_args(argv)
    try:
        payload = run_ready_hygiene(config_path=args.config, live=bool(args.live))
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(payload)


def hygiene_idle_leftover_ready(*, config_path: str | None, live: bool = True) -> None:
    """Idle daemon_cycle skip still runs leftover-ready. OSError cannot stall."""
    if not live:
        return
    try:
        run_ready_hygiene(config_path=config_path, live=True)
    except OSError:
        return


if __name__ == "__main__":
    raise SystemExit(main())

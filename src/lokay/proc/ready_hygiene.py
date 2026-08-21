"""One job: remove leftover ai:ready when work:ready is absent.

After an empty leftover-ready probe, skip that GitHub list for 300s.
Missing stamp always probes. Skip does not refresh the stamp.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import list_labeled_issues, remove_issue_labels
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner

MINI_MILL_REPO = "mikolaj92/lokay"
WORK_READY_LABEL = "work:ready"
HYGIENE_TTL_SECONDS = 300
HYGIENE_STAMP_NAME = "ready-hygiene.stamp"


def hygiene_stamp_path(cfg: Any) -> Path | None:
    """Stamp lives beside mill state. Missing path means always probe."""
    path = getattr(cfg, "state_path", None)
    if not path:
        return None
    return Path(path).expanduser().parent / HYGIENE_STAMP_NAME


def hygiene_recently_empty(stamp: Path | None, *, now: float | None = None) -> bool:
    if stamp is None:
        return False
    try:
        age = (now if now is not None else time.time()) - stamp.stat().st_mtime
    except OSError:
        return False
    return 0 <= age < HYGIENE_TTL_SECONDS


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
    apply = mutations_allowed(live_flag=live, cfg=cfg)
    stamp = hygiene_stamp_path(cfg)
    if apply and hygiene_recently_empty(stamp):
        return ok(
            planned=not apply,
            applied=apply,
            cleaned=[],
            cleaned_count=0,
            skipped=True,
            reason="recent_empty",
        )
    cleaned: list[dict[str, Any]] = []
    probed = False
    for repo in cfg.active_repos():
        if repo.name != MINI_MILL_REPO:
            continue
        probed = True
        issues = list_labeled_issues(
            runner(cfg), cfg, repo, label=cfg.ready_label, live=apply
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


if __name__ == "__main__":
    raise SystemExit(main())

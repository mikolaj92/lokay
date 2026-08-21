"""Fail-closed TTL for empty factory_pass GitHub surveys.

Idle ticks listed open PRs, inbox, and work:ready every pass (~2s) even when
all three were empty. After a complete empty mill survey, stamp beside mill
state and skip those GitHub lists for 120s. Missing stamp always hosts Fala.
Skip while the stamp is fresh does not refresh it, matching leftover closeout
/ over_cap TTL. A non-empty survey or a survey_error clears the stamp.

After the stamp expires, a live idle mill cheap-probes those three GitHub
lists. An empty probe refreshes the stamp and skips Fala. Probe failure or
any open PR / inbox / ready hosts.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from lokay.gh_rate import SURVEY_LIST_CAP
from lokay.mill_scope import mill_repo
from lokay.stage_ledger import LABEL_WORK_READY, LEDGER_ACTIVE_LABELS
from lokay.triage import PARK_LABELS

_CSI = re.compile(r"\[[0-9;]*[mK]")
_DECIDED_LABELS = (
    frozenset({"ai:ready", "ai:blocked", "ai:needs-feedback", LABEL_WORK_READY})
    | frozenset(PARK_LABELS)
    | LEDGER_ACTIVE_LABELS
)
_BRANCH_PREFIX = "ai/fix/"

SURVEY_TTL_SECONDS = 120
SURVEY_STAMP_NAME = "factory-survey.stamp"


def survey_stamp_path(begin: dict[str, Any] | None) -> Path | None:
    """Stamp lives beside mill state. Missing path means always probe."""
    if not begin:
        return None
    path = begin.get("state_path") or begin.get("stuck_path")
    if not path:
        return None
    parent = Path(str(path)).expanduser().parent
    if not parent.as_posix():
        return None
    return parent / SURVEY_STAMP_NAME


def mill_survey_stamp_path() -> Path:
    """Operator mill stamp beside last-pass / state.jsonl."""
    return Path.home() / ".lokay" / SURVEY_STAMP_NAME


def _is_operator_mill_stamp(stamp: Path) -> bool:
    mill = mill_survey_stamp_path()
    try:
        return stamp.expanduser().resolve() == mill.resolve()
    except OSError:
        return stamp.expanduser() == mill


def survey_recently_empty(stamp: Path | None, *, now: float | None = None) -> bool:
    if stamp is None:
        return False
    # Pytest must not skip GitHub surveys using the mill stamp.
    if os.environ.get("PYTEST_CURRENT_TEST") and _is_operator_mill_stamp(stamp):
        return False
    try:
        age = (now if now is not None else time.time()) - stamp.stat().st_mtime
    except OSError:
        return False
    return 0 <= age < SURVEY_TTL_SECONDS


def touch_survey_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


def clear_survey_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.unlink()
    except OSError:
        pass


def last_pass_is_empty_idle(receipt: dict[str, Any] | None) -> bool:
    if not isinstance(receipt, dict):
        return False
    if receipt.get("health") != "idle" and not receipt.get("idle"):
        return False
    remaining = receipt.get("remaining")
    if not isinstance(remaining, dict):
        return False
    work = (
        int(remaining.get("inbox") or 0)
        + int(remaining.get("ready") or 0)
        + int(remaining.get("open_ai_prs") or 0)
        + int(remaining.get("issue_to_pr_started") or 0)
        + int(remaining.get("survey_errors") or 0)
    )
    if work:
        return False
    by_repo = remaining.get("by_repo") or receipt.get("by_repo") or []
    if isinstance(by_repo, list) and any(
        isinstance(row, dict) and bool(row.get("occupied")) for row in by_repo
    ):
        return False
    return True


def skip_idle_factory_pass(
    *,
    live: bool,
    stamp: Path | None = None,
    receipt: dict[str, Any] | None = None,
    now: float | None = None,
    probe: Callable[..., bool | None] | None = None,
) -> dict[str, Any] | None:
    """Skip hosting factory_pass while a live idle mill has an empty survey.

    Fresh stamp: skip without GitHub and without refreshing the stamp.
    Expired stamp: cheap-probe GitHub. Empty probe refreshes the stamp and
    skips. Probe failure or remaining work hosts. Missing stamp always hosts.
    Pytest must not skip the operator mill.
    """
    if not live:
        return None
    if os.environ.get("PYTEST_CURRENT_TEST") and (
        stamp is None or _is_operator_mill_stamp(stamp)
    ):
        return None
    if stamp is None:
        stamp = mill_survey_stamp_path()
    if receipt is None:
        from lokay.pass_receipt import read_pass_receipt

        receipt = read_pass_receipt()
    if not last_pass_is_empty_idle(receipt):
        return None
    remaining = receipt.get("remaining") if isinstance(receipt, dict) else {}
    skipped = {
        "ok": True,
        "health": "idle",
        "idle": True,
        "live": True,
        "progress": 0,
        "remaining": remaining if isinstance(remaining, dict) else {},
        "skipped": True,
        "reason": "recent_empty_survey",
    }
    if survey_recently_empty(stamp, now=now):
        return skipped
    try:
        stamp.stat()
    except OSError:
        return None
    checker = probe or mill_survey_still_empty
    empty = checker()
    if empty is not True:
        return None
    touch_survey_stamp(stamp)
    skipped["reason"] = "recent_empty_survey_probe"
    return skipped


def _strip_csi(text: str) -> str:
    return _CSI.sub("", text or "")


def _gh_json_list(
    args: list[str],
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> list[Any] | None:
    """One ``gh`` list. None means probe failed (nonzero / unreadable JSON)."""
    env = os.environ.copy()
    env["GH_NO_COLOR"] = "1"
    env["NO_COLOR"] = "1"
    runner = run or subprocess.run
    try:
        result = runner(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        rows = json.loads(_strip_csi(result.stdout or "[]"))
    except ValueError:
        return None
    if not isinstance(rows, list):
        return None
    if len(rows) >= SURVEY_LIST_CAP:
        return None
    return rows


def _label_names(raw: Any) -> set[str]:
    names: set[str] = set()
    if not isinstance(raw, list):
        return names
    for item in raw:
        if isinstance(item, dict):
            name = str(item.get("name") or "")
        else:
            name = str(item or "")
        if name:
            names.add(name)
    return names


def mill_survey_still_empty(
    *,
    repo: str | None = None,
    run: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> bool | None:
    """Cheap GitHub probe of mill PR / inbox / ready lists.

    True: all three empty. False: work remains. None: probe failed.
    """
    name = str(repo or mill_repo() or "").strip()
    if not name:
        return None
    prs = _gh_json_list(
        [
            "pr",
            "list",
            "--repo",
            name,
            "--state",
            "open",
            "--json",
            "headRefName",
            "--limit",
            str(SURVEY_LIST_CAP),
        ],
        run=run,
    )
    if prs is None:
        return None
    if any(
        str(row.get("headRefName") or "").startswith(_BRANCH_PREFIX)
        for row in prs
        if isinstance(row, dict)
    ):
        return False
    ready = _gh_json_list(
        [
            "issue",
            "list",
            "--repo",
            name,
            "--state",
            "open",
            "--label",
            LABEL_WORK_READY,
            "--json",
            "number,state",
            "--limit",
            str(SURVEY_LIST_CAP),
        ],
        run=run,
    )
    if ready is None:
        return None
    if any(
        isinstance(row, dict)
        and str(row.get("state") or "").upper() != "CLOSED"
        and int(row.get("number") or 0) > 0
        for row in ready
    ):
        return False
    inbox = _gh_json_list(
        [
            "issue",
            "list",
            "--repo",
            name,
            "--state",
            "open",
            "--json",
            "labels",
            "--limit",
            str(SURVEY_LIST_CAP),
        ],
        run=run,
    )
    if inbox is None:
        return None
    for row in inbox:
        if not isinstance(row, dict):
            continue
        if not (_label_names(row.get("labels")) & _DECIDED_LABELS):
            return False
    return True

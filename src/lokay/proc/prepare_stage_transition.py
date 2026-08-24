"""Prepare one deterministic issue-stage transition and mutation authorization."""

import argparse

from lokay.gh_issues import WORK_READY_LABEL
from lokay.proc._common import load_cfg, mutations_allowed
from lokay.stage_ledger import INFLIGHT_STAGES, LABEL_READY, plan_stage_transition


def prepare(
    *,
    config_path: str | None,
    live: bool,
    repo: str,
    issue: int,
    stage: str,
    receipt: bool,
    comment: str,
) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path, live=live))
    plan = plan_stage_transition(
        stage, ready_label=str(cfg.ready_label or "ai:ready"), receipt=receipt
    )
    remove = list(plan.remove_labels)
    if stage in INFLIGHT_STAGES:
        protected = {str(cfg.ready_label or LABEL_READY), LABEL_READY, WORK_READY_LABEL}
        remove = [x for x in remove if x not in protected]
    text = comment.strip() or (plan.receipt or "")
    return {
        "ok": True,
        "repo": repo,
        "issue": issue,
        "stage": plan.stage,
        "remove_labels": remove,
        "add_labels": list(plan.add_labels),
        "comment": text,
        "live": mutations_allowed(live_flag=live, cfg=cfg),
    }

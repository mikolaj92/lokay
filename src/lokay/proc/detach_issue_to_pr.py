"""Compatibility facade for detached issue-delivery lifecycle atoms."""

from lokay.proc.issue_delivery_launch import detach_issue_to_pr
from lokay.proc.issue_delivery_occupancy import (
    clear_dead_issue_to_pr_receipts,
    clear_issue_to_pr_receipt,
    has_unreadable_issue_to_pr_receipts,
    live_issue_to_pr_receipts,
)
from lokay.proc.issue_delivery_process import (
    _child_pids,  # noqa: F401 — re-exported for over_budget_coder_facts
    _pid_command,  # noqa: F401 — re-exported for over_budget_coder_facts
    coding_live_for_issue,
    is_coding_command,
    is_live_issue_to_pr_pid,
    pid_is_alive,
    terminate_issue_to_pr_pid,
    terminate_orphan_coders_for_issue,
    wrapper_has_coding_descendant,
)
from lokay.proc.issue_delivery_receipts import (
    issue_to_pr_log_path,
    issue_to_pr_receipt_path,
    write_issue_to_pr_receipt,
)

__all__ = [
    "clear_dead_issue_to_pr_receipts",
    "clear_issue_to_pr_receipt",
    "coding_live_for_issue",
    "detach_issue_to_pr",
    "has_unreadable_issue_to_pr_receipts",
    "is_coding_command",
    "is_live_issue_to_pr_pid",
    "issue_to_pr_log_path",
    "issue_to_pr_receipt_path",
    "live_issue_to_pr_receipts",
    "pid_is_alive",
    "terminate_issue_to_pr_pid",
    "terminate_orphan_coders_for_issue",
    "wrapper_has_coding_descendant",
    "write_issue_to_pr_receipt",
]

"""Prompt contract for one semantic issue-triage agent call."""

from __future__ import annotations
import json
from lokay.models import Issue
from lokay.safety import untrusted_issue_block
from lokay.tool_contracts import render_contract

SCHEMA = """{
  "verdict": "ready" | "close" | "needs_evidence" | "needs_human",
  "reason": "short_snake_case_reason",
  "evidence": ["one-line physical facts"],
  "evidence_kind": "repo_shape" | "named_paths" | "linked_prs" | "covering_prs" | null,
  "summary": "one short paragraph"
}"""


def prompt(issue_data: dict, hard_facts: dict, additional: dict | None = None) -> str:
    issue = Issue.from_dict(issue_data)
    evidence_round = ""
    if additional is not None:
        evidence_round = (
            "This is the only evidence round. Do not return needs_evidence again.\n"
            "Additional physical evidence:\n"
            + json.dumps(additional, ensure_ascii=False, sort_keys=True)[:12000]
        )
    return render_contract(
        "issue_triage",
        schema=SCHEMA,
        hard_facts=json.dumps(hard_facts, ensure_ascii=False, sort_keys=True)[:8000],
        untrusted_issue=untrusted_issue_block(issue.title, issue.body),
        evidence_round=evidence_round,
    )

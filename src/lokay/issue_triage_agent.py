"""Prompt contract for one semantic issue-triage agent call."""

from __future__ import annotations
import json
from lokay.models import Issue
from lokay.safety import untrusted_issue_block

SCHEMA = """{
  "verdict": "ready" | "close" | "needs_evidence" | "needs_human",
  "reason": "short_snake_case_reason",
  "evidence": ["one-line physical facts"],
  "evidence_kind": "repo_shape" | "named_paths" | "linked_prs" | "covering_prs" | null,
  "summary": "one short paragraph"
}"""


def prompt(issue_data: dict, hard_facts: dict, additional: dict | None = None) -> str:
    issue = Issue.from_dict(issue_data)
    text = f"""You are Lokay issue triage. Judge one intentional GitHub issue. Return ONLY one JSON object.

Schema:
{SCHEMA}

Rules:
1. Prefer ready (robić) for intentional operator or configured-assignee work.
2. close (zamknąć) only for clearly obsolete, superseded, wrong-shape, or foreign essence objections.
3. Do not split. Oversized or multi-epic work is needs_human (człowiek).
4. needs_evidence selects exactly one closed evidence_kind when one physical fact prevents a verdict.
5. needs_human (człowiek) is residual and terminal. Do not implement.
6. Do not edit files or mutate GitHub.

Hard physical facts:
{json.dumps(hard_facts,ensure_ascii=False,sort_keys=True)[:8000]}

{untrusted_issue_block(issue.title,issue.body)}"""
    if additional is not None:
        text += "\n\nThis is the only evidence round. Do not return needs_evidence again.\nAdditional physical evidence:\n"
        text += json.dumps(additional, ensure_ascii=False, sort_keys=True)[:12000]
    return text

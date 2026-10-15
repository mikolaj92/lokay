from dataclasses import replace
import re
from typing import assert_never

from lokay.types import (
    Run, Event, Planned, Synthesized, Built, Checked, Merged, Conflict, Failed,
    Retried, FixToBuild, Published, Fixed, RedMain, Updated, Progress, Snapshot, Pick,
)


def step(run: Run, event: Event) -> Run:
    current = dict(run.state)
    fields = dict(event.fields)
    outcome = event.outcome
    match event:
        case Failed():
            reason = outcome["reason"]
            failures = current.get("failures", 0) + 1
            transient = bool(re.search(
                r"timeout|timed out|connection|could not resolve host|network|HTTP 5\d\d|host probe",
                reason, re.IGNORECASE))
            to_plan = not event.plan_branch and not transient and (
                current.get("last_error") == reason or reason.startswith("fix_code"))
            delay = min(3600, 60 * 2 ** min(failures - 1, 6)) if transient else 0
            fields.update(node="plan" if to_plan else current.get("node") or "check",
                          result="failed", reason=reason, last_error=None if to_plan else reason,
                          failures=failures, retry_at=event.ts + delay if delay else 0)
            if to_plan:
                fields.update(plan_phase="write", plan_branches={}, plan_synthesis={},
                              plan_evaluations=0, plan_accepted_sha=None)
        case Planned():
            if (current.get("verdict") or {}).get("result") == "wait":
                fields["verdict"] = None
            fields.update(node="plan", plan_phase="write", plan_branches={}, plan_synthesis={},
                          plan_evaluations=0, plan_accepted_sha=None)
        case Built():
            if outcome.get("result") == "failed":
                fields.update(node="plan", plan_phase="write", plan_branches={}, plan_synthesis={},
                              plan_evaluations=0, plan_accepted_sha=None,
                              result="failed", reason=outcome.get("reason") or "build failed",
                              failures=current.get("failures", 0) + 1, retry_at=0)
            elif outcome.get("result") == "done":
                fields.update(failures=0, reason=None, retry_at=0, build_note=None, previous_head=None,
                              pi_response=outcome.get("pi_response") or "")
        case Retried():
            fields.update(failures=0, retry_at=0, reason=None)
        case FixToBuild():
            fields.update(node="build", result="running", reason=None, failures=0, retry_at=0)
        case Synthesized():
            if outcome.get("next") == "ok":
                fields.update(node="build", plan_phase=None, plan_prompt=None)
        case Published():
            if outcome.get("result") == "pr_open":
                fields.update(node="check", verdict=None)
        case Checked() | Conflict():
            fields["node"] = outcome["result"]
            if outcome["result"] == "plan":
                fields.update(plan_phase="write", plan_branches={}, plan_synthesis={},
                              plan_evaluations=0, plan_accepted_sha=None)
        case Fixed():
            fields.update(node="check", verdict=None)
        case Merged():
            fields["result"] = outcome["result"]
        case RedMain():
            fields.update(node=current.get("node") or ("check" if outcome.get("pr") else "plan"),
                          result="running", reason=None, retry_at=0)
        case Progress():
            counts = outcome["counts"]
            stalled = (run.diff_hash == outcome["diff_hash"]
                       or (current.get("fix_fingerprint") == outcome["fingerprint"]
                           and current.get("fix_hunk_fingerprint") == outcome["hunk_fingerprint"])
                       or (len(counts) == 3 and min(counts[1:]) >= counts[0]))
            return replace(run, no_progress=stalled)
        case Updated():
            pass
        case _:
            assert_never(event)
    if "node" in fields and (fields["node"] != current.get("node") or "node_since" not in current):
        current["node_since"] = event.ts
    if fields.get("last_attempt") and not current.get("issue_since"):
        current["issue_since"] = event.ts
    if fields.get("result") == "merged":
        current["issue_since"] = None
    current.update(fields)
    if fields.get("failures") == 0 and "result" not in fields and current.get("result") == "failed":
        current["result"] = "running"
    return Run(current, current.get("diff_fingerprint"))


def docs_only(state: dict, candidate: dict) -> bool:
    if state.get("docs_only") is True or candidate.get("docs_only") is True:
        return True
    if any(re.search(r"\b(?:docs[-_ ]audit|documentation[-_ ]only|docs[-_ ]only|docs_only)\b", str(value), re.IGNORECASE)
           for row in (state, candidate)
           for key, value in row.items()
           if key in ("issue_title", "issue_body", "title", "body", "branch", "headRefName")):
        return True
    text = "\n".join(str(row.get(key) or "") for row in (state, candidate)
                     for key in ("issue_title", "issue_body", "title", "body"))
    if re.search(r"\b(?:implement|add|fix|update|change|modify|refactor|remove)\b[^\n.!?;]*"
                 r"\b(?:code|API|runtime|functions?|tests?|behaviou?r)\b|"
                 r"(?:\b(?:and|or|also|plus)\b|[&;])\s*"
                 r"(?:(?:code|API|runtime|functions?|tests?|behaviou?r)\b|"
                 r"(?:implement|add|fix|update|change|modify|refactor|remove|improve)\s+"
                 r"(?!(?:the\s+)?(?:README(?:\.md)?|docs?|documentation)\b))",
                 text, re.IGNORECASE):
        return False
    return any(re.search(r"^\s*(?:(?:update|fix|add|improve|revise|write)\s+(?:the\s+)?"
                         r"(?:README(?:\.md)?|docs?|documentation)\b|document\s+\w)",
                         str(row.get(key) or ""), re.IGNORECASE)
               for row in (state, candidate) for key in ("issue_title", "title"))


def pick(snapshot: Snapshot) -> Pick | None:
    for repo in sorted(snapshot.repos, key=lambda row: (row.last_attempt, row.name)):
        if repo.busy:
            continue
        number = repo.status.get("issue")
        if (repo.status.get("status") == "red" and number
                and repo.states.get(number, {}).get("result") != "parked"
                and (snapshot.only_issue is None or snapshot.only_issue == number)):
            return Pick(repo.name, number, "red_main")
        if repo.prs is None:
            return Pick(repo.name, 0, "prs")
        ready = []
        for pr in repo.prs:
            branch = pr["headRefName"]
            if not branch.startswith("lokay/") or not branch[6:].isdecimal():
                continue
            issue = int(branch[6:])
            if snapshot.only_issue is not None and snapshot.only_issue != issue:
                continue
            state = repo.states[issue]
            if (state.get("waiting_on", "ready" if not state else None) == "ready"
                    and state.get("result") != "parked"):
                ready.append((docs_only(state, pr), state.get("last_attempt", 0), pr["number"], issue, pr))
        if ready:
            _, _, _, issue, target = min(ready, key=lambda row: row[:3])
            return Pick(repo.name, issue, "pr", target)
        if repo.issues is None:
            return Pick(repo.name, 0, "issues")
        eligible = []
        for issue in repo.issues:
            number = issue["number"]
            if ((snapshot.only_issue is None or snapshot.only_issue == number)
                    and repo.states[number].get("result") != "parked"
                    and repo.states[number].get("waiting_on", "ready" if not repo.states[number] else None) == "ready"
                    and number not in repo.open_prs):
                state = repo.states[number]
                eligible.append((docs_only(state, issue), state.get("last_attempt", 0), number, issue))
        if eligible:
            _, _, number, target = min(eligible, key=lambda row: row[:3])
            return Pick(repo.name, number, "issue", target)
    return None

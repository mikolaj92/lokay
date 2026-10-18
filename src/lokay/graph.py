from copy import deepcopy
from dataclasses import replace
import re
from typing import assert_never

from lokay.scope import kind as change_kind
from lokay.types import (
    PLAN_RESET, Run, Event, EnteredNode, Planned, Synthesized, Built, Checked, Merged, Closed, Failed,
    Retried, FixToBuild, Published, Fixed, RedMain, Updated, Dispatched, Progress, Snapshot, Pick, pr_number,
)


CHECK_ROUND_LIMIT = 15


def merge_allowed(state: dict, sha: str) -> bool:
    recorded = (state.get("verdict") if "last_check" not in state and "check_inputs" not in state
                else state.get("last_check")) or {}
    return bool(sha) and recorded.get("sha") == sha and recorded.get("result") == "merge"


def step(run: Run, event: Event) -> Run:
    current = dict(run.state)
    if current.get("result") == "closed":
        return run
    fields = dict(event.fields)
    outcome = event.outcome
    match event:
        case EnteredNode():
            fields["node"] = outcome["node"]
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
                fields.update(**deepcopy(PLAN_RESET))
        case Planned():
            fields.update(node="plan", **deepcopy(PLAN_RESET))
        case Built():
            if outcome.get("result") == "failed":
                fields.update(node="plan", **deepcopy(PLAN_RESET),
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
        case Checked():
            rounds = fields.get("check_rounds", current.get("check_rounds", 0))
            if outcome["result"] != "merge" and rounds >= CHECK_ROUND_LIMIT:
                fields.update(node="check", result="needs_help", awaiting="human", retry_at=0,
                              reason=f"check round limit: {rounds} rounds without merge")
            else:
                fields["node"] = outcome["result"]
        case Fixed():
            sha = outcome.get("sha") or fields.get("sha")
            rechecks = current.get("dispute_rechecks", [])
            previous_sha = outcome.get('previous_sha', None if outcome.get('result') == 'pushed' else current.get('sha'))
            if sha and sha == previous_sha:
                if sha in rechecks:
                    fields.update(node="plan", **deepcopy(PLAN_RESET))
                else:
                    fields.update(node="check", verdict=None, dispute_rechecks=rechecks + [sha])
            else:
                fields.update(node="check", verdict=None)
        case Closed():
            fields.update(result="closed", waiting_on=None, awaiting=None, retry_at=0,
                          issue_since=None, failures=0, reason=None, last_error=None)
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
        case Dispatched() | Updated():
            pass
        case _:
            assert_never(event)
    if fields.get("node") == "merge":
        sha = fields.get("sha", current.get("sha")) or ""
        if not merge_allowed({**current, **fields}, sha):
            fields.update(node="check", verdict=None, result="check")
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


def _kind(row: dict, pr: bool = False) -> int:
    if (row.get("title", "").startswith("[docs-audit]")
            or any((label.get("name") if isinstance(label, dict) else label) == "docs"
                   for label in row.get("labels", []))):
        return 1
    if not pr:
        return 0
    files = row.get("files")
    if not files:
        diff = row.get("diff") or ""
        files = [path for pair in re.findall(r"^diff --git a/(.*?) b/(.*?)$", diff, re.MULTILINE)
                 for path in pair]
        files.extend(path.removeprefix("a/").removeprefix("b/")
                     for path in re.findall(r"^(?:---|\+\+\+) ([^\t\n]+)", diff, re.MULTILINE)
                     if path != "/dev/null")
    paths = [file.get("path") or file.get("filename") if isinstance(file, dict) else file
             for file in files]
    return int(change_kind(paths) == "docs")


def pick(snapshot: Snapshot) -> Pick | None:
    from lokay.store import derive_waiting_on

    snapshot = replace(snapshot, repos=tuple(
        replace(repo, states={issue: {**state, "waiting_on": derive_waiting_on(state, snapshot.now)}
                              for issue, state in repo.states.items()})
        for repo in snapshot.repos))
    repos = sorted(snapshot.repos, key=lambda row: (row.last_attempt, row.name))
    for repo in repos:
        if repo.busy:
            continue
        number = repo.status.get("issue")
        if (repo.status.get("status") == "red" and number
                and repo.states.get(number, {}).get("waiting_on") != "children"
                and repo.states.get(number, {}).get("result") not in ("merged", "closed")
                and (snapshot.only_issue is None or snapshot.only_issue == number)):
            return Pick(repo.name, number, "red_main")
    due = []
    for repo in snapshot.repos:
        if repo.busy:
            continue
        for issue, state in repo.states.items():
            if (state.get("result") in ("merged", "closed")
                    or (state.get("result") != "parked"
                        and (state.get("waiting_on") == "human" or state.get("awaiting") == "human"))
                    or state.get("waiting_on") == "children"
                    or (snapshot.only_issue is not None and snapshot.only_issue != issue)):
                continue
            retry_at = state.get("retry_at", 0)
            last_attempt = state.get("last_attempt", 0)
            pending = state.get("result") == "pending" and state.get("node") in ("build", "check")
            if retry_at > snapshot.now:
                continue
            if pending and last_attempt + 300 > snapshot.now and retry_at <= 0:
                continue
            if not (state.get("waiting_on") in ("ci", "retry_at") or retry_at > 0
                    or (pending and last_attempt + 300 <= snapshot.now)):
                continue
            due.append((retry_at, last_attempt, repo.name, issue, state))
    if due:
        _, _, repo, issue, state = min(due, key=lambda row: row[:4])
        if state.get("pr"):
            target = {"number": pr_number(state["pr"]), "headRefName": state.get("branch") or f"lokay/{issue}"}
            if state.get("sha"):
                target["headRefOid"] = state["sha"]
            return Pick(repo, issue, "pr", target)
        return Pick(repo, issue, "issue", {"number": issue})
    for repo in repos:
        if repo.busy:
            continue
        if repo.prs is None:
            return Pick(repo.name, 0, "prs")
        ready = []
        for pr in repo.prs:
            if pr.get("state", "OPEN") != "OPEN":
                continue
            branch = pr["headRefName"]
            if not branch.startswith("lokay/") or not branch[6:].isdecimal():
                continue
            issue = int(branch[6:])
            if snapshot.only_issue is not None and snapshot.only_issue != issue:
                continue
            state = repo.states[issue]
            if state.get("result") in ("closed", "merged"):
                continue
            parked = (state.get("result") == "parked"
                      or any(label["name"] == "lokay-parked" for label in pr.get("labels", [])))
            if (parked or state.get("waiting_on", "ready" if not state else None) == "ready"):
                ready.append((_kind(pr, pr=True), state.get("last_attempt", 0), pr["number"], issue, pr))
        fallback = None
        if ready:
            _, _, _, issue, target = min(ready, key=lambda row: row[:4])
            fallback = Pick(repo.name, issue, "pr", target)
            pr_latest = max((state.get("last_attempt", 0) for state in repo.states.values()
                             if state.get("pr")), default=0)
            issue_latest = max((state.get("last_attempt", 0) for state in repo.states.values()
                                if not state.get("pr")), default=0)
            if pr_latest <= issue_latest:
                return fallback
        if repo.issues is None:
            return Pick(repo.name, 0, "issues")
        for issue in sorted(repo.issues, key=lambda row: (_kind(row), row.get("createdAt") or "", row["number"])):
            number = issue["number"]
            if (issue.get("state", "OPEN") == "OPEN"
                    and (snapshot.only_issue is None or snapshot.only_issue == number)
                    and repo.states[number].get("result") not in ("merged", "closed")
                    and (repo.states[number].get("result") == "parked"
                         or repo.states[number].get("waiting_on", "ready" if not repo.states[number] else None) == "ready")
                    and number not in repo.open_prs):
                return Pick(repo.name, number, "issue", issue)
        if fallback is not None:
            return fallback
    return None

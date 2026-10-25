from __future__ import annotations

from functools import partial

import hashlib
import json
import os
import shutil
import signal
import sys
import time
from collections.abc import Callable
from pathlib import Path

from lokay import graph, store
from dataclasses import replace
from lokay.types import Event, Run, Snapshot, RepoSnapshot, Dispatched, Checked, parse_event, pr_number
from lokay.merge import merge_blocked
from lokay.gates import gate_rows
from lokay.effects import maintenance
from lokay.effects.git import base_branch, merge_base_or_restart, restart_from_base, push, worktree_remove
from lokay.effects.git import git, git_bytes, git_try, head as git_head

from lokay.types import Finding, Note, parse_finding
from lokay.config import load_repos, repo as repo_config, tick_budget
from lokay.effects.gh import gh_json, gh_ok, fit_body, auth_status, host_ops, open_issues, open_pr_for, pr_closed_by_factory
from lokay.effects.retry import retry
from lokay.store import acquire_lock, release_lock, lock_path
from lokay.effects.pi import (OneHarnessRunDone, TickExpired, check_deadline, cleanup_process_groups, kill_process_groups,
                       process_groups, run_process, tick_deadline, tick_harness_started)
from lokay.store import repo_attempt, repo_last_attempt, rounds_append, run_dir, state_read, state_update


dumps = partial(json.dumps, default=store.json_default)
RECOVERY_EVIDENCE = "\n\nMain recovery setup/lock evidence:\n"


def tick(repo: str, issue: int, act: Callable[[Run], Event]) -> Run:
    run = store.load(repo, issue)
    event = act(run)
    run = graph.step(run, event)
    store.save(repo, issue, run, event)
    return run


def act(run: Run) -> Event:
    picked = run.state

    def dispatch() -> dict:
        node = picked.get("node")
        if node not in ("plan", "build", "check", "fix", "merge"):
            return {}
        saved = state_read(picked["repo"], picked["issue"])
        before = saved.get("updated_at")
        if saved.get("result") == "wait":
            if store.derive_waiting_on(saved) != "ready":
                return saved.get("verdict") or {"result": "wait"}
            state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "check"}}, result="check", verdict=None,
                         retry_at=0, awaiting=None)
            node = "check"
        try:
            check_deadline()
            prepared = _prepare(picked) if node in ("plan", "build") else _resume(picked)
            outcome = prepared if isinstance(prepared, dict) else _finish(picked, *prepared)
        except TickExpired as exc:
            repo, issue = picked["repo"], picked["issue"]
            reason = "tick yields after one harness2 run" if isinstance(exc, OneHarnessRunDone) else "tick budget exhausted"
            line = "Tick: one harness2 run done; resume saved node" if isinstance(exc, OneHarnessRunDone) else "Tick: budget exhausted; resume saved node"
            state_update(repo, issue, result="pending", reason=reason)
            rounds_append(repo, issue, line)
            return {"result": "pending", "reason": reason}
        except Escalated as exc:
            return exc.outcome
        except RetryLater as exc:
            return {"result": "failed", "reason": str(exc)}
        except Exception as exc:
            outcome = {"result": "failed", "reason": f"{type(exc).__name__}: {exc}"}
        if outcome.get("next") in ("plan", "build"):
            return outcome
        repo, issue = picked["repo"], picked["issue"]
        if outcome.get("result") in ("pending", "pr_open", "check", "wait", "closed", "main_red", "parked", "empty_patch", "same_patch"):
            return outcome
        if outcome.get("result") == "merged":
            state_update(repo, issue, result="merged", failures=0, retry_at=0, reason=None)
            return outcome
        state = state_read(repo, issue)
        if (state.get("result") == "failed" and state.get("reason") == outcome.get("reason")
                and state.get("updated_at") != before):
            return outcome
        reason = outcome.get("reason") or outcome.get("error") or outcome.get("artifact") or "node failed"
        return needs_help(picked, reason)
    try:
        outcome = dispatch()
        return Dispatched(time.time(), fields=store.load(picked["repo"], picked["issue"]).state, outcome=outcome)
    finally:
        if sys.exception() is None:
            published_cleanup(picked)


def _repo_paths(repo: dict, issue: int) -> tuple[Path, Path]:
    root = Path(os.path.expanduser(repo["clone_path"]))
    return root, root.parent / f"{root.name}-wt-{issue}"


class RetryLater(RuntimeError):
    pass


class Escalated(BaseException):
    def __init__(self, outcome: dict):
        self.outcome = outcome


def probes(env: dict[str, str] | None = None) -> dict[str, str]:
    child = dict(os.environ if env is None else env)
    out: dict[str, str] = {}
    api = child.get("LOKAY2_DECISION_API") or "mini"
    if child.get("LOKAY2_GB10") == "down":
        out["decision_host"] = "fail"
    else:
        base = child.get("LOKAY2_DECISION_BASE_URL") or ("" if api == "chat" else "http://192.168.1.52:8005")
        url = base.rstrip("/") + ("/models" if api == "chat" else "/health")
        args = ["/usr/bin/curl", "-sS", "-m", "5", "-w", "\n%{http_code}"]
        key = child.get("LOKAY2_DECISION_API_KEY")
        if key:
            args.extend(["-H", "@-"])
        args.append(url)
        try:
            fetched = run_process(
                args,
                env=child,
                timeout=8,
                input=f"authorization: Bearer {key}\n" if key else None,
            )
            raw, _, code = (fetched.stdout or "").rpartition("\n")
            ready = (fetched.returncode == 0 and code.strip() == "200"
                     and (api == "chat" or json.loads(raw).get("ready") is True))
            out["decision_host"] = "ok" if ready else "fail"
        except Exception:
            out["decision_host"] = "fail"
    out["provider"] = "ok" if child.get("LOKAY2_PROVIDER") and child.get("LOKAY2_PROVIDER") != child.get("PI_PROVIDER", "") else "fail"
    if child.get("LOKAY2_PROVIDER") and "PI_PROVIDER" not in child:
        out["provider"] = "ok"
    out["model"] = "ok" if child.get("LOKAY2_MODEL") else "fail"
    out["decision"] = "ok" if api == "mini" or child.get("LOKAY2_DECISION_MODEL") else "fail"
    out["pi"] = "ok" if shutil.which("pi", path=child.get("PATH")) else "fail"
    try:
        gh = auth_status(child)
        out["gh"] = "ok" if gh.returncode == 0 else "fail"
    except Exception:
        out["gh"] = "fail"
    return out


def host_ready(report: dict[str, str]) -> bool:
    return all(value == "ok" for value in report.values())


def list_prs(name):
    return tuple(gh_json([
        "pr", "list", "--repo", name, "--state", "open", "--limit", "1000000",
        "--json", "number,headRefName,headRefOid,labels,state",
    ], error="pr list failed", default="[]"))


def closed_prs(name, issue):
    return sorted(gh_json([
        "pr", "list", "--repo", name, "--head", f"lokay/{issue}",
        "--state", "closed", "--limit", "100", "--json", "number,mergedAt,closedAt",
    ], error="closed pr list failed", default="[]"), key=lambda pr: pr.get("closedAt") or "", reverse=True)


def reopen_closed_issues(name, issues, reopened):
    prs = None
    for row in issues:
        issue = row["number"]
        saved = state_read(name, issue)
        if (saved.get("result") != "closed" or (name, issue) in reopened
                or saved.get("recovery_exhausted")):
            continue
        if prs is None:
            prs = list_prs(name)
        has_open_pr = any(pr.get("headRefName") == f"lokay/{issue}"
                          and pr.get("state", "OPEN") == "OPEN" for pr in prs)
        closed = closed_prs(name, issue) if not has_open_pr else ()
        unmerged = next((pr for pr in closed if not pr.get("mergedAt")), None)
        closed_unmerged_pr = bool(unmerged and pr_closed_by_factory(name, unmerged["number"]))
        merged_pr = any(pr.get("mergedAt") for pr in closed)
        if graph.reopen_issue_allowed(saved, True, has_open_pr, closed_unmerged_pr, merged_pr):
            state_update(name, issue, _event={"action": "reopened", "outcome": {"issue": True}})
            reopened.add((name, issue))


def poll_outcome(saved: dict, remote: dict, issue: int) -> tuple[str | None, str | None]:
    pr = (remote.get(f"pr_{int(saved['pr'])}") or {}) if saved.get("pr") else {}
    if pr.get("state") == "MERGED":
        return "merged", (pr.get("mergeCommit") or {}).get("oid")
    issue_state = (remote.get(f"issue_{int(issue)}") or {}).get("state")
    if issue_state == "CLOSED":
        return "closed", None
    if issue_state == "OPEN" and pr.get("state") == "CLOSED":
        return "reopened", None
    return None, None


def pick(env: dict[str, str] | None = None) -> dict:
    free = shutil.disk_usage(Path.home()).free
    token = maintenance.ENV.set(env)
    try:
        maintenance.sweep(aggressive=free < 10000000000)
    finally:
        maintenance.ENV.reset(token)
    if shutil.disk_usage(Path.home()).free < 5000000000:
        return {"result": "idle", "reason": "disk"}
    report = probes(env)
    if not host_ready(report):
        failed = " ".join(f"{name}={value}" for name, value in report.items() if value != "ok")
        return {"result": "idle", "reason": "host_down", "failed": failed}
    child = os.environ if env is None else env
    repos_file = child.get("LOKAY2_REPOS_FILE")
    only_repo = child.get("LOKAY2_REPO")
    only_issue = int(child["LOKAY2_ISSUE"]) if child.get("LOKAY2_ISSUE") else None
    configured = load_repos(Path(repos_file) if repos_file else None)
    repos = [repo for repo in configured if not only_repo or repo["name"] == only_repo]
    blocked = []

    def idle():
        if blocked:
            name, issue, saved = max(blocked, key=lambda row: row[2].get("failures", 0))
            return {"result": "idle", "reason": "idle_backoff", "repo": name, "issue": issue,
                    "issue_since": saved.get("issue_since"), "failures": saved.get("failures", 0),
                    "last_error": saved.get("reason") or saved.get("last_error")}
        return {"result": "idle", "reason": "no_work"}

    from lokay.store import main_status
    from lokay.main_guard import check_main

    statuses = main_status()
    for repo in sorted(configured, key=lambda row: (statuses.get(row["name"], {}).get("checked_at", 0), row["name"])):
        name = repo["name"]
        clone = Path(repo["clone_path"]).expanduser()
        if (repo["merge"] != "on" or not clone.is_dir()
                or statuses.get(name, {}).get("checked_at", 0) > time.time() - 3600):
            continue
        held = None
        attempted = False
        try:
            check_deadline()
            held = acquire_lock(lock_path(name.split("/")[0], name))
            if held["result"] != "held":
                continue
            current = main_status().get(name, {})
            if current.get("checked_at", 0) > time.time() - 3600:
                continue
            attempted = True
            store.save_main_status(name, {**current, "checked_at": time.time()})
            check_main(name, clone, config=repo, force=True)
        except TickExpired:
            raise
        except Exception as exc:
            store.log_event("main_checks", repo=name, outcome={"result": "failed", "reason": str(exc)})
        finally:
            if held and held["result"] == "held":
                try:
                    release_lock(held)
                except Exception as exc:
                    store.log_event("main_checks", repo=name, outcome={"result": "failed", "reason": str(exc)})
        if attempted:
            break
    statuses = main_status()
    snapshots = []
    pr_lists = {}
    issue_lists = {}
    reopened = set()

    def cached_prs(name):
        if name not in pr_lists:
            pr_lists[name] = list_prs(name)
        return pr_lists[name]

    def list_issues(name):
        if name not in issue_lists:
            issue_lists[name] = tuple(open_issues(name))
        return issue_lists[name]

    for repo in repos:
        name = repo["name"]
        states = {}
        for path in run_dir(name, 0).parent.glob("*"):
            if not path.name.isdecimal() or not path.is_dir():
                continue
            issue = int(path.name)
            saved = state_read(name, issue)
            if (saved.get("awaiting") == "children"
                    and not (statuses.get(name, {}).get("issue") == issue
                             and (statuses.get(name, {}).get("status") == "red"
                                  or any(state_read(name, child).get("recovery_sha")
                                         for child in saved.get("children", []))))):
                from lokay.effects.gh import children_done

                held = acquire_lock(lock_path(name.split("/")[0], name))
                if held["result"] == "held":
                    try:
                        saved = state_read(name, issue)
                        if (saved.get("awaiting") == "children"
                                and children_done(name, saved.get("children") or [])):
                            fields = store.escalation_fields(saved)
                            fields.update(difficulty="hard", children=[], split_tasks=None,
                                          split_generation=saved.get("split_generation", 0) + 1,
                                          previous_head=None)
                            state_update(name, issue, _event={"action": "enter_node", "outcome": {"node": fields.pop("node")}}, **fields)
                            saved = state_read(name, issue)
                    finally:
                        release_lock(held)
            if saved:
                states[issue] = saved
        if any(saved.get("split_generation", 0) > 0 for saved in states.values()):
            rows = list_issues(name)
            superseded = graph.superseded(RepoSnapshot(name, states=states, prs=cached_prs(name)), rows)
            if superseded:
                held = acquire_lock(lock_path(name.split("/")[0], name))
                if held["result"] == "held":
                    try:
                        for issue, parent in superseded.items():
                            saved = state_read(name, issue)
                            if saved.get("result") == "merged" or saved.get("pr"):
                                continue
                            current = states[parent]
                            tasks = ", ".join(f"#{child}" for child in current.get("children", [])) or "none"
                            gh_ok(["issue", "close", str(issue), "--repo", name, "--reason", "not planned",
                                   "--comment", fit_body(f"Duplicate: #{parent} was replanned (split {current['split_generation']}); "
                                                         f"its tasks are now {tasks}.")], error="superseded issue close failed")
                            state_update(name, issue, _event={"action": "closed"}, closed_on_github=True)
                            store.log_event("superseded_closed", repo=name, issue=issue, parent=parent)
                            states[issue] = state_read(name, issue)
                            issue_lists[name] = tuple(row for row in issue_lists[name] if int(row["number"]) != issue)
                    finally:
                        release_lock(held)
        busy = False
        active = {issue: saved for issue, saved in states.items()
                  if saved.get("result") not in ("merged", "closed")
                  and (only_issue is None or issue == only_issue)}
        if active:
            owner, repo_name = name.split("/", 1)
            fields = [f"issue_{int(issue)}: issueOrPullRequest(number: {int(issue)}) "
                      "{ ... on Issue { state body } ... on PullRequest { state body } }" for issue in active]
            fields.extend(f"pr_{number}: pullRequest(number: {number}) {{ state mergeCommit {{ oid }} }}"
                          for number in sorted({int(saved["pr"]) for saved in active.values() if saved.get("pr")}))
            query = ("query($owner: String!, $name: String!) { repository(owner:$owner,name:$name) { "
                     + " ".join(fields) + " } }")
            response = gh_json(["api", "graphql", "-f", f"owner={owner}", "-f", f"name={repo_name}",
                                "-f", f"query={query}"], allow_partial_data=True)
            remote = response["data"].get("repository") or {}
            closing = [issue for issue, saved in active.items() if poll_outcome(saved, remote, issue)[0]]
            if closing:
                held = acquire_lock(lock_path(name.split("/")[0], name))
                busy = held["result"] != "held"
                if not busy:
                    try:
                        for issue in closing:
                            saved = state_read(name, issue)
                            if not saved or saved.get("result") in ("merged", "closed"):
                                states[issue] = saved
                                continue
                            outcome, oid = poll_outcome(saved, remote, issue)
                            if outcome == "merged":
                                state_update(name, issue, _event={"action": "merge_complete", "outcome": {
                                    "result": "merged", "merge_sha": oid}}, sha=oid,
                                    failures=0, retry_at=0, reason=None, last_error=None)
                            elif outcome == "closed":
                                state_update(name, issue, _event={"action": "closed"}, closed_on_github=True)
                            elif outcome == "reopened":
                                if pr_closed_by_factory(name, saved["pr"]):
                                    state_update(name, issue, _event={"action": "reopened", "outcome": {"issue": True}})
                                    reopened.add((name, issue))
                                else:
                                    state_update(name, issue, _event={"action": "closed"})
                            states[issue] = state_read(name, issue)
                    finally:
                        release_lock(held)
            for issue in active:
                if "body" in (remote.get(f"issue_{issue}") or {}):
                    states[issue] = {**states[issue], "remote_body": remote[f"issue_{issue}"]["body"]}
        closed = [issue for issue, saved in states.items()
                  if saved.get("result") == "closed" and "cleanup" not in saved]
        root = Path(repo["clone_path"]).expanduser()
        if closed and root.is_dir():
            code, out, _ = git_try(root, "for-each-ref", "--format=%(refname)", "refs/heads/lokay/")
            branches = set(out.splitlines())
            cleanup_issues = [issue for issue in closed
                              if _repo_paths(repo, issue)[1].exists() or f"refs/heads/lokay/{issue}" in branches]
            if code == 0 and cleanup_issues:
                held = acquire_lock(lock_path(name.split("/")[0], name))
                if held["result"] == "held":
                    try:
                        for issue in cleanup_issues:
                            if "cleanup" in state_read(name, issue):
                                continue
                            root, worktree = _repo_paths(repo, issue)
                            try:
                                cleanup = worktree_remove(root, worktree, safe=True, branch=f"lokay/{issue}",
                                                          patch_path=run_dir(name, issue) / "cleanup.patch")
                            except Exception as exc:
                                cleanup = {"result": "failed", "error": str(exc)}
                            state_update(name, issue, cleanup="done" if cleanup.get("result") == "removed" else "failed")
                            store.log_event("closed_cleanup", repo=name, issue=issue, outcome=cleanup)
                    finally:
                        release_lock(held)
        main_sha = None
        if root.is_dir() and any(state.get("empty_main_sha") or state.get("same_main_sha") for state in states.values()):
            code, sha, _ = git_try(root, "rev-parse", f"origin/{base_branch(root)}")
            if code == 0 and sha.strip():
                main_sha = sha.strip()
        snapshots.append(RepoSnapshot(name, repo_last_attempt(name), statuses.get(name, {}),
                                      states=states, busy=busy, main_sha=main_sha))
    snapshot = Snapshot(tuple(snapshots), time.time(), only_issue)
    while True:
        check_deadline()
        snapshot = replace(snapshot, now=time.time())
        selected = graph.pick(snapshot)
        if selected is None:
            return idle()
        name, number = selected.repo, selected.issue
        repo = next(row for row in snapshot.repos if row.name == name)
        if selected.kind == "prs":
            prs = tuple(row for row in cached_prs(name) if row.get("state", "OPEN") == "OPEN")
            states = {}
            for row in prs:
                branch = row["headRefName"]
                if not branch.startswith("lokay/") or not branch[6:].isdecimal():
                    continue
                issue = int(branch[6:])
                if only_issue is not None and issue != only_issue:
                    continue
                saved = state_read(name, issue)
                if saved.get("result") != "merged" and not any(
                        int(item["number"]) == issue for item in list_issues(name)):
                    remote_issue = gh_json(["issue", "view", str(issue), "--repo", name,
                                            "--json", "state,closedAt,url"], error="issue view failed")
                    if remote_issue.get("state") == "CLOSED":
                        store.log_event("orphan_pr_skipped", repo=name, issue=issue, pr=row["number"])
                        prs = tuple(pr for pr in prs if pr["number"] != row["number"])
                        continue
                if saved.get("result") == "closed" and (name, issue) not in reopened:
                    issue_open = any(int(item["number"]) == issue and item.get("state", "OPEN") == "OPEN"
                                     for item in list_issues(name))
                    if graph.reopen_pr_allowed(saved, row, issue_open):
                        state_update(name, issue, _event={"action": "reopened", "outcome": {
                            "sha": row["headRefOid"], "pr": row["number"]}})
                        reopened.add((name, issue))
                        saved = state_read(name, issue)
                if saved.get("result") in ("closed", "merged"):
                    states[issue] = saved
                    continue
                states[issue] = saved
                if saved.get("waiting_on") == "retry_at" or saved.get("retry_at", 0) > time.time():
                    blocked.append((name, issue, saved))
            states = {issue: {**saved, "remote_body": next((row.get("body") for row in list_issues(name)
                      if row["number"] == issue), None)} for issue, saved in states.items()}
            repo = replace(repo, prs=prs, states={**repo.states, **states})
        elif selected.kind == "issues":
            issues = tuple(row for row in list_issues(name)
                           if row.get("state", "OPEN") == "OPEN"
                           and (only_issue is None or int(row["number"]) == only_issue))
            reopen_closed_issues(name, issues, reopened)
            states = {}
            open_prs = set()
            for row in issues:
                issue = row["number"]
                saved = states[issue] = state_read(name, issue)
                if (saved.get("result") in ("merged", "closed")
                        or saved.get("waiting_on") in ("children", "ci")
                        or any(result != "merged" for result in graph.blockers(
                            replace(repo, issues=issues, states={**repo.states, **states}), issue).values())):
                    continue
                if saved.get("waiting_on") == "retry_at" or saved.get("retry_at", 0) > time.time():
                    open_prs.add(issue)
                    continue
                if open_pr_for(name, f"lokay/{issue}") is None:
                    break
                open_prs.add(issue)
            else:
                for row in issues:
                    saved = state_read(name, row["number"])
                    if saved.get("failures", 0):
                        blocked.append((name, row["number"], saved))
            repo = replace(repo, issues=issues[:len(states)], states={**repo.states, **states},
                           open_prs=frozenset(open_prs))
        else:
            held = acquire_lock(lock_path(name.split("/")[0], name))
            if held["result"] != "held":
                if selected.kind == "pr":
                    blocked.extend((name, int(row["headRefName"][6:]),
                                    state_read(name, int(row["headRefName"][6:])))
                                   for row in repo.prs or ()
                                   if row["headRefName"].startswith("lokay/")
                                   and row["headRefName"][6:].isdecimal()
                                   and (only_issue is None or int(row["headRefName"][6:]) == only_issue)
                                   and repo.states[int(row["headRefName"][6:])].get("retry_at", 0) <= snapshot.now)
                repo = replace(repo, busy=True)
            else:
                try:
                    repo_attempt(name, time.time())
                    branch = f"lokay/{number}"
                    if selected.kind in ("red_main", "replan"):
                        pr = open_pr_for(name, branch)
                        saved = state_read(name, number)
                        node = "plan" if saved.get("awaiting") == "children" else saved.get("node") or ("check" if pr else "plan")
                        now = time.time()
                        state_update(name, number,
                                     _event={"action": "red_main", "outcome": {"pr": pr, "status": repo.status}},
                                     branch=branch, pr=pr["number"] if pr else None, last_attempt=now,
                                     **store.pick_ladder_fields(saved, now))
                    else:
                        pr = selected.target if selected.kind == "pr" else None
                        saved = state_read(name, number)
                        node = saved.get("node")
                        resumed = {}
                        if pr:
                            branch = pr["headRefName"]
                            labelled = any(label["name"] == "lokay-parked" for label in pr.get("labels", []))
                            if labelled:
                                gh_ok([
                                    "pr", "edit", str(pr["number"]), "--repo", name,
                                    "--remove-label", "lokay-parked",
                                ], error="park label removal failed", include_stdout=True)
                            if saved.get("result") == "parked":
                                resumed = store.escalation_fields(saved)
                                resumed.pop("node")
                                resumed.pop("result")
                                resumed.pop("reason")
                                node = "plan"
                            node = node if node in ("plan", "build", "check", "fix", "merge") else "check"
                        else:
                            closed = closed_prs(name, number)
                            if (closed and not closed[0].get("mergedAt")
                                    and not pr_closed_by_factory(name, closed[0]["number"])):
                                state_update(name, number, _event={"action": "closed"})
                                release_lock(held)
                                return idle()
                            node = node or "plan"
                            if saved.get("result") == "parked":
                                resumed = store.escalation_fields(saved)
                                resumed.pop("node")
                                resumed.pop("result")
                                resumed.pop("reason")
                                node = "plan"
                        now = time.time()
                        state_update(name, number, _event={"action": "enter_node", "outcome": {"node": node}}, branch=branch, pr=pr["number"] if pr else None,
                                     result="running", reason=None, last_attempt=now,
                                     **{**store.pick_ladder_fields(saved, now), **resumed})
                    store.ledger_append({"kind": "pick", "repo": name, "issue": number,
                                         "attempt": now, "reason": selected.kind or node,
                                         "blocked_by": graph.blockers(repo, number)})
                    return {"result": "picked", "repo": name, "issue": number, "node": node,
                            "pr": pr["number"] if pr else None, "held": held}
                except BaseException:
                    release_lock(held)
                    raise
        snapshot = replace(snapshot, repos=tuple(repo if row.name == name else row for row in snapshot.repos))


def refresh_body(repo: str, issue: int) -> dict:
    from lokay.build import pr_body
    from lokay.effects.gh import pr_set_body

    config = repo_config(repo)
    _, worktree = _repo_paths(config, issue)
    pr = open_pr_for(repo, f"lokay/{issue}")
    if not pr:
        raise RuntimeError(f"open PR missing for {repo} lokay/{issue}")
    saved = state_read(repo, issue)
    body = pr_body(worktree, saved.get("issue_body") or "", issue,
                   saved.get("last_check") or saved.get("verdict"))
    notes = (saved.get("verdict") or {}).get("notes") or []
    lens_notes = [parsed for note in notes
                  if isinstance(parsed := parse_finding(note), Note) and parsed.pytanie]
    for raw in saved.get("check_notes", []):
        item = parse_finding(raw)
        if isinstance(item, Finding):
            lens_notes.append(Note(item.lens, item.lens,
                                   f"{item.plik}:{item.linia_od}-{item.linia_do}: {item.zmiana}"))
    if lens_notes:
        body += "\n\n## Uwagi bez konkretu\n" + "\n".join(
            f"- {note.pytanie}: {note.note}" for note in lens_notes)
    return pr_set_body(repo, pr["number"], body, issue)


def main(argv: list[str] | None = None) -> int:
    import sys

    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] == "refresh-body":
        if len(args) != 3 or not args[2].isdigit() or int(args[2]) < 1:
            raise ValueError("usage: lokay refresh-body <repo> <issue>")
        print(dumps(refresh_body(args[1], int(args[2])), separators=(",", ":")))
        return 0
    if "--check" in args:
        report = probes()
        print(dumps(report, separators=(",", ":")))
        return 0 if host_ready(report) else 1
    from lokay.store import log_event

    def shutdown(signum, frame):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        kill_process_groups(list(process_groups))
        raise SystemExit(128 + signum)

    handlers = {sig: signal.signal(sig, shutdown) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        cleanup_process_groups()
        log_event("start")
        token = tick_deadline.set(time.monotonic() + tick_budget())
        harness_token = tick_harness_started.set(False)
        try:
            _tick()
            return 0
        except TickExpired:
            return 0
        finally:
            tick_harness_started.reset(harness_token)
            tick_deadline.reset(token)
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def _tick() -> dict:
    import sys

    outcome = pick()
    if outcome["result"] == "idle":
        from lokay.observe import current

        current(result="idle", idle_reason=outcome["reason"],
                **{key: value for key, value in outcome.items()
                   if key in ("repo", "issue", "issue_since", "failures", "last_error")})
        store.log_event("idle", reason=outcome["reason"])
        extra = outcome.get("failed") or ""
        print(f"idle {outcome['reason']} {extra}".rstrip(), file=sys.stderr)
        return outcome
    try:
        print(dumps({k: v for k, v in outcome.items() if k != "held"}, separators=(",", ":")))
        result = {}
        escalated = escalate(outcome, (state_read(outcome["repo"], outcome["issue"]).get("verdict") or {}).get("uwagi"))
        if escalated:
            return escalated
        def execute(run: Run) -> Event:
            event = act(Run.from_state({**run.state, **{key: outcome[key] for key in ("repo", "issue", "held")}}))
            result.update(event.outcome)
            return event
        tick(outcome["repo"], outcome["issue"], execute)
        if result.get("result") == "merged":
            from lokay.observe import current

            current(result="merged", node=None, node_since=None, issue_since=None,
                    idle_reason=None, last_merge=time.time())
        if outcome.get("node") in ("plan", "build", "check", "fix", "merge"):
            print(dumps(result, separators=(",", ":")))
        return result
    finally:
        release_lock(outcome["held"])


def _ensure_worktree(picked: dict) -> Path:
    from lokay.effects.git import ensure_worktree

    config = repo_config(picked["repo"])
    root, worktree = _repo_paths(config, picked["issue"])
    outcome = ensure_worktree(root, f"lokay/{picked['issue']}", worktree)
    if outcome.get("result") != "added":
        raise RuntimeError(outcome.get("error") or str(outcome))
    return worktree


def _retry[T](picked: dict, node: str, action: Callable[[], T], expected: str | None = None, *, worktree: bool = True) -> T:
    repo, issue = picked["repo"], picked["issue"]
    state_update(repo, issue, _event={"action": "enter_node", "outcome": {"node": node}})
    try:
        check_deadline()
        if worktree and node in {"plan", "build", "check", "fix", "merge"}:
            _ensure_worktree(picked)
        outcome = action()
        if expected is None or (isinstance(outcome, dict) and outcome.get("result") == expected):
            state_update(repo, issue, _event={"action": "retry_succeeded",
                                             "outcome": {"result": outcome.get("result")} if isinstance(outcome, dict) else {}})
            return outcome
        reason = (outcome.get("reason") or outcome.get("error") or str(outcome)
                  if isinstance(outcome, dict) else str(outcome))
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
    outcome = needs_help(picked, reason)
    if outcome.get("next") == "plan" and outcome.get("result") == "pending":
        raise Escalated(outcome)
    raise RetryLater(reason)


def replan_prompt(picked: dict, reason: str, findings: list, head: str | None = None) -> str:
    from lokay.plan import prompt_for

    repo, issue = picked["repo"], picked["issue"]
    saved = state_read(repo, issue)
    if head is None:
        configured = next((row for row in load_repos() if row["name"] == repo), None)
        if configured:
            _, worktree = _repo_paths(configured, issue)
            if worktree.exists():
                from lokay.effects.git import git_try

                code, out, err = git_try(worktree, "rev-parse", "HEAD")
                if code != 0:
                    raise RuntimeError(err or "HEAD lookup failed")
                head = out.strip()
    history = saved.get("plan_history", []) + [{"reason": reason, "uwagi": findings}]
    state_update(repo, issue, plan_history=history,
                 **({"previous_head": head} if head else {}))
    directory = run_dir(repo, issue)
    rounds = directory / "rounds.md"
    prompt = prompt_for(saved.get("issue_title") or "", saved.get("issue_body")) + (
        "\n\nUwagi:\n" + dumps(history[-5:], ensure_ascii=False)[-20000:]
        + "\n\nLast state:\n" + dumps({key: value for key, value in saved.items()
                                     if key not in ("plan_prompt", "plan_history", "local_ci",
                                                    "last_check", "check_inputs")}, ensure_ascii=False)[:20000]
        + "\n\nFix history:\n" + dumps(saved.get("fix_history", []), ensure_ascii=False)[-20000:]
        + "\n\nRounds:\n" + ("\n".join(rounds.read_text().splitlines()[-20:]) if rounds.is_file() else "")
        + "\n\n" + reason + "\n"
    )
    ci = saved.get("local_ci") or {}
    ci_failures = [row for row in (saved.get("verdict") or {}).get("uwagi", [])
                   if row.get("warstwa") == "GitHub CI"]
    if ci.get("result") == "red" and (not ci.get("sha") or ci["sha"] == head):
        ci_failures = [*(ci.get("failed") or [{"log": ci.get("log") or ""}]), *ci_failures]
    if ci_failures:
        tail_size = 4000 // len(ci_failures)
        prompt += "\n\nCI failures:\n" + "\n".join(
            (str(row.get("check") or row.get("warstwa") or "CI") + "\n" + (row.get("log") or ""))[-tail_size:]
            if tail_size else "" for row in ci_failures
        )
    rounds_append(repo, issue, "Re-Plan prompt:\n" + prompt)
    return prompt


def _split_issue(picked: dict, root: Path) -> dict:
    from lokay import plan
    from lokay.effects.git import plan_checkout
    from lokay.effects.gh import create_child_issue

    saved = state_read(picked["repo"], picked["issue"])
    tasks = saved.get("split_tasks")
    if tasks is None:
        outcome = _retry(picked, "plan", lambda: plan.split_tasks(
            saved.get("plan_prompt") or plan.prompt_for(saved["issue_title"], saved["issue_body"]),
            run_dir(picked["repo"], picked["issue"]) / "split.json", cwd=plan_checkout(root)), "done", worktree=False)
        tasks = plan.validate_tasks(outcome["tasks"])
        state_update(picked["repo"], picked["issue"], split_tasks=tasks, children=[])
    tasks = plan.validate_tasks(tasks)
    children = list(state_read(picked["repo"], picked["issue"]).get("children") or [])
    for index, task in enumerate(tasks):
        if index < len(children):
            continue
        if task.get("after"):
            task = {**task, "blocked_by": [children[item] for item in task["after"]]}
        number = create_child_issue(picked["repo"], picked["issue"], index, task,
                                    saved.get("split_generation", 0))
        state_update(picked["repo"], number, blocked_by=task.get("blocked_by", []))
        children.append(number)
        state_update(picked["repo"], picked["issue"], children=children)
    state_update(picked["repo"], picked["issue"], awaiting="children", _event={"action": "enter_node", "outcome": {"node": "plan"}},
                 result="pending", retry_at=0, failures=0, reason=None, split_pending=False)
    return {"result": "pending", "children": children}


def _prepare(picked: dict) -> tuple | dict:
    from lokay.build import build_publish, tidy_and_commit
    from lokay import plan
    from lokay.h2 import run_issue
    from lokay.effects.git import apply_patch, git_try

    saved = state_read(picked["repo"], picked["issue"])
    loaded = gh_json(["issue", "view", str(picked["issue"]), "--repo", picked["repo"], "--json", "title,body"],
                     error="issue view failed")
    if not isinstance(loaded.get("title"), str) or not loaded["title"].strip():
        raise RuntimeError("issue title is missing or invalid")
    body = loaded.get("body")
    if body is not None and not isinstance(body, str):
        raise RuntimeError("issue body is invalid")
    if "issue_title" not in saved or "issue_body" not in saved:
        state_update(picked["repo"], picked["issue"], issue_title=loaded["title"], issue_body=body)
        saved = state_read(picked["repo"], picked["issue"])
    elif (loaded["title"] != saved["issue_title"]
          or (saved["issue_body"] != body
              and not (saved["issue_body"] or "").startswith((body or "") + RECOVERY_EVIDENCE))):
        state_update(picked["repo"], picked["issue"], issue_title=loaded["title"], issue_body=body, plan_prompt=None)
        rounds_append(picked["repo"], picked["issue"],
                      "Plan: issue changed on GitHub; refreshed issue text and reset plan prompt")
        saved = state_read(picked["repo"], picked["issue"])
    title, body = saved["issue_title"], saved["issue_body"]
    if host_ops(body):
        from lokay.effects.gh import fit_body

        reason = "not a coding issue (lokay-host-ops)"
        gh_ok(["issue", "comment", str(picked["issue"]), "--repo", picked["repo"],
               "--body", fit_body("lokay skips this issue: its body carries the lokay-host-ops marker, so it is host/ops work, not a code change.")],
              strip=False, error="issue comment failed")
        state_update(picked["repo"], picked["issue"],
                     _event={"action": "closed", "outcome": {"reason": reason}}, host_ops=True)
        return {"result": "closed", "reason": reason}
    if saved.get("difficulty") not in plan.DIFFICULTIES:
        from lokay.effects.decide import decide

        answer = _retry(picked, "plan", lambda: decide(plan.difficulty_questions(title, body)))["difficulty"]
        if answer["choice"] not in plan.DIFFICULTIES:
            raise RuntimeError("invalid difficulty choice")
        if saved.get("pr") is not None and answer["choice"] == "too_big":
            answer = {**answer, "choice": "hard"}
        state_update(picked["repo"], picked["issue"], difficulty=answer["choice"], difficulty_decision=answer)
        saved = state_read(picked["repo"], picked["issue"])
    repo = repo_config(picked["repo"])
    root, worktree = _repo_paths(repo, picked["issue"])
    if saved.get("pr") is None:
        if saved["difficulty"] == "too_big" or saved.get("split_pending"):
            return _split_issue(picked, root)
    elif saved.get("split_pending"):
        state_update(picked["repo"], picked["issue"], split_pending=False)

    _ensure_worktree(picked)
    name, issue = picked["repo"], picked["issue"]
    branch = f"lokay/{issue}"
    base = base_branch(worktree)
    context = hashlib.sha256(dumps([title, body, saved["difficulty"], saved.get("plan_history", [])]).encode()).hexdigest()
    if saved.get("h2_context") != context:
        state_update(name, issue, h2_context=context, h2_start=None, h2_patch=None,
                     h2_summary=None, h2_all_ran=False, h2_committed=None, h2_published=False)
        saved = state_read(name, issue)
    state_update(name, issue, _event={"action": "enter_node", "outcome": {"node": "build"}}, branch=branch)
    check_deadline()
    if not saved.get("h2_patch"):
        git(worktree, "fetch", "origin", base, timeout=300)
        if not saved.get("h2_start"):
            if git(worktree, "status", "--porcelain", "--untracked-files=no"):
                out = git_bytes(worktree, "diff", "--binary", "HEAD", timeout=300)
                artifact = run_dir(name, issue) / f"build-leftover-{git_head(worktree)[:12]}-{time.time_ns()}.patch"
                store.write_artifact(artifact, out)
                rounds_append(name, issue, f"Build: saved leftover changes to {artifact.name}")
                git(worktree, "reset", "--hard", "HEAD", timeout=300)
            if git_try(worktree, "merge-base", "--is-ancestor", "HEAD", f"origin/{base}")[0]:
                restart_from_base(worktree, base)
                rounds_append(name, issue, f"Build: restart from origin/{base} on the existing branch")
            else:
                conflicts = merge_base_or_restart(worktree, base)
                if conflicts:
                    rounds_append(name, issue, f"Build: base merge conflicts in {', '.join(conflicts)}; restarted from origin/{base}")
            state_update(name, issue, h2_start=git_head(worktree))
        built = run_issue(name, issue, root, start=state_read(name, issue)["h2_start"], title=title,
                          body=body)
        if built.get("result") != "done":
            return needs_help(picked, built.get("reason") or "harness2 failed")
        state_update(name, issue, h2_patch=str(built["patch"]), h2_summary=built.get("summary") or "",
                     h2_all_ran=built.get("all_ran") is True)
        saved = state_read(name, issue)
    patch = Path(saved["h2_patch"])
    if not patch.read_bytes().strip():
        from lokay.main_guard import check_main
        from lokay.effects.gh import fit_body

        if not saved.get("h2_all_ran") or not (saved.get("h2_summary") or "").strip():
            return needs_help(picked, "harness2: empty patch without complete execution and summary evidence")
        previous = store.main_status().get(name, {})
        main = check_main(name, root, base=base, config=repo, force=True,
                          merge_sha=(previous.get("culprit") or {}).get("sha"),
                          pr=(previous.get("culprit") or {}).get("pr"))
        baseline = main["baseline"]
        if main["status"] != "green":
            guard = main.get("issue")
            recovery = state_read(name, guard) if guard else {}
            unhealthy = (main["status"] == "red" or
                         (main["status"] == "unknown" and time.time() - main.get("since", time.time()) >= 3600))
            if unhealthy and guard and (issue == guard or issue in recovery.get("children", [])):
                if saved.get("recovery_sha") == baseline["sha"]:
                    if issue != guard:
                        gh_ok(["issue", "close", str(issue), "--repo", name, "--comment",
                               fit_body("Recovery exhausted after two empty patches.\n" + dumps(baseline))],
                              error="recovery issue close failed", strip=False)
                    state_update(name, issue, _event={"action": "closed"}, closed_on_github=issue != guard,
                                 recovery_exhausted=True)
                    if all(state_read(name, child).get("result") in ("closed", "merged")
                           for child in recovery.get("children", [])):
                        state_update(name, guard, _event={"action": "closed"}, closed_on_github=False,
                                     recovery_exhausted=True)
                        store.save_main_status(name, {**main, "exhausted_sha": baseline["sha"]})
                    return {"result": "closed", "reason": "main recovery exhausted; hourly guard remains active"}
                culprit = main.get("culprit") or {}
                diagnosis = {}
                if (culprit.get("sha") and culprit.get("pr")
                        and git_try(root, "merge-base", "--is-ancestor", culprit["sha"], baseline["sha"])[0] == 0):
                    for key, revision in (("culprit", culprit["sha"]), ("parent", culprit["sha"] + "^1")):
                        diagnosis[key] = check_main(name, root, base=base, config=repo,
                                                    force=True, revision=revision)
                failing = diagnosis.get("culprit", {}).get("baseline", {})
                if (main["status"] == "red" and baseline["lockfile"]["status"] == "pass"
                        and baseline["ci"].get("tested") is True
                        and not any(row.get("warstwa") == "setup" for row in baseline["ci"].get("failed", []))
                        and diagnosis.get("parent", {}).get("status") == "green"
                        and diagnosis.get("culprit", {}).get("status") == "red"
                        and failing.get("lockfile", {}).get("status") == "pass"
                        and failing.get("ci", {}).get("tested") is True
                        and not any(row.get("warstwa") == "setup" for row in failing["ci"].get("failed", []))):
                    parents = git(worktree, "rev-list", "--parents", "-n", "1", culprit["sha"]).split()
                    git(worktree, "revert", "--no-commit", *(["-m", "1"] if len(parents) > 2 else []), culprit["sha"])
                    store.write_artifact(patch, git_bytes(worktree, "diff", "--binary", "HEAD"))
                    tidy_and_commit(worktree, f"Revert culprit PR #{culprit['pr']}")
                    state_update(name, issue, h2_summary=f"Revert culprit PR #{culprit['pr']}",
                                 h2_committed=git_head(worktree))
                    saved = state_read(name, issue)
                else:
                    evidence = dumps({"baseline": baseline, "diagnosis": diagnosis}, ensure_ascii=False)
                    state_update(name, issue, _event={"action": "enter_node", "outcome": {"node": "build"}},
                                 result="pending", recovery_sha=baseline["sha"], h2_patch=None,
                                 h2_start=None, h2_context=None, h2_committed=None,
                                 issue_body=(body or "") + RECOVERY_EVIDENCE + evidence)
                    return {"result": "pending", "next": "build"}
            else:
                return store.empty_patch(name, issue, baseline["sha"])
        if main["status"] == "green":
            return close_empty_patch(name, issue, saved, baseline)
    if not saved.get("h2_committed"):
        leftovers = set(filter(None, git(worktree, "ls-files", "--others", "--exclude-standard", "-z").split("\0")))
        if leftovers:
            rounds_append(name, issue, "Build: leaving untracked leftovers untouched: "
                          + ", ".join(sorted({path.split("/")[0] for path in leftovers})))
        if git_head(worktree) == saved["h2_start"]:
            apply_patch(worktree, patch)
        paths = set(filter(None, git(worktree, "diff", "--cached", "--no-renames", "--name-only", "-z").split("\0")))
        tidy_and_commit(worktree, "lokay build", paths=paths)
        state_update(name, issue, h2_committed=git_head(worktree))
    if not git(worktree, "rev-list", f"origin/{base}..HEAD"):
        return store.empty_patch(name, issue, git(worktree, "rev-parse", f"origin/{base}"))
    state_update(name, issue, _event={"action": "build_complete", "outcome": {"result": "done"}})
    def publish():
        pr = open_pr_for(picked["repo"], branch)
        expected = pr.get("headRefOid") if pr else None
        outcome = build_publish(
            worktree, branch, expected, picked["repo"], int(picked["issue"]),
            title, body or "",
        )
        if outcome.get("result") == "pr_open" and not outcome.get("sha"):
            return {"result": "failed", "reason": "missing published SHA"}
        return outcome
    published = _retry(picked, "build", publish, "pr_open")
    state_update(
        picked["repo"], picked["issue"], pr=published.get("pr"),
        sha=published.get("sha"), result=published["result"], h2_published=True,
    )
    state_update(picked["repo"], picked["issue"], _event={"action": "published", "outcome": published})
    return worktree, branch, published["sha"], repo.get("test") or [], 1


def close_empty_patch(name: str, issue: int, saved: dict, baseline: dict) -> dict:
    from lokay.effects.gh import fit_body

    if saved.get("pr"):
        return store.empty_patch(name, issue, baseline["sha"])
    evidence = (f"{saved['h2_summary']}\n\nMain zielony. Tested SHA: `{baseline['sha']}`\n"
                f"argv: `{dumps(baseline['argv'])}`\n"
                f"Executed tests: {baseline['ci'].get('executed', 0)}\n"
                f"Lock checks: {baseline['lockfile']['status']}")
    gh_ok(["issue", "close", str(issue), "--repo", name, "--comment", fit_body(evidence)],
          error="issue close failed", strip=False)
    state_update(name, issue, _event={"action": "closed"}, closed_on_github=True)
    return {"result": "closed", "reason": "harness2: empty patch, all runs complete, main green"}


def needs_help(picked: dict, reason: str, sha: str | None = None, *, plan_branch: bool = False) -> dict:
    if escalated := escalate(picked, reason=reason):
        return escalated
    repo, issue = picked["repo"], picked["issue"]
    saved = state_read(repo, issue)
    event = {"ts": time.time(), "fields": {}, "action": "needs_help",
             "outcome": {"reason": reason}, "plan_branch": plan_branch}
    derived = graph.step(Run.from_state(saved), parse_event(event)).state
    fields = {}
    to_plan = derived.get("last_error") is None
    if to_plan:
        rounds_append(repo, issue, f"{saved.get('node', picked.get('node', 'check'))} → Plan: {reason}")
        fields["plan_prompt"] = replan_prompt(picked, f"Repeated failure: {reason}",
                                             (saved.get("verdict") or {}).get("uwagi", []),
                                             sha or saved.get("sha") or "")
    state_update(repo, issue, **fields, _event=event,
                 pr=saved.get("pr", picked.get("pr")),
                 sha=sha if sha is not None else saved.get("sha"))
    if not to_plan:
        rounds_append(repo, issue, f"{reason} → retry later" if derived["retry_at"] else f"{reason} → retry")
    return {"result": "failed", "reason": reason}


def escalate(picked: dict, uwagi: list | None = None, *, force: bool = False,
             reason: str | None = None) -> dict | None:
    repo, issue = picked["repo"], picked["issue"]
    saved = state_read(repo, issue)
    uwagi = uwagi or (saved.get("verdict") or {}).get("uwagi", [])
    if gate_rows(uwagi):
        return None
    if saved.get("result") == "merged" or saved.get("awaiting") == "children":
        return None
    now = time.time()
    if not any(saved.get(key) for key in ("diff_changed_at", "issue_since", "ladder_since")):
        state_update(repo, issue, ladder_since=now)
    since = store.ladder_start(saved, now)
    hours = float(os.environ.get("LOKAY2_LADDER_HOURS", "6"))
    if not 0 < hours < float("inf"):
        raise ValueError("LOKAY2_LADDER_HOURS must be positive")
    timed_out = now - since >= hours * 3600
    if not force and not timed_out:
        if saved.get("result") == "wait":
            return None
        if (saved.get("wait_escape") in ("retry", "plan")
                and saved.get("node") != "fix" and saved.get("result") != "fix"):
            return None
        if saved.get("no_progress", 0) < 6 and len(saved.get("fix_history", [])) < 6:
            return None
    prompt = replan_prompt(picked, reason or "No progress; increase difficulty.",
                           uwagi, saved.get("sha") or "")
    fields = store.escalation_fields(saved)
    state_update(repo, issue, _event={"action": "enter_node", "outcome": {"node": fields.pop("node")}},
                 **{**fields, "plan_prompt": prompt})
    rounds_append(repo, issue, f"Difficulty → {fields['difficulty']}")
    return {"result": "pending", "next": "plan"}


def fix_step(picked: dict, node: str, action, sha: str) -> dict:
    try:
        check_deadline()
        _ensure_worktree(picked)
        outcome = action()
    except Exception as exc:
        return needs_help(picked, f"{node}: {type(exc).__name__}: {exc}", sha)
    expected = "done" if node == "harness2" else "pushed"
    if outcome.get("result") != expected and not (
        node == "fix_publish" and outcome.get("result") == "remote_moved" and outcome.get("sha")
    ):
        return needs_help(picked, f"{node}: {outcome}", sha)
    return outcome


def published_cleanup(picked: dict) -> None:
    from lokay.effects.git import git_try

    try:
        root, worktree = _repo_paths(repo_config(picked["repo"]), picked["issue"])
        if not worktree.exists():
            return
        branch = f"lokay/{picked['issue']}"
        code, out, err = git_try(worktree, "merge-base", "--is-ancestor", "HEAD", f"refs/remotes/origin/{branch}")
        if code != 0:
            cleanup = {"result": "kept", "path": str(worktree), "reason": "HEAD not confirmed on origin branch"}
        else:
            cleanup = worktree_remove(root, worktree, safe=True, branch=branch)
    except Exception as exc:
        cleanup = {"result": "failed", "error": str(exc)}
    store.log_event("published_cleanup", repo=picked["repo"], issue=picked["issue"], outcome=cleanup)


def pushed_pr(repo: str, branch: str, sha: str) -> dict | None:
    def lookup():
        check_deadline()
        pr = open_pr_for(repo, branch)
        return pr if pr and pr.get("headRefOid") == sha else None

    return retry(lookup, 6, lambda result: "sha mismatch" if result is None else None,
                 delay=lambda attempt: 5)


def _resume(picked: dict) -> tuple | dict:
    from lokay.effects.git import git_try

    repo = repo_config(picked["repo"])
    root, worktree = _repo_paths(repo, picked["issue"])
    branch = f"lokay/{picked['issue']}"
    try:
        pr = open_pr_for(picked["repo"], branch)
    except Exception as exc:
        return needs_help(picked, f"resume PR: {type(exc).__name__}: {exc}")
    if not pr or not pr.get("headRefOid"):
        state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "build"}}, result="running",
                     pr=None, sha=None, verdict=None, local_ci=None, fix_fingerprint=None,
                     reason=None, last_error=None, failures=0, retry_at=0, awaiting=None,
                     build_from_main=True)
        rounds_append(picked["repo"], picked["issue"], "Resume without PR or SHA → Build")
        return _prepare({**picked, "node": "build", "pr": None})
    sha = pr["headRefOid"]
    state_update(picked["repo"], picked["issue"], pr=pr["number"])
    if pr.get("headRefName", branch) != branch or (picked.get("pr") and pr_number(picked["pr"]) != pr["number"]):
        return needs_help(picked, "PR branch or number mismatch", sha)
    try:
        _ensure_worktree(picked)
    except Exception as exc:
        return needs_help(picked, f"resume worktree: {exc}", sha)
    code, files, err = git_try(worktree, "diff", "--name-only", "--diff-filter=U", "-z")
    if code:
        return needs_help(picked, f"resume index: {err.strip() or files.strip()}", sha)
    merge_code, out, err = git_try(worktree, "rev-parse", "--verify", "--quiet", "MERGE_HEAD")
    if merge_code not in (0, 1):
        return needs_help(picked, f"resume merge: {err.strip() or out.strip()}", sha)
    if files or merge_code == 0:
        saved = state_read(picked["repo"], picked["issue"])
        verdict = saved.get("verdict") or {}
        if not any(parse_finding(row).lens == "conflict" for row in verdict.get("uwagi", [])):
            verdict = {"result": "fix", "sha": sha, "uwagi": [
                {"pytanie": "conflict", "plik": name, "log": "Resolve the interrupted merge; preserve local changes."}
                for name in filter(None, files.split("\0"))
            ] or [{"pytanie": "conflict", "plik": "", "log": "Complete the pending merge (MERGE_HEAD exists)."}]}
        state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "fix"}}, result="fix", sha=sha, verdict=verdict)
        return worktree, branch, sha, repo.get("test") or [], 1
    from lokay.build import tidy_and_commit

    tidy_and_commit(worktree, "lokay resume")
    code, out, err = git_try(worktree, "fetch", "origin", branch)
    if code != 0:
        return needs_help(picked, f"resume fetch: {err.strip() or out.strip()}", sha)
    code, out, err = git_try(worktree, "rev-parse", "HEAD")
    if code != 0:
        return needs_help(picked, f"resume HEAD: {err.strip() or out.strip()}", sha)
    local = out.strip()
    if local != sha:
        ahead, out, err = git_try(worktree, "merge-base", "--is-ancestor", sha, local)
        if ahead not in (0, 1):
            return needs_help(picked, f"resume ancestry: {err.strip() or out.strip()}", sha)
        behind = 1
        if ahead != 0:
            behind, out, err = git_try(worktree, "merge-base", "--is-ancestor", local, sha)
            if behind not in (0, 1):
                return needs_help(picked, f"resume ancestry: {err.strip() or out.strip()}", sha)
            code, out, err = git_try(worktree, "merge", "--ff-only" if behind == 0 else "--no-edit", f"origin/{branch}")
            if code != 0:
                reason = "sha diverged: conflict" if behind != 0 else f"resume ff: {err.strip() or out.strip()}"
                return needs_help(picked, reason, sha)
        if behind != 0:
            published = fix_step(picked, "fix_publish", lambda: push(worktree, branch, sha), sha)
            if published.get("result") != "pushed":
                if published.get("result") == "failed":
                    return published
                return needs_help(picked, f"fix_publish: {published}", sha)
            code, out, err = git_try(worktree, "rev-parse", "HEAD")
            pr = pushed_pr(picked["repo"], branch, out.strip()) if code == 0 else None
            if code != 0 or not pr:
                return needs_help(picked, "sha mismatch after push", sha)
            sha = out.strip()
            _retry(picked, "fix", lambda: refresh_body(picked["repo"], int(picked["issue"])), "updated")
    code, out, err = git_try(worktree, "rev-parse", "HEAD")
    if code != 0 or out.strip() != sha:
        return needs_help(picked, f"sha mismatch: {err.strip() or out.strip()}", sha)
    saved = state_read(picked["repo"], picked["issue"])
    if saved.get("sha") != sha or (saved.get("verdict") or {}).get("sha") != sha:
        state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "check"}}, verdict=None, fix_fingerprint=None)
    state_update(picked["repo"], picked["issue"], sha=sha)
    return worktree, branch, sha, repo.get("test") or [], 1


def replan_deleted_files(picked: dict, verdict: dict, head: str) -> bool:
    findings = [row for row in verdict.get("uwagi", [])
                if parse_finding(row).lens == "deleted_files"]
    if not findings:
        return False
    reason = "\n".join(parse_finding(row).zmiana for row in findings
                       if isinstance(parse_finding(row), Finding))
    prompt = replan_prompt(picked, reason, findings, head)
    state_update(picked["repo"], picked["issue"], _event={"action": "replan"},
                 plan_prompt=prompt, reason=reason, result="pending")
    return True


def _finish(picked: dict, worktree: Path, branch: str, sha: str, tests: list, plan_rounds: int = 1) -> dict:
    from lokay.review import hunks
    from lokay.effects.git import git_try
    from lokay.effects.gh import check_comment, pr_files
    from lokay import finish

    repo = repo_config(picked["repo"])
    clone_path, _ = _repo_paths(repo, picked["issue"])
    saved = state_read(picked["repo"], picked["issue"])
    rounds = saved.get("check_rounds", 0)
    verdict = saved.get("verdict")
    pending = "check" if saved.get("node") in ("merge", "wait") else saved.get("node")
    if saved.get("result") == "wait" or (verdict or {}).get("result") == "wait":
        if store.derive_waiting_on({**saved, "result": "wait"}) != "ready":
            return verdict or {"result": "wait", "sha": sha}
        state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "check"}}, result="check", verdict=None,
                     retry_at=0, awaiting=None)
        verdict = None
        pending = "check"

    def sync_head():
        return finish.sync_head(worktree, branch)

    base = base_branch(worktree)

    def conflict_fix(files, log):
        return finish.conflict_fix(picked, sha, files, log)

    def sync_main():
        return finish.sync_main(worktree, base)

    while True:
        escalated = escalate(picked, ((verdict or {}).get("uwagi") if verdict else None))
        if escalated:
            return escalated
        if pending == "plan":
            prepared = _prepare({**picked, "node": "plan"})
            if isinstance(prepared, dict):
                return prepared
            worktree, branch, sha, tests, plan_rounds = prepared
            base = base_branch(worktree)
            pending = "check"
        check_deadline()
        saved = state_read(picked["repo"], picked["issue"])
        if saved.get("merge_attempts", {}).get(sha, 0) >= 2:
            pending = "fix"
        elif pending == "merge" and saved.get("merge_conflict_sha") == sha:
            pending = "check"
        if pending == "merge" and not graph.merge_allowed(saved, sha):
            pending = "check"
            verdict = None
            state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "check"}},
                         sha=sha, verdict=None, result="check")
        if pending == "merge" and verdict and verdict.get("sha") == sha:
            merged, base, sha, pending, verdict = finish.merge(
                picked, worktree, branch, sha, verdict, base, plan_rounds, rounds, clone_path, sync_head)
            if merged is not None:
                return merged
        saved = state_read(picked["repo"], picked["issue"])
        blocked = merge_blocked(saved, sha)
        if blocked and pending == "fix":
            pr = _retry(picked, "fix", lambda: open_pr_for(picked["repo"], branch))
            if not pr:
                raise RuntimeError("PR missing after merge conflict")
            pr_number = pr["number"]
            verdict = conflict_fix(_retry(picked, "fix", lambda: pr_files(picked["repo"], pr_number)),
                                   "Merge conflict on GitHub; change the PR before checking again.")
        state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "fix" if pending == "fix" else "check"}}, sha=sha)
        if pending != "fix":
            conflicts = _retry(picked, "check", sync_main)
            if conflicts:
                conflict_verdict = verdict = conflict_fix(conflicts, f"Resolve the merge with origin/{base}.")
                pending = "fix"
                rounds_append(picked["repo"], picked["issue"], "Check: conflict, files=" + ", ".join(conflicts))
                pr = _retry(picked, "check", lambda: open_pr_for(picked["repo"], branch))
                if pr:
                    conflict_pr_number = pr["number"]
                    _retry(picked, "check", lambda: check_comment(picked["repo"], conflict_pr_number,
                           rounds + 1, conflict_verdict, {"result": "conflict"}))
            else:
                pushed = fix_step(picked, "fix_publish", lambda: push(worktree, branch, sha), sha)
                if pushed["result"] == "failed":
                    return pushed
                if pushed["result"] == "remote_moved" and pushed.get("sha"):
                    _retry(picked, "check", sync_head)
                    sha = pushed["sha"]
                    pending = "check"
                    continue
                if pushed["result"] != "pushed":
                    raise RuntimeError(f"base synchronization publish failed: {pushed}")
                previous_sha = sha
                sha = pushed["sha"]
                if not pushed_pr(picked["repo"], branch, sha):
                    return needs_help(picked, "sha mismatch after push", sha)
                _retry(picked, "check", lambda: refresh_body(picked["repo"], int(picked["issue"])), "updated")
                state_update(picked["repo"], picked["issue"], sha=sha, verdict=None)
                if blocked and sha == previous_sha:
                    pr = _retry(picked, "fix", lambda: open_pr_for(picked["repo"], branch))
                    if not pr:
                        raise RuntimeError("PR missing after merge conflict")
                    pr_number = pr["number"]
                    verdict = conflict_fix(_retry(picked, "fix", lambda: pr_files(picked["repo"], pr_number)),
                                           "Merge conflict on GitHub; change the PR before checking again.")
                    pending = "fix"
        def read_diff():
            code, out, err = git_try(worktree, "diff", f"origin/{base}...HEAD", timeout=30)
            if code != 0:
                raise RuntimeError(err or "diff failed")
            return out
        active_node = "fix" if pending == "fix" else "check"
        diff = _retry(picked, active_node, read_diff)
        def read_head():
            code, out, err = git_try(worktree, "rev-parse", "HEAD")
            if code != 0:
                raise RuntimeError(err or "HEAD lookup failed")
            return out.strip()
        head = _retry(picked, active_node, read_head)
        diff_fingerprint = hashlib.sha256((diff or "").encode()).hexdigest()
        if pending != "fix":
            saved = state_read(picked["repo"], picked["issue"])
            if saved.get("replan_diff_fingerprint"):
                if graph.same_patch(saved, diff_fingerprint):
                    code, main_sha, err = git_try(worktree, "rev-parse", f"origin/{base}")
                    if code != 0:
                        raise RuntimeError(err or "main revision lookup failed")
                    main_sha = main_sha.strip()
                    state_update(picked["repo"], picked["issue"], _event={"action": "build_complete", "outcome": {
                        "same_patch": True, "main_sha": main_sha}})
                    rounds_append(picked["repo"], picked["issue"],
                                  f"Check: same patch after replan, diff={diff_fingerprint}, parked until origin/{base} moves from {main_sha}")
                    return {"result": "same_patch", "reason": "same patch after replan", "same_main_sha": main_sha}
                state_update(picked["repo"], picked["issue"], replan_diff_fingerprint=None)
        if pending == "fix" and verdict:
            signal, outcome = finish.fix(
                picked, worktree, branch, sha, verdict, diff, head, diff_fingerprint, repo,
                clone_path, base, read_diff, sync_head)
            if signal == "return":
                return outcome
            sha, pending, verdict = outcome
            continue
        rows = hunks(diff or "")
        saved = state_read(picked["repo"], picked["issue"])
        ci = finish.local_checks(picked, worktree, repo, sha, clone_path, base, tests, rows)
        pr_number, remote = finish.remote_checks(picked, branch, sha)
        if remote["result"] == "sha_moved":
            _retry(picked, "check", sync_head)
            sha = remote["sha"]
            pending = "check"
            continue
        if remote["result"] == "red":
            from lokay.effects.gh import main_inherited

            def compare_main_checks():
                code, main_sha, err = git_try(clone_path, "rev-parse", f"origin/{base}")
                if code != 0:
                    raise RuntimeError(err or "main checks revision lookup failed")
                code, paths, err = git_try(worktree, "diff", "--name-only", "--no-renames", f"origin/{base}...{sha}")
                if code != 0:
                    raise RuntimeError(err or "checks paths lookup failed")
                return main_inherited(picked["repo"], main_sha.strip(), remote,
                                      any(path.startswith(".github/") for path in paths.splitlines()))

            remote = _retry(picked, "check", compare_main_checks)
            state_update(picked["repo"], picked["issue"], ci=remote["result"])
        if remote["result"] == "pending":
            state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "check"}}, result="pending", verdict=None)
            rounds_append(picked["repo"], picked["issue"], f"Check: sha={sha}, GitHub CI pending")
            _retry(picked, "check", lambda: check_comment(picked["repo"], pr_number, rounds + 1,
                   {"result": "pending", "sha": sha, "uwagi": []}, remote))
            return {"result": "pending", "sha": sha}
        ci = {**ci, "failed": ci["failed"] + [
            {"warstwa": "GitHub CI", "plik": "", "check": name,
             "log": name + "\n" + (remote.get("failed_logs") or {}).get(name, name)}
            for name in remote.get("failed") or []
        ], "ci": remote["result"],
            **({"inherited": remote["inherited"]} if remote.get("inherited") else {}),
            "notes": [*ci["notes"], *(remote.get("notes") or [])],
            "result": "green" if ci["result"] == "green" and remote["result"] in ("green", "no_ci", "inherited") else "red"}
        state_update(picked["repo"], picked["issue"], local_ci=ci)
        decisions, kinds, check_notes, dismissed_keys, plan_text, check_results, checks_failed, main_sha = finish.lenses(
            picked, worktree, base, sha, saved, diff, rows, ci, rounds)
        verdict, rounds = finish.complete_check(
            picked, worktree, base, sha, ci, decisions, plan_text, checks_failed, dismissed_keys,
            check_results, pr_number, rounds, check_notes, diff_fingerprint, kinds, conflict_fix, main_sha)
        if replan_deleted_files(picked, verdict, sha):
            return {"result": "pending", "next": "plan"}
        derived = graph.step(store.load(picked["repo"], picked["issue"]),
                             Checked(time.time(), outcome=verdict)).state
        pending = derived["node"]
        findings = [finding for entry in derived.get("check_history", [])
                    for finding in entry.get("findings", [])]
        if pending == "plan":
            from lokay.retro import publish

            split = derived.get("fix_limit_hits", 0) >= 2 and derived.get("pr") is None
            prompt = replan_prompt(
                picked,
                ("Split this issue into smaller tasks against every finding below. " if split else "")
                + f"Check→Fix did not converge in {graph.FIX_ROUND_LIMIT} rounds; revise the plan against every finding below.",
                findings, sha)
            prompt += "\n\nEvery Check finding:\n" + dumps(findings, ensure_ascii=False)
            state_update(picked["repo"], picked["issue"],
                         _event={"action": "verdict", "outcome": verdict}, plan_prompt=prompt)
            _retry(picked, "plan", publish)
            rounds_append(picked["repo"], picked["issue"],
                          "Fix round limit → split" if split else f"Fix round limit → Plan (hit {derived['fix_limit_hits']})")
            store.log_event("fix_round_limit", hit=derived["fix_limit_hits"], repo=picked["repo"], issue=picked["issue"],
                            rounds=rounds, reason=derived["reason"])
            if split:
                return _split_issue(picked, clone_path)
            return {"result": "pending", "next": "plan"}
        escalated = escalate(picked, verdict.get("uwagi"))
        if escalated:
            return escalated
        if pending == "wait":
            return finish.wait(picked, verdict, head)
        state_update(picked["repo"], picked["issue"], _event={"action": "verdict", "outcome": verdict})

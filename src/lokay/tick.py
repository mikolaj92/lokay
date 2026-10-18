from __future__ import annotations

from copy import deepcopy
from functools import partial

import hashlib
import json
import os
import re
import shutil
import signal
import sys
import time
from collections.abc import Callable
from pathlib import Path

from lokay import graph, store
from dataclasses import replace
from lokay.types import PLAN_RESET, Event, Run, Snapshot, RepoSnapshot, Dispatched, parse_event, pr_number
from lokay.merge import merge_blocked
from lokay.effects import maintenance
from lokay.effects.git import base_branch, changes_before_merge, commit_paths, worktree_remove
from lokay.effects.git import git, head as git_head

from lokay.types import Finding, Note, parse_finding
from lokay.config import load_repos, repo as repo_config, tick_budget
from lokay.effects.gh import gh_json, gh_ok, auth_status, open_issues, open_pr_for
from lokay.effects.retry import retry
from lokay.store import acquire_lock, release_lock, lock_path
from lokay.effects.pi import (TickExpired, check_deadline, cleanup_process_groups, kill_process_groups,
                       process_groups, retry_sleep, run_process, tick_deadline)
from lokay.store import repo_attempt, repo_last_attempt, rounds_append, run_dir, state_read, state_update


dumps = partial(json.dumps, default=store.json_default)


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
            if saved.get("plan_schema") == 2 and node != "plan":
                from lokay.plan import valid_plan

                if not valid_plan(run_dir(picked["repo"], picked["issue"]) / "plan.md", 2):
                    outcome = {"next": "plan", "reason": "PLAN ERROR: invalid version-2 plan"}
                    state_update(picked["repo"], picked["issue"],
                                 _event={"action": "replan", "outcome": outcome},
                                 **deepcopy(PLAN_RESET))
                    return outcome
            prepared = _prepare(picked) if node in ("plan", "build") else _resume(picked)
            outcome = prepared if isinstance(prepared, dict) else _finish(picked, *prepared)
        except TickExpired:
            repo, issue = picked["repo"], picked["issue"]
            state_update(repo, issue, result="pending", reason="tick budget exhausted")
            rounds_append(repo, issue, "Tick: budget exhausted; resume saved node")
            return {"result": "pending", "reason": "tick budget exhausted"}
        except Escalated as exc:
            return exc.outcome
        except RetryLater as exc:
            return {"result": "failed", "reason": str(exc)}
        except Exception as exc:
            outcome = {"result": "failed", "reason": f"{type(exc).__name__}: {exc}"}
        if outcome.get("next") in ("plan", "build"):
            return outcome
        repo, issue = picked["repo"], picked["issue"]
        if outcome.get("result") in ("pending", "pr_open", "check", "wait"):
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
        if (repo["merge"] != "on" or name == "mikolaj92/Temida" or not clone.is_dir()
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
            check_main(name, clone, config=repo)
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

    def list_prs(name):
        if name not in pr_lists:
            pr_lists[name] = tuple(gh_json([
                "pr", "list", "--repo", name, "--state", "open", "--limit", "1000000",
                "--json", "number,headRefName,headRefOid,labels,state",
            ], error="pr list failed", default="[]"))
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
            if saved.get("awaiting") == "children":
                from lokay.effects.gh import children_merged

                held = acquire_lock(lock_path(name.split("/")[0], name))
                if held["result"] == "held":
                    try:
                        saved = state_read(name, issue)
                        if (saved.get("awaiting") == "children"
                                and children_merged(name, saved.get("children") or [])):
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
        busy = False
        active = {issue: saved for issue, saved in states.items()
                  if saved.get("result") not in ("merged", "closed")
                  and (only_issue is None or issue == only_issue)}
        if active:
            owner, repo_name = name.split("/", 1)
            fields = [f"issue_{int(issue)}: issueOrPullRequest(number: {int(issue)}) "
                      "{ ... on Issue { state } ... on PullRequest { state } }" for issue in active]
            fields.extend(f"pr_{number}: pullRequest(number: {number}) {{ state }}"
                          for number in sorted({int(saved["pr"]) for saved in active.values() if saved.get("pr")}))
            query = ("query($owner: String!, $name: String!) { repository(owner:$owner,name:$name) { "
                     + " ".join(fields) + " } }")
            response = gh_json(["api", "graphql", "-f", f"owner={owner}", "-f", f"name={repo_name}",
                                "-f", f"query={query}"], allow_partial_data=True)
            remote = response["data"].get("repository") or {}
            closing = []
            for issue, saved in active.items():
                if (remote.get(f"issue_{int(issue)}") or {}).get("state") == "CLOSED":
                    closing.append(issue)
                elif saved.get("pr"):
                    if (remote.get(f"pr_{int(saved['pr'])}") or {}).get("state") == "CLOSED":
                        closing.append(issue)
                else:
                    prs = gh_json([
                        "pr", "list", "--repo", name, "--head", saved.get("branch") or f"lokay/{issue}",
                        "--state", "closed", "--json", "number,headRefName,state",
                    ], error="pr list failed", default="[]")
                    if any(row.get("state") == "CLOSED" for row in prs):
                        closing.append(issue)
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
                            state_update(name, issue, _event={"action": "closed"})
                            states[issue] = state_read(name, issue)
                            root, worktree = _repo_paths(repo, issue)
                            cleanup = worktree_remove(root, worktree, safe=True, branch=f"lokay/{issue}")
                            store.log_event("closed_cleanup", repo=name, issue=issue, outcome=cleanup)
                    finally:
                        release_lock(held)
        snapshots.append(RepoSnapshot(name, repo_last_attempt(name), statuses.get(name, {}),
                                      states=states, busy=busy))
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
            prs = tuple(row for row in list_prs(name) if row.get("state", "OPEN") == "OPEN")
            states = {}
            for row in prs:
                branch = row["headRefName"]
                if not branch.startswith("lokay/") or not branch[6:].isdecimal():
                    continue
                issue = int(branch[6:])
                if only_issue is not None and issue != only_issue:
                    continue
                saved = state_read(name, issue)
                if saved.get("result") in ("closed", "merged"):
                    states[issue] = saved
                    continue
                states[issue] = saved
                if saved.get("waiting_on") == "retry_at" or saved.get("retry_at", 0) > time.time():
                    blocked.append((name, issue, saved))
            repo = replace(repo, prs=prs, states={**repo.states, **states})
        elif selected.kind == "issues":
            issues = tuple(row for row in list_issues(name)
                           if row.get("state", "OPEN") == "OPEN"
                           and (only_issue is None or int(row["number"]) == only_issue))
            states = {}
            open_prs = set()
            for row in issues:
                issue = row["number"]
                saved = states[issue] = state_read(name, issue)
                if (saved.get("result") in ("merged", "closed")
                        or saved.get("waiting_on") in ("children", "ci")):
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
                    if selected.kind == "red_main":
                        pr = open_pr_for(name, branch)
                        saved = state_read(name, number)
                        node = saved.get("node") or ("check" if pr else "plan")
                        state_update(name, number,
                                     _event={"action": "red_main", "outcome": {"pr": pr, "status": repo.status}},
                                     branch=branch, pr=pr["number"] if pr else None, last_attempt=time.time())
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
                            if labelled or saved.get("result") == "parked":
                                resumed = store.escalation_fields(saved)
                                resumed.pop("node")
                                resumed.pop("result")
                                resumed.pop("reason")
                                node = "plan"
                            node = node if node in ("plan", "build", "check", "fix", "merge") else "check"
                        else:
                            node = node or "plan"
                            if saved.get("result") == "parked":
                                resumed = store.escalation_fields(saved)
                                resumed.pop("node")
                                resumed.pop("result")
                                resumed.pop("reason")
                                node = "plan"
                        state_update(name, number, _event={"action": "enter_node", "outcome": {"node": node}}, branch=branch, pr=pr["number"] if pr else None,
                                     result="running", reason=None, last_attempt=time.time(),
                                     **resumed)
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
    body = pr_body(worktree, run_dir(repo, issue) / "plan.md", issue,
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
        try:
            _tick()
            return 0
        except TickExpired:
            return 0
        finally:
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


def _retry[T](picked: dict, node: str, action: Callable[[], T], expected: str | None = None, *, plan_branch: bool = False) -> T:
    repo, issue = picked["repo"], picked["issue"]
    state_update(repo, issue, _event={"action": "enter_node", "outcome": {"node": node}})
    try:
        check_deadline()
        if node in {"plan", "build", "check", "fix", "merge"}:
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
    outcome = needs_help(picked, reason, plan_branch=plan_branch)
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
    art = directory / "plan.md"
    rounds = directory / "rounds.md"
    prompt = prompt_for(saved.get("issue_title") or "", saved.get("issue_body")) + (
        "\n\nPrevious plan:\n" + (art.read_text() if art.is_file() else "")
        + "\n\nUwagi:\n" + dumps(history, ensure_ascii=False)
        + "\n\nLast state:\n" + dumps({key: value for key, value in saved.items()
                                     if key not in ("plan_prompt", "plan_branches", "plan_synthesis")}, ensure_ascii=False)
        + "\n\nFix history:\n" + dumps(saved.get("fix_history", []), ensure_ascii=False)
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


def _plan_graph(picked: dict, art: Path, title: str, body: str | None, *, cwd: Path | None = None) -> int:
    from lokay import plan
    from lokay.effects.decide import decide

    repo, issue = picked["repo"], picked["issue"]
    store.ensure_directory(art.parent)
    while True:
        if escalated := escalate(picked):
            raise Escalated(escalated)
        saved = state_read(repo, issue)
        context = saved.get("plan_prompt") or plan.prompt_for(title, body)
        branches = saved.get("plan_branches") or {}
        synthesis = saved.get("plan_synthesis") or {}
        rounds = saved.get("plan_rounds", 0)
        difficulty = saved["difficulty"]
        if difficulty == "easy":
            phase = saved.get("plan_phase") or "write"
            state_update(repo, issue, _event={"action": "enter_node", "outcome": {"node": "plan"}}, plan_phase=phase, plan_prompt=context)

            def single_written():
                nonlocal rounds, phase
                rounds += 1
                phase = "check"
                state_update(repo, issue, plan_phase=phase, plan_rounds=rounds)
                rounds_append(repo, issue, f"Plan single {rounds}: write")

            outcome = _retry(picked, "plan", lambda: plan.plan_one(
                "minimal", context, art, cwd=cwd, phase=phase,
                on_written=single_written, single=True, plan_schema=2), "done", plan_branch=True)
            rounds_append(repo, issue, f"Plan single {rounds}: Decision {outcome['next']}")
            if outcome["next"] == "ok":
                state_update(repo, issue, _event={"action": "synthesis", "outcome": outcome},
                             plan_kind=outcome.get("kind", "code"),
                             plan_schema=2, plan_accepted_sha=hashlib.sha256(art.read_bytes()).hexdigest(),
                             plan_notes=outcome.get("notes", []), fix_history=[], fix_counts=[],
                             **store.round_fields(state_read(repo, issue), accepted_plan=True))
                return rounds
            state_update(repo, issue, **store.round_fields(state_read(repo, issue)))
            prompt = replan_prompt(picked, "Single plan rejected", outcome["uwagi"])
            state_update(repo, issue, **deepcopy(PLAN_RESET), plan_prompt=prompt, plan_notes=[])
            continue
        paths = {}
        for perspective in plan.PERSPECTIVES[:2 if difficulty == "medium" else 3]:
            branch_art = art.parent / "plans" / f"{perspective}.md"
            store.ensure_directory(branch_art.parent)
            branch = branches.setdefault(perspective, {
                "phase": "write", "rounds": 0, "accepted_sha": None,
                "prompt": context, "fingerprint": None,
            })
            accepted = (plan.valid_plan(branch_art, branch.get("plan_schema")) and branch.get("accepted_sha") ==
                        hashlib.sha256(branch_art.read_bytes()).hexdigest())
            if accepted:
                paths[perspective] = branch_art
                continue
            if branch["phase"] == "failed":
                continue
            if branch["phase"] == "accepted":
                branch.update(phase="write", accepted_sha=None)
            while True:
                if escalated := escalate(picked):
                    raise Escalated(escalated)
                state_update(repo, issue, _event={"action": "enter_node", "outcome": {"node": "plan"}}, plan_phase="write", plan_prompt=context,
                             plan_branches=branches, plan_synthesis=synthesis)
                check_deadline()
                def written():
                    nonlocal rounds
                    rounds += 1
                    branch.update(phase="check", rounds=branch["rounds"] + 1, plan_schema=2)
                    state_update(repo, issue, plan_branches=branches, plan_rounds=rounds)
                    rounds_append(repo, issue, f"Plan {perspective} {branch['rounds']}: write")
                try:
                    outcome = _retry(picked, "plan", lambda: plan.plan_one(
                        perspective, branch["prompt"], branch_art,
                        cwd=cwd, phase=branch["phase"], on_written=written,
                        plan_schema=branch.get("plan_schema")), "done", plan_branch=True)
                except RetryLater as exc:
                    branch.update(phase="failed", reason=str(exc), accepted_sha=None)
                    state_update(repo, issue, plan_branches=branches,
                                 **store.round_fields(state_read(repo, issue)))
                    rounds_append(repo, issue, f"Plan {perspective}: failed: {exc}")
                    break
                rounds_append(repo, issue, f"Plan {perspective} {branch['rounds']}: Decision {outcome['next']}")
                if outcome["next"] == "ok":
                    branch.update(phase="accepted", accepted_sha=hashlib.sha256(branch_art.read_bytes()).hexdigest(),
                                  kind=outcome.get("kind", "code"))
                    paths[perspective] = branch_art
                    state_update(repo, issue, plan_branches=branches, fix_history=[], fix_counts=[],
                                 **store.round_fields(state_read(repo, issue), accepted_plan=True))
                    break
                state_update(repo, issue, **store.round_fields(state_read(repo, issue)))
                fingerprint = hashlib.sha256(dumps(outcome["uwagi"], sort_keys=True).encode()).hexdigest()
                branch.update(phase="write", fingerprint=fingerprint,
                              prompt=context + "\n\nPrevious branch plan:\n" + branch_art.read_text()
                              + "\n\nUwagi:\n" + dumps(outcome["uwagi"], ensure_ascii=False))
                state_update(repo, issue, plan_branches=branches)
                retry_sleep(20)
        if len(paths) != (2 if difficulty == "medium" else 3):
            reasons = [{"perspective": name, "reason": branch.get("reason")} for name, branch in branches.items()]
            prompt = replan_prompt(picked, "Not all required plans were accepted", reasons)
            state_update(repo, issue, **deepcopy(PLAN_RESET), plan_prompt=prompt)
            retry_sleep(20)
            continue
        if difficulty == "medium":
            comparison = _retry(picked, "plan", lambda: decide(plan.comparison_questions(paths, context)))
            choice = comparison["next"]["choice"]
            if choice not in paths:
                raise RuntimeError("invalid plan comparison choice")
            store.write_artifact(art, paths[choice].read_text())
            state_update(repo, issue, _event={"action": "synthesis", "outcome": {"next": "ok"}},
                         plan_comparison=comparison, plan_kind=branches[choice].get("kind", "code"),
                         plan_schema=branches[choice].get("plan_schema"), plan_accepted_sha=hashlib.sha256(art.read_bytes()).hexdigest(),
                         plan_notes=[], fix_history=[], fix_counts=[],
                         **store.round_fields(state_read(repo, issue), accepted_plan=True))
            return rounds
        synthesis = synthesis or {"phase": "write", "fingerprint": None, "uwagi": [], "rounds": 0}
        fresh = False
        while True:
            if escalated := escalate(picked):
                raise Escalated(escalated)
            state_update(repo, issue, _event={"action": "enter_node", "outcome": {"node": "plan"}}, plan_phase="write", plan_synthesis=synthesis)
            check_deadline()
            if synthesis["phase"] == "write" or not plan.valid_plan(art, synthesis.get("plan_schema")):
                failed = {name: branch.get("reason") for name, branch in branches.items() if branch["phase"] == "failed"}
                prompt = context + "\n\nFailed branches:\n" + dumps(failed, ensure_ascii=False)
                prompt += "\n\nUwagi:\n" + dumps(synthesis["uwagi"], ensure_ascii=False)
                _retry(picked, "plan", lambda: plan.synthesize(paths, prompt, art, cwd=cwd), "done")
                rounds += 1
                synthesis.update(phase="check", rounds=synthesis["rounds"] + 1, plan_schema=2)
                state_update(repo, issue, plan_synthesis=synthesis, plan_rounds=rounds)
                rounds_append(repo, issue, f"Synteza {synthesis['rounds']}: write")
            check_deadline()
            outcome = plan.verdict(decide(plan.plan_questions(art.read_text())))
            if outcome.get("next") not in ("ok", "revise"):
                raise RuntimeError(f"unknown plan verdict: {outcome.get('next')}")
            rounds_append(repo, issue, f"Synteza {synthesis['rounds']}: Decision {outcome['next']}")
            if outcome["next"] == "ok":
                synthesis["phase"] = "accepted"
                state_update(repo, issue, _event={"action": "synthesis", "outcome": outcome},
                             plan_synthesis=synthesis, plan_kind=outcome.get("kind", "code"),
                             plan_schema=synthesis.get("plan_schema"), plan_accepted_sha=hashlib.sha256(art.read_bytes()).hexdigest(),
                             plan_notes=outcome.get("notes", []), fix_history=[], fix_counts=[],
                             **store.round_fields(state_read(repo, issue), accepted_plan=True))
                return rounds
            state_update(repo, issue, **store.round_fields(state_read(repo, issue)))
            fingerprint = hashlib.sha256(dumps(outcome["uwagi"], sort_keys=True).encode()).hexdigest()
            if synthesis["fingerprint"] == fingerprint:
                prompt = replan_prompt(picked, "Repeated synthesis rejection", outcome["uwagi"])
                state_update(repo, issue, **deepcopy(PLAN_RESET), plan_prompt=prompt)
                fresh = True
            else:
                synthesis.update(phase="write", fingerprint=fingerprint, uwagi=outcome["uwagi"])
                state_update(repo, issue, plan_synthesis=synthesis)
            retry_sleep(20)
            if fresh:
                break


def _prepare(picked: dict) -> tuple | dict:
    from lokay.build import build_code, build_publish, recover_no_changes

    from lokay import plan

    saved = state_read(picked["repo"], picked["issue"])
    if "issue_title" not in saved or "issue_body" not in saved:
        loaded = gh_json(["issue", "view", str(picked["issue"]), "--repo", picked["repo"], "--json", "title,body"],
                         error="issue view failed")
        if not isinstance(loaded.get("title"), str) or not loaded["title"].strip():
            raise RuntimeError("issue title is missing or invalid")
        body = loaded.get("body")
        if body is not None and not isinstance(body, str):
            raise RuntimeError("issue body is invalid")
        state_update(picked["repo"], picked["issue"], issue_title=loaded["title"], issue_body=body)
        saved = state_read(picked["repo"], picked["issue"])
    title, body = saved["issue_title"], saved["issue_body"]
    if saved.get("difficulty") not in plan.DIFFICULTIES:
        from lokay.effects.decide import decide

        answer = _retry(picked, "plan", lambda: decide(plan.difficulty_questions(title, body)))["difficulty"]
        if answer["choice"] not in plan.DIFFICULTIES:
            raise RuntimeError("invalid difficulty choice")
        state_update(picked["repo"], picked["issue"], difficulty=answer["choice"], difficulty_decision=answer)
        saved = state_read(picked["repo"], picked["issue"])
    repo = repo_config(picked["repo"])
    root, worktree = _repo_paths(repo, picked["issue"])
    _ensure_worktree(picked)
    if saved["difficulty"] == "too_big":
        from lokay.effects.gh import create_child_issue

        tasks = saved.get("split_tasks")
        if tasks is None:
            outcome = _retry(picked, "plan", lambda: plan.split_tasks(
                saved.get("plan_prompt") or plan.prompt_for(title, body),
                run_dir(picked["repo"], picked["issue"]) / "split.json", cwd=root), "done")
            tasks = plan.validate_tasks(outcome["tasks"])
            state_update(picked["repo"], picked["issue"], split_tasks=tasks, children=[])
        tasks = plan.validate_tasks(tasks)
        children = list(state_read(picked["repo"], picked["issue"]).get("children") or [])
        for index, task in enumerate(tasks):
            if index < len(children):
                continue
            number = create_child_issue(picked["repo"], picked["issue"], index, task,
                                        saved.get("split_generation", 0))
            children.append(number)
            state_update(picked["repo"], picked["issue"], children=children)
        state_update(picked["repo"], picked["issue"], awaiting="children", _event={"action": "enter_node", "outcome": {"node": "plan"}},
                     result="pending", retry_at=0, failures=0, reason=None)
        return {"result": "pending", "children": children}

    if saved.get("node", picked["node"]) == "plan" and worktree.exists() and not saved.get("previous_head"):
        state_update(picked["repo"], picked["issue"], previous_head=git_head(worktree))
    art = run_dir(picked["repo"], picked["issue"]) / "plan.md"
    plan_rounds = saved.get("plan_rounds", 0)
    accepted = (plan.valid_plan(art, saved.get("plan_schema")) and saved.get("plan_accepted_sha") ==
                hashlib.sha256(art.read_bytes()).hexdigest())
    if saved.get("node", picked["node"]) == "plan" or saved.get("plan_phase") or not accepted:
        plan_rounds = _plan_graph(picked, art, title, body, cwd=root)
    branch = f"lokay/{picked['issue']}"
    check_deadline()
    if saved.get("build_from_main"):
        state_update(picked["repo"], picked["issue"], build_from_main=False)
    plan_text = art.read_text()
    state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "build"}}, branch=branch)
    base = base_branch(worktree)
    try:
        git(worktree, "fetch", "origin", base, timeout=300)
    except RuntimeError as exc:
        return needs_help(picked, f"build fetch: {exc}")
    try:
        changed_paths = changes_before_merge(worktree)
        if changed_paths:
            committed = commit_paths(worktree, changed_paths, "lokay build (resume)")
            if committed:
                rounds_append(picked["repo"], picked["issue"],
                              f"Build: committed leftover changes before merge: {len(committed)} files")
        git(worktree, "merge", "--no-edit", f"origin/{base}", timeout=300)
    except RuntimeError as exc:
        return needs_help(picked, f"build merge: {exc}")
    from lokay.setup import prepare_dependencies

    prepare_dependencies(worktree, repo, int(picked["issue"]))
    saved = state_read(picked["repo"], picked["issue"])
    build_note = saved.get("build_note")
    if saved.get("plan_notes"):
        build_note = (build_note or "") + "\n\nNon-blocking plan notes:\n" + dumps(saved["plan_notes"])
    check_deadline()
    built = build_code(worktree, plan_text, title, body, dict(os.environ), expected_branch=branch,
                       clone_path=root, previous_head=state_read(picked["repo"], picked["issue"]).get("previous_head"),
                       **({"build_note": build_note} if build_note else {}),
                       **({"kind": "docs_change"} if saved.get("plan_kind", "code") == "docs_change" else {}))
    built = recover_no_changes(worktree, built, branch, picked=picked)
    if built.get("result") == "failed":
        reason = built.get("reason") or "build failed"
        explanation = built.get("explanation") or built.get("artifact") or ""
        rounds_append(picked["repo"], picked["issue"], f"Build → Plan: {reason}")
        state_update(picked["repo"], picked["issue"], _event={"action": "build_complete", "outcome": built},
                     plan_prompt=replan_prompt(picked, f"Uwagi (Build): {reason}: {explanation}", [built],
                                               git_head(worktree) if worktree.exists() else None))
        return {**built, "next": "plan"}
    if built.get("result") != "done":
        raise RuntimeError(f"unexpected Build outcome: {built}")
    state_update(picked["repo"], picked["issue"], _event={"action": "build_complete", "outcome": built})
    def publish():
        pr = open_pr_for(picked["repo"], branch)
        expected = pr.get("headRefOid") if pr else None
        outcome = build_publish(
            worktree, branch, expected, picked["repo"], int(picked["issue"]),
            title, art,
        )
        if outcome.get("result") == "pr_open" and not outcome.get("sha"):
            return {"result": "failed", "reason": "missing published SHA"}
        return outcome
    published = _retry(picked, "build", publish, "pr_open")
    state_update(
        picked["repo"], picked["issue"], pr=published.get("pr"),
        sha=published.get("sha"), result=published["result"],
    )
    state_update(picked["repo"], picked["issue"], _event={"action": "published", "outcome": published})
    return worktree, branch, published["sha"], repo.get("test") or [], plan_rounds


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
    if saved.get("result") == "merged" or saved.get("awaiting") == "children":
        return None
    now = time.time()
    if not any(saved.get(key) for key in ("diff_changed_at", "issue_since", "ladder_since")):
        state_update(repo, issue, ladder_since=now)
    since = max(saved.get("diff_changed_at") or saved.get("issue_since")
                or saved.get("ladder_since") or now, saved.get("ladder_since") or 0)
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
                           uwagi or (saved.get("verdict") or {}).get("uwagi", []),
                           saved.get("sha") or "")
    fields = store.escalation_fields(saved)
    state_update(repo, issue, _event={"action": "enter_node", "outcome": {"node": fields.pop("node")}},
                 **{**fields, "plan_prompt": prompt})
    rounds_append(repo, issue, f"Difficulty → {fields['difficulty']}")
    return {"result": "pending", "next": "plan"}


def fix_to_build(picked: dict, worktree: Path) -> dict | None:
    from lokay.effects.git import git_try
    from lokay.scope import is_test

    saved = state_read(picked["repo"], picked["issue"])
    ci = saved.get("local_ci") or {}
    code, head, err = git_try(worktree, "rev-parse", "HEAD")
    if code != 0:
        raise RuntimeError(err or "HEAD lookup failed")
    if ci.get("sha") != head.strip():
        return None
    if ci.get("result") != "red":
        return None
    log = ci.get("log") or ""
    failed = re.findall(r"^FAILED\s+([^\s:]+)::", log, re.MULTILINE)
    if not failed:
        return None
    code, added, err = git_try(worktree, "diff", "--name-status", "--diff-filter=A", f"origin/{base_branch(worktree)}...HEAD")
    if code != 0:
        raise RuntimeError(err or "added test diff failed")
    added_tests = {line.split("\t", 1)[1] for line in added.splitlines()
                   if "\t" in line and is_test(line.split("\t", 1)[1])}
    code, tracked, err = git_try(worktree, "ls-files")
    if code != 0:
        raise RuntimeError(err or "test paths lookup failed")
    tests = [path for path in tracked.splitlines() if is_test(path)]
    files = set()
    for path in failed:
        relative = path.removeprefix("./")
        if Path(path).is_absolute():
            try:
                relative = str(Path(path).relative_to(worktree))
            except ValueError:
                continue
        matches = [name for name in tests if name == relative or name.endswith("/" + relative)]
        if len(matches) == 1 and matches[0] in added_tests:
            files.add(matches[0])
    if not files:
        return None
    names = ", ".join(sorted(files))
    note = (f"Failing test(s) added by this PR: {names}\n{log[-6000:]}\n"
            "Fix the production code so they pass, or remove these newly added tests (new unit tests are not allowed).")
    rounds_append(picked["repo"], picked["issue"], "Fix → Build: failing test added in this PR: " + names)
    state_update(picked["repo"], picked["issue"], _event={"action": "fix_to_build", "outcome": ci},
                 build_note=note)
    return {"next": "build"}


def fix_step(picked: dict, node: str, action, sha: str) -> dict:
    try:
        check_deadline()
        _ensure_worktree(picked)
        outcome = action()
    except Exception as exc:
        return needs_help(picked, f"{node}: {type(exc).__name__}: {exc}", sha)
    if node == "fix_code" and outcome.get("next") == "build":
        return outcome
    if node == "fix_code" and outcome.get("reason") == "outside_worktree":
        prompt = replan_prompt(picked, outcome.get("explanation") or "outside_worktree", [outcome], sha)
        state_update(picked["repo"], picked["issue"], _event={"action": "replan", "outcome": outcome},
                     plan_prompt=prompt, result="failed", reason="outside_worktree", retry_at=0)
        return {**outcome, "next": "plan"}
    expected = "done" if node == "fix_code" else "pushed"
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
    from lokay.build import fix_publish, tidy_and_commit

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
            published = fix_step(picked, "fix_publish", lambda: fix_publish(worktree, branch, sha), sha)
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


def _finish(picked: dict, worktree: Path, branch: str, sha: str, tests: list, plan_rounds: int = 1) -> dict:
    from lokay.review import hunks
    from lokay.build import fix_publish
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
                pushed = fix_step(picked, "fix_publish", lambda: fix_publish(worktree, branch, sha), sha)
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
        ], "ci": remote["result"], "notes": [*ci["notes"], *(remote.get("notes") or [])],
            "result": "green" if ci["result"] == "green" and remote["result"] in ("green", "no_ci") else "red"}
        state_update(picked["repo"], picked["issue"], local_ci=ci)
        decisions, kinds, check_notes, dismissed_keys, plan_text, check_results, checks_failed = finish.lenses(
            picked, worktree, base, sha, saved, diff, rows, ci, rounds)
        verdict, rounds = finish.complete_check(
            picked, worktree, base, sha, ci, decisions, plan_text, checks_failed, dismissed_keys,
            check_results, pr_number, rounds, check_notes, diff_fingerprint, kinds, conflict_fix)
        pending = verdict["result"]
        escalated = escalate(picked, verdict.get("uwagi"))
        if escalated:
            return escalated
        if pending == "wait":
            return finish.wait(picked, verdict, head)
        state_update(picked["repo"], picked["issue"], _event={"action": "verdict", "outcome": verdict})

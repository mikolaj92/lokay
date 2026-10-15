from __future__ import annotations

from json import dumps

import hashlib
import json
import os
import re
import shutil
import signal
import time
from functools import wraps
from pathlib import Path

from lokay import store
from lokay.git import command

from lokay.types import Finding, Note, parse_finding
from lokay.config import load_repos, tick_budget
from lokay.gh import _gh, auth_status, open_issues, open_pr_for
from lokay.lock import acquire, release
from lokay.run import (TickExpired, check_deadline, cleanup_process_groups, kill_process_groups,
                       process_groups, retry_sleep, run_process, tick_deadline)
from lokay.store import repo_attempt, repo_last_attempt, rounds_append, run_dir, state_read, state_update


def step(state: dict, event: dict) -> dict:
    current = dict(state)
    fields = dict(event["fields"])
    action = event.get("action")
    outcome = event.get("outcome") or {}
    if action == "needs_help":
        reason = outcome["reason"]
        failures = current.get("failures", 0) + 1
        transient = bool(re.search(
            r"timeout|timed out|connection|could not resolve host|network|HTTP 5\d\d|host probe",
            reason, re.IGNORECASE))
        to_plan = not event.get("plan_branch") and not transient and (
            current.get("last_error") == reason or reason.startswith("fix_code"))
        delay = min(3600, 60 * 2 ** min(failures - 1, 6)) if transient else 0
        fields.update(node="plan" if to_plan else current.get("node") or "check",
                      result="failed", reason=reason, last_error=None if to_plan else reason,
                      failures=failures, retry_at=event["ts"] + delay if delay else 0)
        if to_plan:
            fields.update(plan_phase="write", plan_branches={}, plan_synthesis={},
                          plan_evaluations=0, plan_accepted_sha=None)
    elif action == "replan" or (action == "build_complete" and outcome.get("result") == "failed"):
        fields.update(node="plan", plan_phase="write", plan_branches={}, plan_synthesis={},
                      plan_evaluations=0, plan_accepted_sha=None)
        if action == "build_complete":
            fields.update(result="failed", reason=outcome.get("reason") or "build failed",
                          failures=current.get("failures", 0) + 1, retry_at=0)
    elif action == "retry_succeeded":
        fields.update(failures=0, retry_at=0, reason=None)
    elif action == "build_complete" and outcome.get("result") == "done":
        fields.update(failures=0, reason=None, retry_at=0, build_note=None, previous_head=None,
                      pi_response=outcome.get("pi_response") or "")
    elif action == "fix_to_build":
        fields.update(node="build", result="running", reason=None, failures=0, retry_at=0)
    elif action == "synthesis" and outcome.get("next") == "ok":
        fields.update(node="build", plan_phase=None, plan_prompt=None)
    elif action == "published" and outcome.get("result") == "pr_open":
        fields.update(node="check", verdict=None)
    elif action == "verdict":
        fields["node"] = outcome["result"]
        if outcome["result"] == "plan":
            fields.update(plan_phase="write", plan_branches={}, plan_synthesis={},
                          plan_evaluations=0, plan_accepted_sha=None)
    elif action == "fix_complete":
        fields.update(node="check", verdict=None)
    elif action == "merge_complete":
        fields["result"] = outcome["result"]
    elif action == "red_main":
        fields.update(node=current.get("node") or ("check" if outcome.get("pr") else "plan"),
                      result="running", reason=None, retry_at=0)
    if "node" in fields and (fields["node"] != current.get("node") or "node_since" not in current):
        current["node_since"] = event["ts"]
    if fields.get("last_attempt") and not current.get("issue_since"):
        current["issue_since"] = event["ts"]
    if fields.get("result") == "merged":
        current["issue_since"] = None
    current.update(fields)
    if fields.get("failures") == 0 and "result" not in fields and current.get("result") == "failed":
        current["result"] = "running"
    return current


class RetryLater(RuntimeError):
    pass


def guarded_step(step):
    @wraps(step)
    def guarded(picked: dict) -> dict:
        before = state_read(picked["repo"], picked["issue"]).get("updated_at")
        try:
            check_deadline()
            outcome = step(picked)
        except TickExpired:
            repo, issue = picked["repo"], picked["issue"]
            state_update(repo, issue, result="pending", reason="tick budget exhausted")
            rounds_append(repo, issue, "Tick: budget exhausted; resume saved node")
            return {"result": "pending", "reason": "tick budget exhausted"}
        except RetryLater as exc:
            return {"result": "failed", "reason": str(exc)}
        except Exception as exc:
            outcome = {"result": "failed", "reason": f"{type(exc).__name__}: {exc}"}
        if outcome.get("next") in ("plan", "build"):
            return outcome
        repo, issue = picked["repo"], picked["issue"]
        if outcome.get("result") in ("pending", "pr_open"):
            return outcome
        if outcome.get("result") == "merged":
            state_update(repo, issue, result="merged", failures=0, retry_at=0, reason=None)
            from lokay.observe import current

            current(result="merged", node=None, node_since=None, issue_since=None,
                    idle_reason=None, last_merge=time.time())
            return outcome
        state = state_read(repo, issue)
        if (state.get("result") == "failed" and state.get("reason") == outcome.get("reason")
                and state.get("updated_at") != before):
            return outcome
        reason = outcome.get("reason") or outcome.get("error") or outcome.get("artifact") or "node failed"
        return needs_help(picked, reason)
    return guarded


def is_task(issue: dict) -> bool:
    # Epics and trackers group tasks; lokay-stalled is an alarm, not a task.
    title = issue["title"].strip().lower()
    return not (
        title.startswith(("epic", "[tracker]", "tracker"))
        or title == "lokay-stalled"
        or any(
            (label.get("name", "") if isinstance(label, dict) else label).lower()
            in ("tracker", "epic")
            for label in issue.get("labels") or []
        )
    )


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
    report = probes(env)
    if not host_ready(report):
        failed = " ".join(f"{name}={value}" for name, value in report.items() if value != "ok")
        return {"result": "idle", "reason": "host_down", "failed": failed}
    child = os.environ if env is None else env
    repos_file = child.get("LOKAY2_REPOS_FILE")
    only_repo = child.get("LOKAY2_REPO")
    only_issue = int(child["LOKAY2_ISSUE"]) if child.get("LOKAY2_ISSUE") else None
    repos = [repo for repo in load_repos(Path(repos_file) if repos_file else None)
             if not only_repo or repo["name"] == only_repo]
    blocked = []

    def idle():
        if blocked:
            name, issue, saved = max(blocked, key=lambda row: row[2].get("failures", 0))
            return {"result": "idle", "reason": "idle_backoff", "repo": name, "issue": issue,
                    "issue_since": saved.get("issue_since"), "failures": saved.get("failures", 0),
                    "last_error": saved.get("reason") or saved.get("last_error")}
        return {"result": "idle", "reason": "no_work"}

    def choose(repo):
        has_prs = False
        for turn in ("pr", "issue"):
            if turn == "issue" and has_prs:
                break
            check_deadline()
            name = repo["name"]
            if turn == "pr":
                code, out, err = _gh([
                    "pr", "list", "--repo", name, "--state", "open", "--limit", "1000000",
                    "--json", "number,headRefName,headRefOid",
                ])
                if code != 0:
                    raise RuntimeError(err.strip() or "pr list failed")
                prs = [row for row in json.loads(out or "[]") if row["headRefName"].startswith("lokay/")]
                has_prs = has_prs or bool(prs)
                prs = [row for row in prs if row["headRefName"][6:].isdecimal()
                       and (only_issue is None or int(row["headRefName"][6:]) == only_issue)]
                ready = []
                for row in prs:
                    number = int(row["headRefName"][6:])
                    saved = state_read(name, number)
                    if saved.get("retry_at", 0) > time.time():
                        blocked.append((name, number, saved))
                    else:
                        ready.append(row)
                if not ready:
                    continue
            if turn == "pr":
                target = min(ready, key=lambda row: (
                    state_read(name, int(row["headRefName"][6:])).get("last_attempt", 0), row["number"]))
                number = int(target["headRefName"][6:])
            else:
                issues = [row for row in open_issues(name) if is_task(row)
                          and (only_issue is None or int(row["number"]) == only_issue)]
                target = next((row for row in issues
                               if state_read(name, row["number"]).get("retry_at", 0) <= time.time()
                               and open_pr_for(name, f"lokay/{row['number']}") is None), None)
                if target is None:
                    for row in issues:
                        saved = state_read(name, row["number"])
                        if saved.get("failures", 0):
                            blocked.append((name, row["number"], saved))
                    continue
                number = target["number"]
            held = acquire(name.split("/")[0], f"{name}/wt-{number}")
            if held["result"] != "held":
                if turn == "pr":
                    blocked.extend((name, int(row["headRefName"][6:]),
                                    state_read(name, int(row["headRefName"][6:]))) for row in ready)
                continue
            chosen = None
            try:
                repo_attempt(name, time.time())
                if turn == "pr":
                    pr = target
                    issue = int(pr["headRefName"][6:])
                    saved_node = state_read(name, issue).get("node")
                    node = saved_node if saved_node in ("plan", "build", "check", "fix", "merge") else "check"
                    state_update(name, issue, node=node, branch=pr["headRefName"], pr=pr["number"],
                                 result="running", reason=None, last_attempt=time.time())
                    chosen = {"result": "picked", "repo": name, "issue": issue,
                              "node": node, "pr": pr["number"], "held": held}
                    return chosen
                issue = target
                saved = state_read(name, issue["number"])
                branch = f"lokay/{issue['number']}"
                chosen = {
                    "result": "picked",
                    "repo": name,
                    "issue": issue["number"],
                    "node": saved.get("node") or "plan",
                    "pr": None,
                    "held": held,
                }
                state_update(name, issue["number"], node=chosen["node"], branch=branch, pr=chosen["pr"],
                             result="running", reason=None, last_attempt=time.time())
            except BaseException:
                chosen = None
                raise
            finally:
                if chosen is None:
                    release(held)
            return chosen
        return None

    from lokay.store import main_status

    statuses = main_status()
    for repo in sorted(repos, key=lambda row: (repo_last_attempt(row["name"]), row["name"])):
        check_deadline()
        name = repo["name"]
        status = statuses.get(name, {})
        number = status.get("issue")
        if status.get("status") != "red" or not number or (only_issue is not None and only_issue != number):
            chosen = choose(repo)
            if chosen is not None:
                return chosen
            continue
        held = acquire(name.split("/")[0], f"{name}/wt-{number}")
        if held["result"] != "held":
            continue
        try:
            repo_attempt(name, time.time())
            branch = f"lokay/{number}"
            pr = open_pr_for(name, branch)
            saved = state_read(name, number)
            node = saved.get("node") or ("check" if pr else "plan")
            state_update(name, number, _event={"action": "red_main", "outcome": {"pr": pr, "status": status}},
                         branch=branch, pr=pr["number"] if pr else None, last_attempt=time.time())
            return {"result": "picked", "repo": name, "issue": number, "node": node,
                    "pr": pr["number"] if pr else None, "held": held}
        except BaseException:
            release(held)
            raise
    return idle()


def refresh_body(repo: str, issue: int) -> dict:
    from lokay.build import pr_body
    from lokay.gh import pr_set_body

    config = next(row for row in load_repos() if row["name"] == repo)
    root = Path(os.path.expanduser(config["clone_path"]))
    worktree = root.parent / f"{root.name}-wt-{issue}"
    pr = open_pr_for(repo, f"lokay/{issue}")
    if not pr:
        raise RuntimeError(f"open PR missing for {repo} lokay/{issue}")
    body = pr_body(worktree, run_dir(repo, issue) / "plan.md",
                   state_read(repo, issue).get("pi_response") or "")
    saved = state_read(repo, issue)
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
    import json
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
            return _tick()
        except TickExpired:
            return 0
        finally:
            tick_deadline.reset(token)
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def _tick() -> int:
    import sys

    outcome = pick()
    if outcome["result"] == "idle":
        from lokay.observe import current

        current(result="idle", idle_reason=outcome["reason"],
                **{key: value for key, value in outcome.items()
                   if key in ("repo", "issue", "issue_since", "failures", "last_error")})
        extra = outcome.get("failed") or ""
        print(f"idle {outcome['reason']} {extra}".rstrip(), file=sys.stderr)
        return 0
    try:
        print(dumps({k: v for k, v in outcome.items() if k != "held"}, separators=(",", ":")))
        if outcome.get("node") in ("plan", "build"):
            print(dumps(advance(outcome), separators=(",", ":")))
        elif outcome.get("node") in ("check", "fix", "merge"):
            print(dumps(resume(outcome), separators=(",", ":")))
    finally:
        release(outcome["held"])
    return 0


def _retry(picked: dict, node: str, action, expected: str | None = None, *, plan_branch: bool = False):
    repo, issue = picked["repo"], picked["issue"]
    state_update(repo, issue, node=node)
    try:
        check_deadline()
        outcome = action()
        if expected is None or outcome.get("result") == expected:
            state_update(repo, issue, _event={"action": "retry_succeeded",
                                             "outcome": {"result": outcome.get("result")} if isinstance(outcome, dict) else {}})
            return outcome
        reason = outcome.get("reason") or outcome.get("error") or str(outcome)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
    needs_help(picked, reason, plan_branch=plan_branch)
    raise RetryLater(reason)


@guarded_step
def advance(picked: dict) -> dict:
    prepared = _prepare(picked)
    if isinstance(prepared, dict):
        return prepared
    worktree, branch, sha, tests, plan_rounds = prepared
    return _finish(picked, worktree, branch, sha, tests, plan_rounds)


def replan_prompt(picked: dict, reason: str, findings: list, head: str | None = None) -> str:
    from lokay.plan import prompt_for

    repo, issue = picked["repo"], picked["issue"]
    saved = state_read(repo, issue)
    if head is None:
        configured = next((row for row in load_repos() if row["name"] == repo), None)
        if configured:
            root = Path(os.path.expanduser(configured["clone_path"]))
            worktree = root.parent / f"{root.name}-wt-{issue}"
            if worktree.exists():
                from lokay.git import _git

                code, out, err = _git(worktree, ["rev-parse", "HEAD"])
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


def _plan_graph(picked: dict, art: Path, title: str, body: str | None) -> int:
    from lokay import plan
    from lokay.decide import decide

    repo, issue = picked["repo"], picked["issue"]
    store.ensure_directory(art.parent)
    while True:
        saved = state_read(repo, issue)
        context = saved.get("plan_prompt") or plan.prompt_for(title, body)
        branches = saved.get("plan_branches") or {}
        synthesis = saved.get("plan_synthesis") or {}
        rounds = saved.get("plan_rounds", 0)
        paths = {}
        for perspective in plan.PERSPECTIVES:
            branch_art = art.parent / "plans" / f"{perspective}.md"
            store.ensure_directory(branch_art.parent)
            branch = branches.setdefault(perspective, {
                "phase": "write", "rounds": 0, "accepted_sha": None,
                "prompt": context, "fingerprint": None,
            })
            accepted = (plan.valid_plan(branch_art) and branch.get("accepted_sha") ==
                        hashlib.sha256(branch_art.read_bytes()).hexdigest())
            if accepted:
                paths[perspective] = branch_art
                continue
            if branch["phase"] == "failed":
                continue
            if branch["phase"] == "accepted":
                branch.update(phase="write", accepted_sha=None)
            while True:
                state_update(repo, issue, node="plan", plan_phase="write", plan_prompt=context,
                             plan_branches=branches, plan_synthesis=synthesis)
                check_deadline()
                def written():
                    nonlocal rounds
                    rounds += 1
                    branch.update(phase="check", rounds=branch["rounds"] + 1)
                    state_update(repo, issue, plan_branches=branches, plan_rounds=rounds)
                    rounds_append(repo, issue, f"Plan {perspective} {branch['rounds']}: write")
                try:
                    outcome = _retry(picked, "plan", lambda: plan.plan_one(
                        perspective, branch["prompt"], branch_art,
                        phase=branch["phase"], on_written=written), "done", plan_branch=True)
                except RetryLater as exc:
                    branch.update(phase="failed", reason=str(exc), accepted_sha=None)
                    state_update(repo, issue, plan_branches=branches)
                    rounds_append(repo, issue, f"Plan {perspective}: failed: {exc}")
                    break
                rounds_append(repo, issue, f"Plan {perspective} {branch['rounds']}: Decision {outcome['next']}")
                if outcome["next"] == "ok":
                    branch.update(phase="accepted", accepted_sha=hashlib.sha256(branch_art.read_bytes()).hexdigest())
                    paths[perspective] = branch_art
                    state_update(repo, issue, plan_branches=branches)
                    break
                fingerprint = hashlib.sha256(dumps(outcome["uwagi"], sort_keys=True).encode()).hexdigest()
                branch.update(phase="write", fingerprint=fingerprint,
                              prompt=context + "\n\nPrevious branch plan:\n" + branch_art.read_text()
                              + "\n\nUwagi:\n" + dumps(outcome["uwagi"], ensure_ascii=False))
                state_update(repo, issue, plan_branches=branches)
                retry_sleep(20)
        if not paths:
            reasons = [{"perspective": name, "reason": branch.get("reason")} for name, branch in branches.items()]
            prompt = replan_prompt(picked, "Wszystkie 3 plany nieudane", reasons)
            state_update(repo, issue, plan_branches={}, plan_synthesis={}, plan_prompt=prompt,
                         plan_phase="write", plan_accepted_sha=None)
            retry_sleep(20)
            continue
        synthesis = synthesis or {"phase": "write", "fingerprint": None, "uwagi": [], "rounds": 0}
        fresh = False
        while True:
            state_update(repo, issue, node="plan", plan_phase="write", plan_synthesis=synthesis)
            check_deadline()
            if synthesis["phase"] == "write" or not plan.valid_plan(art):
                failed = {name: branch.get("reason") for name, branch in branches.items() if branch["phase"] == "failed"}
                prompt = context + "\n\nFailed branches:\n" + dumps(failed, ensure_ascii=False)
                prompt += "\n\nUwagi:\n" + dumps(synthesis["uwagi"], ensure_ascii=False)
                _retry(picked, "plan", lambda: plan.synthesize(paths, prompt, art), "done")
                rounds += 1
                synthesis.update(phase="check", rounds=synthesis["rounds"] + 1)
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
                             plan_synthesis=synthesis,
                             plan_accepted_sha=hashlib.sha256(art.read_bytes()).hexdigest(),
                             plan_notes=outcome.get("notes", []))
                return rounds
            fingerprint = hashlib.sha256(dumps(outcome["uwagi"], sort_keys=True).encode()).hexdigest()
            if synthesis["fingerprint"] == fingerprint:
                prompt = replan_prompt(picked, "Repeated synthesis rejection", outcome["uwagi"])
                state_update(repo, issue, plan_branches={}, plan_synthesis={}, plan_prompt=prompt,
                             plan_phase="write", plan_accepted_sha=None)
                fresh = True
            else:
                synthesis.update(phase="write", fingerprint=fingerprint, uwagi=outcome["uwagi"])
                state_update(repo, issue, plan_synthesis=synthesis)
            retry_sleep(20)
            if fresh:
                break


def _prepare(picked: dict) -> tuple | dict:
    from lokay.build import build_code, build_publish
    from lokay.gh import _gh
    from lokay.git import worktree_add

    from lokay import plan

    saved = state_read(picked["repo"], picked["issue"])
    if "issue_title" not in saved or "issue_body" not in saved:
        code, raw, err = _gh(["issue", "view", str(picked["issue"]), "--repo", picked["repo"], "--json", "title,body"])
        if code != 0:
            raise RuntimeError(err.strip() or "issue view failed")
        loaded = json.loads(raw)
        if not isinstance(loaded.get("title"), str) or not loaded["title"].strip():
            raise RuntimeError("issue title is missing or invalid")
        body = loaded.get("body")
        if body is not None and not isinstance(body, str):
            raise RuntimeError("issue body is invalid")
        state_update(picked["repo"], picked["issue"], issue_title=loaded["title"], issue_body=body)
        saved = state_read(picked["repo"], picked["issue"])
    title, body = saved["issue_title"], saved["issue_body"]
    repo = next(row for row in load_repos() if row["name"] == picked["repo"])
    root = Path(os.path.expanduser(repo["clone_path"]))
    worktree = root.parent / f"{root.name}-wt-{picked['issue']}"
    from lokay.build import _git as build_git

    if saved.get("node", picked["node"]) == "plan" and worktree.exists() and not saved.get("previous_head"):
        state_update(picked["repo"], picked["issue"], previous_head=build_git(worktree, ["rev-parse", "HEAD"]))
    art = run_dir(picked["repo"], picked["issue"]) / "plan.md"
    plan_rounds = saved.get("plan_rounds", 0)
    accepted = (plan.valid_plan(art) and saved.get("plan_accepted_sha") ==
                hashlib.sha256(art.read_bytes()).hexdigest())
    if saved.get("node", picked["node"]) == "plan" or saved.get("plan_phase") or not accepted:
        plan_rounds = _plan_graph(picked, art, title, body)
    branch = f"lokay/{picked['issue']}"
    check_deadline()
    if not worktree.exists():
        _retry(picked, "build", lambda: worktree_add(root, branch, worktree), "added")
    plan_text = art.read_text()
    state_update(picked["repo"], picked["issue"], node="build", branch=branch)
    from lokay.setup import prepare_dependencies

    prepare_dependencies(worktree, repo, int(picked["issue"]))
    saved = state_read(picked["repo"], picked["issue"])
    build_note = saved.get("build_note")
    if saved.get("plan_notes"):
        build_note = (build_note or "") + "\n\nNon-blocking plan notes:\n" + dumps(saved["plan_notes"])
    check_deadline()
    built = build_code(worktree, plan_text, title, body, dict(os.environ), expected_branch=branch,
                       clone_path=root, previous_head=state_read(picked["repo"], picked["issue"]).get("previous_head"),
                       **({"build_note": build_note} if build_note else {}))
    if built.get("result") == "no_changes" or built.get("reason") == "no_changes":
        pr = open_pr_for(picked["repo"], branch)
        if pr:
            build_git(worktree, ["fetch", "origin", "main"])
            if int(build_git(worktree, ["rev-list", "--count", "origin/main..HEAD"])) > 0:
                rounds_append(picked["repo"], picked["issue"],
                              "no_changes: fix already on branch, checking existing PR")
                built = {**built, "result": "done", "reason": None,
                         "artifact": build_git(worktree, ["rev-parse", "HEAD"])}
        if built.get("result") == "no_changes":
            built = {**built, "result": "failed", "reason": "no_changes"}
    if built.get("result") == "failed":
        reason = built.get("reason") or "build failed"
        explanation = built.get("explanation") or built.get("artifact") or ""
        rounds_append(picked["repo"], picked["issue"], f"Build → Plan: {reason}")
        state_update(picked["repo"], picked["issue"], _event={"action": "build_complete", "outcome": built},
                     plan_prompt=replan_prompt(picked, f"Uwagi (Build): {reason}: {explanation}", [built],
                                               build_git(worktree, ["rev-parse", "HEAD"]) if worktree.exists() else None))
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
    repo, issue = picked["repo"], picked["issue"]
    saved = state_read(repo, issue)
    event = {"ts": time.time(), "fields": {}, "action": "needs_help",
             "outcome": {"reason": reason}, "plan_branch": plan_branch}
    derived = step(saved, event)
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


def fix_to_build(picked: dict, worktree: Path) -> dict | None:
    from lokay.git import _git
    from lokay.scope import is_test

    saved = state_read(picked["repo"], picked["issue"])
    ci = saved.get("local_ci") or {}
    code, head, err = _git(worktree, ["rev-parse", "HEAD"])
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
    code, added, err = _git(worktree, ["diff", "--name-status", "--diff-filter=A", "origin/main...HEAD"])
    if code != 0:
        raise RuntimeError(err or "added test diff failed")
    added_tests = {line.split("\t", 1)[1] for line in added.splitlines()
                   if "\t" in line and is_test(line.split("\t", 1)[1])}
    code, tracked, err = _git(worktree, ["ls-files"])
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
        # Package-local pytest paths must identify one file, not an existing namesake.
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


def pushed_pr(repo: str, branch: str, sha: str) -> dict | None:
    for attempt in range(6):
        check_deadline()
        pr = open_pr_for(repo, branch)
        if pr and pr.get("headRefOid") == sha:
            return pr
        if attempt < 5:
            retry_sleep(5)
    return None


@guarded_step
def resume(picked: dict) -> dict:
    from lokay.git import _git

    repo = next(row for row in load_repos() if row["name"] == picked["repo"])
    root = Path(os.path.expanduser(repo["clone_path"]))
    worktree = root.parent / f"{root.name}-wt-{picked['issue']}"
    branch = f"lokay/{picked['issue']}"
    try:
        pr = open_pr_for(picked["repo"], branch)
    except Exception as exc:
        return needs_help(picked, f"resume PR: {type(exc).__name__}: {exc}")
    if not pr or not pr.get("headRefOid"):
        return needs_help(picked, "resume PR missing or missing SHA")
    sha = pr["headRefOid"]
    state_update(picked["repo"], picked["issue"], pr=pr["number"])
    # open_pr_for filters by branch; its contract returns number and SHA only.
    if pr.get("headRefName", branch) != branch or (picked.get("pr") and picked["pr"] != pr["number"]):
        return needs_help(picked, "PR branch or number mismatch", sha)
    code, out, err = _git(worktree, ["branch", "--show-current"]) if worktree.is_dir() else (1, "", "missing worktree")
    if code != 0 or out.strip() != branch:
        def restore():
            commands = [["fetch", "origin", branch]]
            if worktree.exists():
                # Keep the old branch, commits and dirty files in a sibling worktree.
                backup = worktree.with_name(f"{worktree.name}-recovery-{time.time_ns()}")
                commands.append(["worktree", "move", str(worktree), str(backup)])
            else:
                commands.append(["worktree", "prune"])
            for args in commands:
                status, output, error = _git(root, args)
                if status != 0:
                    raise RuntimeError(error or output)
            exists, _, _ = _git(root, ["show-ref", "--verify", f"refs/heads/{branch}"])
            args = (["worktree", "add", str(worktree), branch] if exists == 0 else
                    ["worktree", "add", "-b", branch, str(worktree), f"origin/{branch}"])
            status, output, error = _git(root, args)
            if status != 0:
                raise RuntimeError(error or output)
            state_update(picked["repo"], picked["issue"], node="check", verdict=None, local_ci=None)
            rounds_append(picked["repo"], picked["issue"], "Worktree restored → Check")
        _retry(picked, "check", restore)
    from lokay.build import tidy_and_commit
    from lokay.fix import fix_publish

    tidy_and_commit(worktree, "lokay resume")
    code, out, err = _git(worktree, ["fetch", "origin", branch])
    if code != 0:
        return needs_help(picked, f"resume fetch: {err.strip() or out.strip()}", sha)
    code, out, err = _git(worktree, ["rev-parse", "HEAD"])
    if code != 0:
        return needs_help(picked, f"resume HEAD: {err.strip() or out.strip()}", sha)
    local = out.strip()
    if local != sha:
        ahead, out, err = _git(worktree, ["merge-base", "--is-ancestor", sha, local])
        if ahead not in (0, 1):
            return needs_help(picked, f"resume ancestry: {err.strip() or out.strip()}", sha)
        behind = 1
        if ahead != 0:
            behind, out, err = _git(worktree, ["merge-base", "--is-ancestor", local, sha])
            if behind not in (0, 1):
                return needs_help(picked, f"resume ancestry: {err.strip() or out.strip()}", sha)
            code, out, err = _git(worktree, ["merge", "--ff-only" if behind == 0 else "--no-edit", f"origin/{branch}"])
            if code != 0:
                reason = "sha diverged: conflict" if behind != 0 else f"resume ff: {err.strip() or out.strip()}"
                return needs_help(picked, reason, sha)
        if behind != 0:
            published = fix_step(picked, "fix_publish", lambda: fix_publish(worktree, branch, sha), sha)
            if published.get("result") != "pushed":
                if published.get("result") == "failed":
                    return published
                return needs_help(picked, f"fix_publish: {published}", sha)
            code, out, err = _git(worktree, ["rev-parse", "HEAD"])
            pr = pushed_pr(picked["repo"], branch, out.strip()) if code == 0 else None
            if code != 0 or not pr:
                return needs_help(picked, "sha mismatch after push", sha)
            sha = out.strip()
            _retry(picked, "fix", lambda: refresh_body(picked["repo"], int(picked["issue"])), "updated")
    code, out, err = _git(worktree, ["rev-parse", "HEAD"])
    if code != 0 or out.strip() != sha:
        return needs_help(picked, f"sha mismatch: {err.strip() or out.strip()}", sha)
    saved = state_read(picked["repo"], picked["issue"])
    if saved.get("sha") != sha or (saved.get("verdict") or {}).get("sha") != sha:
        state_update(picked["repo"], picked["issue"], node="check", verdict=None, fix_fingerprint=None)
    state_update(picked["repo"], picked["issue"], sha=sha)
    return _finish(picked, worktree, branch, sha, repo.get("test") or [])


def finding_summary(raw: dict) -> dict:
    item = parse_finding(raw)
    return {"pytanie": item.lens if "pytanie" in raw else raw.get("warstwa", ""),
            "plik": item.plik if isinstance(item, Finding) else "",
            "linie": [item.linia_od if isinstance(item, Finding) and "linia_od" in raw else None,
                      item.linia_do if isinstance(item, Finding) and "linia_do" in raw else None],
            "zmiana": item.zmiana if isinstance(item, Finding) else "",
            "uzasadnienie": (raw.get("uzasadnienie") or raw.get("log") or "")[:300]}


def finding_fingerprint(raw: dict) -> list:
    item = parse_finding(raw)
    return [item.plik if isinstance(item, Finding) else None,
            item.lens if "pytanie" in raw else raw.get("warstwa"),
            item.zmiana if isinstance(item, Finding) and "zmiana" in raw else None]


def finding_key(raw: dict) -> tuple:
    item = parse_finding(raw)
    if not isinstance(item, Finding):
        return ("", "", "", "")
    return (item.plik, item.linia_od if "linia_od" in raw else "",
            item.linia_do if "linia_do" in raw else "", item.zmiana)


def dismissed_key(row: dict) -> list:
    item = parse_finding(row)
    if not isinstance(item, Finding) and not item.pytanie:
        return [row.get("warstwa"), row.get("log")]
    return [item.plik if isinstance(item, Finding) else None,
            item.linia_od if isinstance(item, Finding) and "linia_od" in row else None,
            item.linia_do if isinstance(item, Finding) and "linia_do" in row else None,
            item.lens if "pytanie" in row else None]


def _finish(picked: dict, worktree: Path, branch: str, sha: str, tests: list, plan_rounds: int = 1) -> dict:
    from lokay.check import QUESTIONS, aggregate, check_state, decide_batches, hunks
    from lokay.main_guard import local_baseline, run_repo_tests
    from lokay.checks import CheckInput, run_checks
    from lokay.decide import decide
    from lokay.fix import fix_code, fix_publish
    from lokay.git import _git
    from lokay.gh import _gh, open_pr_for, pr_checks, check_comment
    from lokay.merge import merge_sha
    from lokay.run import run_process

    repo = next(row for row in load_repos() if row["name"] == picked["repo"])
    clone_path = Path(os.path.expanduser(repo["clone_path"]))
    saved = state_read(picked["repo"], picked["issue"])
    rounds = saved.get("check_rounds", 0)
    verdict = saved.get("verdict")
    # Revalidate Merge on a new tick; Fix keeps its SHA-bound findings.
    pending = "check" if saved.get("node") == "merge" else saved.get("node")

    def sync_head():
        for args in (["fetch", "origin", branch], ["merge", "--ff-only", f"origin/{branch}"]):
            code, out, err = _git(worktree, args)
            if code != 0:
                raise RuntimeError(err or out)

    def sync_main():
        code, out, err = _git(worktree, ["fetch", "origin", "main"])
        if code != 0:
            raise RuntimeError(err or out)
        code, out, err = _git(worktree, ["diff", "--name-only", "--diff-filter=U"])
        if code != 0:
            raise RuntimeError(err or out)
        if out.strip():
            return out.splitlines()
        code, out, err = _git(worktree, ["merge", "--no-edit", "origin/main"])
        if code != 0:
            conflict_code, files, conflict_err = _git(worktree, ["diff", "--name-only", "--diff-filter=U"])
            if conflict_code == 0 and files.strip():
                return files.splitlines()
            raise RuntimeError(conflict_err or err or out)
        return []

    while True:
        check_deadline()
        if pending == "merge" and verdict and verdict.get("sha") == sha:
            pr = _retry(picked, "merge", lambda: open_pr_for(picked["repo"], branch))
            if pr and pr.get("headRefOid") == sha:
                state_update(picked["repo"], picked["issue"], node="merge", pr=pr["number"])
                try:
                    merged = merge_sha(
                        picked["repo"], pr["number"], sha, verdict, worktree,
                        picked.get("held"), picked["repo"].split("/")[0], int(picked["issue"]),
                        {"plan_rounds": plan_rounds, "check_rounds": rounds},
                        clone_path=clone_path,
                    )
                except Exception as exc:
                    raise RuntimeError(
                        f"merge repo={picked['repo']} pr={pr['number']} sha={sha}: "
                        f"{type(exc).__name__}: {exc}"
                    ) from exc
                state_update(picked["repo"], picked["issue"], _event={"action": "merge_complete", "outcome": merged})
                if merged["result"] == "merged":
                    state_update(picked["repo"], picked["issue"], sha=merged["merge_sha"])
                    rounds_append(picked["repo"], picked["issue"], f"Merge: sha={merged['merge_sha']}")
                    return merged
                rounds_append(picked["repo"], picked["issue"], f"Merge: retry, result={merged['result']}")
                if merged["result"] != "conflict":
                    state_update(picked["repo"], picked["issue"], node="check", verdict=None)
            state_update(picked["repo"], picked["issue"], node="check", verdict=None)
            if pr and pr.get("headRefOid") and pr["headRefOid"] != sha:
                _retry(picked, "check", sync_head)
                sha = pr["headRefOid"]
            pending = "check"
        state_update(picked["repo"], picked["issue"], node="fix" if pending == "fix" else "check", sha=sha)
        if pending != "fix":
            conflicts = _retry(picked, "check", sync_main)
            if conflicts:
                verdict = {"result": "fix", "sha": sha, "uwagi": [
                    {"pytanie": "conflict", "plik": file, "log": "Resolve the merge with origin/main."}
                    for file in conflicts
                ]}
                pending = "fix"
                state_update(picked["repo"], picked["issue"], _event={"action": "verdict", "outcome": verdict},
                             verdict=verdict)
                rounds_append(picked["repo"], picked["issue"], "Check: conflict, files=" + ", ".join(conflicts))
                pr = _retry(picked, "check", lambda: open_pr_for(picked["repo"], branch))
                if pr:
                    _retry(picked, "check", lambda: check_comment(picked["repo"], pr["number"],
                           rounds + 1, verdict, {"result": "conflict"}))
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
                    raise RuntimeError(f"main synchronization publish failed: {pushed}")
                sha = pushed["sha"]
                if not pushed_pr(picked["repo"], branch, sha):
                    return needs_help(picked, "sha mismatch after push", sha)
                _retry(picked, "check", lambda: refresh_body(picked["repo"], int(picked["issue"])), "updated")
                state_update(picked["repo"], picked["issue"], sha=sha, verdict=None)
        def read_diff():
            diff = command(worktree, ["diff", "origin/main...HEAD"])
            if diff.returncode != 0:
                raise RuntimeError(diff.stderr or "diff failed")
            return diff
        active_node = "fix" if pending == "fix" else "check"
        diff = _retry(picked, active_node, read_diff)
        def read_head():
            code, out, err = _git(worktree, ["rev-parse", "HEAD"])
            if code != 0:
                raise RuntimeError(err or "HEAD lookup failed")
            return out.strip()
        head = _retry(picked, active_node, read_head)
        diff_fingerprint = hashlib.sha256((diff.stdout or "").encode()).hexdigest()
        if pending == "fix" and verdict:
            uwagi = verdict["uwagi"]
            if not uwagi:
                state_update(picked["repo"], picked["issue"], node="check", verdict=None,
                             local_ci=None, test_log=None, fix_fingerprint=None, fix_reason=None,
                             result="check")
                return {"result": "check", "sha": sha}
            findings = {
                dumps([row["name"], row.get("location")] if "name" in row else
                           finding_fingerprint(row))
                for row in uwagi
            }
            fingerprint = hashlib.sha256(dumps(sorted(findings)).encode()).hexdigest()
            # Hunk content is evidence independent of shifted line numbers.
            hunk_text = "\n".join(line for line in (diff.stdout or "").splitlines()
                                  if not line.startswith(("@@", "index ")))
            hunk_fingerprint = hashlib.sha256(hunk_text.encode()).hexdigest()
            saved = state_read(picked["repo"], picked["issue"])
            counts = (saved.get("fix_counts", []) + [len(uwagi)])[-3:]
            history = saved.get("fix_history", []) + [uwagi]
            state_update(picked["repo"], picked["issue"], fix_counts=counts, fix_history=history)
            rounds_append(picked["repo"], picked["issue"],
                          f"Fix progress: findings={fingerprint}, hunk={hunk_fingerprint}, "
                          f"diff={diff_fingerprint}, counts={counts}")
            stalled = (saved.get("diff_fingerprint") == diff_fingerprint
                       or (saved.get("fix_fingerprint") == fingerprint
                           and saved.get("fix_hunk_fingerprint") == hunk_fingerprint)
                       or (len(counts) == 3 and min(counts[1:]) >= counts[0]))
            test_log = (saved.get("test_log") or "") if (saved.get("local_ci") or {}).get("sha") == head else ""
            art = run_dir(picked["repo"], picked["issue"]) / "plan.md"
            ci = saved.get("local_ci") or {}
            lens_kinds = {path.stem.removeprefix("check_") for path in QUESTIONS.glob("check_*.json")}
            can_dispute = (head == sha == verdict.get("sha") == ci.get("sha")
                           and ci.get("result") == "green"
                           and ci.get("ci") in ("green", "no_ci")
                           and all(row.get("warstwa") == "scope"
                                   or (parse_finding(row).lens in lens_kinds and "warstwa" not in row)
                                   for row in uwagi))
            if stalled and not can_dispute:
                redirected = fix_to_build(picked, worktree)
                if redirected:
                    return redirected
                rounds_append(picked["repo"], picked["issue"], "Fix → Plan: no progress, findings=" + fingerprint)
                title, body = saved.get("issue_title"), saved.get("issue_body")
                if not title:
                    def read_issue():
                        code, raw, err = _gh(["issue", "view", str(picked["issue"]),
                                              "--repo", picked["repo"], "--json", "title,body"])
                        if code != 0:
                            raise RuntimeError(err or "issue view failed")
                        return json.loads(raw)
                    issue = _retry(picked, "plan", read_issue)
                    title, body = issue["title"], issue.get("body")
                state_update(picked["repo"], picked["issue"], issue_title=title, issue_body=body,
                             fix_counts=[], diff_fingerprint=None)
                prompt = replan_prompt(picked, "Fix made no progress; revise the plan.", uwagi, head)
                prompt += "\n\nTest log:\n" + test_log
                rounds_append(picked["repo"], picked["issue"], "Re-Plan test log:\n" + test_log)
                state_update(picked["repo"], picked["issue"], _event={"action": "replan"}, plan_prompt=prompt)
                prepared = _prepare({**picked, "node": "plan"})
                if isinstance(prepared, dict):
                    return prepared
                worktree, branch, sha, tests, plan_rounds = prepared
                pending = "check"
                continue
            prompt = (
                Path(__file__).resolve().parents[2].joinpath("prompts/fix.md").read_text()
                + "\n\nSHA:\n" + sha
                + "\n\nIssue:\n" + (saved.get("issue_title") or "")
                + "\n" + (saved.get("issue_body") or "")[:6000]
                + ("\n\nCI is red. Making CI green takes precedence over scope/alignment notes: "
                   "changes needed for CI to pass are in scope and must not be reverted."
                   if saved.get("ci") == "red" or (saved.get("local_ci") or {}).get("result") == "red"
                   else "")
                + "\n\nUwagi:\n" + dumps(uwagi)
                + "\n\nDiff:\n" + (diff.stdout or "")[:20000]
                + "\n\nTest log:\n" + test_log
                + "\n\nPlan:\n" + (art.read_text() if art.is_file() else "")
                + "\n\nPrevious failure:\n" + (saved.get("fix_reason") or "")
            )
            if stalled:
                prompt += ("\n\nThese findings repeat after previous fix attempts. "
                           "Either make a concrete change that resolves them, or, if a finding is wrong "
                           "or not actionable, make no commit and explain why in a '## Dispute' section.")
            from lokay.setup import prepare_dependencies

            prepare_dependencies(worktree, repo, int(picked["issue"]))
            def fix_action():
                outcome = fix_code(worktree, sha, prompt, dict(os.environ), clone_path=clone_path)
                if outcome.get("result") == "no_changes" or outcome.get("reason") == "no_changes":
                    response = outcome.get("pi_response") or outcome.get("explanation") or ""
                    state_update(picked["repo"], picked["issue"], pi_response=response)
                    if can_dispute:
                        justification = (response.split("## Dispute", 1)[1].strip()
                                         if "## Dispute" in response else response[-2000:])
                        upheld = {}
                        rejected = []
                        def category(row):
                            return parse_finding(row).lens or ("scope" if row.get("warstwa") == "scope" else "")

                        for kind in sorted({category(row) for row in uwagi}):
                            findings = [row for row in uwagi if category(row) == kind]
                            request = {
                                "questions": [{
                                    "id": "valid", "type": "bool",
                                    "instructions": "Given the developer's justification, the diff and the issue goal, "
                                                    "is this review finding still valid and actionable?",
                                    "options": {"true": "finding still valid, must be fixed", "false": "finding rejected"},
                                }],
                                "state": {"issue_title": saved.get("issue_title") or "",
                                          "issue_body": (saved.get("issue_body") or "")[:4000],
                                          "findings": findings, "justification": justification[:3000],
                                          "diff": (diff.stdout or "")[:20000]},
                            }
                            answer = _retry(picked, "check", lambda: decide(request))["valid"]
                            valid = answer["choice"] == "true"
                            probabilities = answer["probabilities"]
                            rounds_append(picked["repo"], picked["issue"],
                                          f"Dispute: {kind} {'upheld' if valid else 'rejected'} "
                                          f"(p={dumps(probabilities)})")
                            current = state_read(picked["repo"], picked["issue"])
                            check_history = current.get("check_history", [])
                            if check_history and check_history[-1]["sha"] == sha:
                                check_history[-1].setdefault("dispute", {})[kind] = "upheld" if valid else "rejected"
                                state_update(picked["repo"], picked["issue"], check_history=check_history)
                            if valid:
                                upheld[kind] = probabilities
                            else:
                                for row in findings:
                                    item = parse_finding(row)
                                    change = item.zmiana if isinstance(item, Finding) else ""
                                    rejected.append({**row, "zmiana": change + "\nDispute: " + justification})
                        if rejected:
                            current = state_read(picked["repo"], picked["issue"])
                            dismissed = current.get("dispute_dismissed") or {}
                            keys = dismissed.get("keys", []) if dismissed.get("sha") == sha else []
                            keys += [dismissed_key(row) for row in rejected]
                            state_update(picked["repo"], picked["issue"],
                                         check_notes=current.get("check_notes", []) + rejected,
                                         dispute_dismissed={"sha": sha, "keys": keys})
                            _retry(picked, "check", lambda: refresh_body(picked["repo"], int(picked["issue"])), "updated")
                        if not upheld:
                            return {"result": "done", "dispute_rejected": True}
                        remaining = [row for row in uwagi if category(row) in upheld]
                        retry_prompt = prompt.replace("\n\nUwagi:\n" + dumps(uwagi),
                                                      "\n\nUwagi:\n" + dumps(remaining))
                        retry_prompt += "\n\nThe finding was upheld after your dispute. Reason to treat it as valid: "
                        retry_prompt += dumps(upheld) + "; your dispute was: " + justification
                        retry_prompt += ". Make a concrete change.\nRemaining findings:\n"
                        retry_prompt += dumps(remaining)
                        outcome = fix_code(worktree, sha, retry_prompt, dict(os.environ), clone_path=clone_path)
                        state_update(picked["repo"], picked["issue"],
                                     pi_response=outcome.get("pi_response") or outcome.get("explanation") or "")
                    if outcome.get("result") == "no_changes" or outcome.get("reason") == "no_changes":
                        redirected = fix_to_build(picked, worktree)
                        if redirected:
                            return redirected
                return outcome
            fixed = fix_step(picked, "fix_code", fix_action, sha)
            if fixed.get("dispute_rejected"):
                verdict = {**verdict, "result": "merge", "uwagi": []}
                pending = "merge"
                state_update(picked["repo"], picked["issue"], _event={"action": "verdict", "outcome": verdict},
                             result="merge", verdict=verdict)
                continue
            if fixed.get("next") in ("build", "plan"):
                return fixed
            if fixed["result"] == "failed":
                return fixed
            state_update(picked["repo"], picked["issue"], pi_response=fixed.get("pi_response") or "")
            pushed = fix_step(picked, "fix_publish", lambda: fix_publish(worktree, branch, sha), sha)
            if pushed["result"] == "failed":
                return pushed
            if pushed["result"] == "remote_moved" and pushed.get("sha"):
                _retry(picked, "check", sync_head)
            previous_sha = sha
            sha = pushed["sha"]
            if sha != previous_sha and pushed["result"] == "pushed":
                def read_fix_subject():
                    code, subject, err = _git(worktree, ["log", "--format=%s", "origin/main..HEAD"])
                    if code != 0:
                        raise RuntimeError(err or "fix commit subject lookup failed")
                    return next(iter(subject.splitlines()), "")

                subject = _retry(picked, "fix", read_fix_subject)
                check_history = state_read(picked["repo"], picked["issue"]).get("check_history", [])
                if check_history and check_history[-1]["sha"] == previous_sha:
                    check_history[-1].update(fix_sha=sha, fix_commit_subject=subject)
                    state_update(picked["repo"], picked["issue"], check_history=check_history)
            if pushed["result"] == "pushed":
                if not pushed_pr(picked["repo"], branch, sha):
                    return needs_help(picked, "sha mismatch after push", sha)
                _retry(picked, "fix", lambda: refresh_body(picked["repo"], int(picked["issue"])), "updated")
            state_update(picked["repo"], picked["issue"], sha=sha, fix_reason=None, fix_fingerprint=fingerprint,
                         fix_hunk_fingerprint=hunk_fingerprint, diff_fingerprint=diff_fingerprint)
            rounds_append(picked["repo"], picked["issue"], f"Fix: sha={sha}")
            pending = "check"
            state_update(picked["repo"], picked["issue"], _event={"action": "fix_complete", "outcome": pushed})
            continue
        rows = hunks(diff.stdout or "")
        saved = state_read(picked["repo"], picked["issue"])
        from lokay.setup import prepare_dependencies

        state_update(picked["repo"], picked["issue"], local_ci=None, test_log=None, tested=False)
        setup = prepare_dependencies(worktree, repo, int(picked["issue"]))
        setup = setup if isinstance(setup, dict) else {}
        if setup.get("failed"):
            ci = {"sha": sha, "result": "red", "tested": False, "tested_cwds": [],
                  "failed": setup["failed"], "notes": [], "log": setup["log"]}
        else:
            ci = _retry(picked, "check", lambda: run_repo_tests(repo, sha, worktree))
            ci = {**ci, "log": setup.get("log", "") + "\n" + ci["log"]}
        if ci["result"] == "red" and not setup.get("failed"):
            ci = _retry(picked, "check", lambda: local_baseline(picked["repo"], clone_path, ci))
        ci = {**ci, "argv": list(tests)}
        state_update(picked["repo"], picked["issue"], local_ci=ci, test_log=ci["log"])
        if ci["notes"]:
            rounds_append(picked["repo"], picked["issue"], f"Check: sha={sha}, flaky=" + dumps(ci["notes"]))
        if tests and not ci.get("baseline"):
            tested_cwds = set(ci.get("tested_cwds") or [])
            for row in rows:
                directory = (Path(worktree) / row["plik"]).parent
                while directory != Path(worktree) and directory != directory.parent:
                    if (directory / "pyproject.toml").is_file():
                        if str(directory.resolve()) not in tested_cwds:
                            ci = {**ci, "result": "red", "failed": [*ci["failed"], {
                                "warstwa": "tests", "plik": row["plik"],
                                "log": f"no test command ran in changed package: {directory}",
                            }]}
                        break
                    directory = directory.parent
        state_update(picked["repo"], picked["issue"], tested=ci.get("tested", False))
        log = ci["log"]
        directory = run_dir(picked["repo"], picked["issue"])
        store.ensure_directory(directory)
        store.write_artifact(directory / f"check-{rounds + 1}-diff.patch", diff.stdout or "")
        store.write_artifact(directory / f"check-{rounds + 1}-test.log", log)
        pr = _retry(picked, "check", lambda: open_pr_for(picked["repo"], branch))
        if not pr:
            raise RuntimeError("PR missing during Check")
        remote = _retry(picked, "check", lambda: pr_checks(picked["repo"], pr["number"], sha))
        state_update(picked["repo"], picked["issue"], ci=remote["result"])
        if remote["result"] == "sha_moved":
            _retry(picked, "check", sync_head)
            sha = remote["sha"]
            pending = "check"
            continue
        if remote["result"] == "pending":
            state_update(picked["repo"], picked["issue"], node="check", result="pending", verdict=None)
            rounds_append(picked["repo"], picked["issue"], f"Check: sha={sha}, GitHub CI pending")
            _retry(picked, "check", lambda: check_comment(picked["repo"], pr["number"], rounds + 1,
                   {"result": "pending", "sha": sha, "uwagi": []}, remote))
            return {"result": "pending", "sha": sha}
        ci = {**ci, "failed": ci["failed"] + [
            {"warstwa": "GitHub CI", "plik": "", "check": name,
             "log": name + "\n" + (remote.get("failed_logs") or {}).get(name, name)}
            for name in remote.get("failed") or []
        ], "ci": remote["result"], "notes": [*ci["notes"], *(remote.get("notes") or [])],
            "result": "green" if ci["result"] == "green" and remote["result"] in ("green", "no_ci") else "red"}
        state_update(picked["repo"], picked["issue"], local_ci=ci)
        def read_stat():
            stat = command(worktree, ["diff", "--stat", "origin/main...HEAD"])
            if stat.returncode != 0:
                raise RuntimeError(stat.stderr or "diff stat failed")
            return stat.stdout or ""

        directory = run_dir(picked["repo"], picked["issue"])
        decision_state = check_state(directory, rounds + 1, diff.stdout or "",
                                     _retry(picked, "check", read_stat), ci,
                                     sha=sha, repo=picked["repo"], issue=picked["issue"],
                                     issue_title=(saved.get("issue_title") or "")[:4000],
                                     issue_body=(saved.get("issue_body") or "")[:4000],
                                     history=saved.get("check_history", [])[-5:])
        decisions = []
        kinds = tuple(p.stem.removeprefix("check_") for p in sorted(QUESTIONS.glob("check_*.json")))
        for kind in kinds:
            decision = decide_batches(kind, rows, {**decision_state, "kind": kind},
                                      lambda request: _retry(picked, "check", lambda: decide(request)))
            decision["sha"] = sha
            decisions.append(decision)
            rounds_append(picked["repo"], picked["issue"],
                          f"Check lens {kind}, round={rounds + 1}: next={decision['next']}, "
                          f"p={dumps(decision.get('probabilities', []))}")
        groups = {}
        for decision in decisions:
            for finding in decision["uwagi"]:
                key = finding_key(finding)
                groups.setdefault(key, []).append(finding)
        degenerate = {key for key, findings in groups.items()
                      if len({parse_finding(finding).lens or "" for finding in findings}) >= 5}
        check_notes = state_read(picked["repo"], picked["issue"]).get("check_notes", [])
        for key in sorted(degenerate, key=lambda row: tuple("" if value is None else str(value) for value in row)):
            findings = groups[key]
            categories = sorted({parse_finding(finding).lens or "" for finding in findings})
            for finding in findings:
                if finding not in check_notes:
                    check_notes.append(finding)
            file, first, last, change = key
            rounds_append(picked["repo"], picked["issue"],
                          f"Check degenerate answer: categories={','.join(categories)}, "
                          f"plik={file}, range={first}-{last}, zmiana={change}")
            import sys

            print(dumps({"event": "check_degenerate_answer", "categories": categories,
                              "plik": file, "linia_od": first, "linia_do": last, "zmiana": change}),
                  file=sys.stderr, flush=True)
        dismissed = state_read(picked["repo"], picked["issue"]).get("dispute_dismissed") or {}
        dismissed_keys = dismissed.get("keys", []) if dismissed.get("sha") == sha else []
        for decision in decisions:
            original = decision["uwagi"]
            decision["uwagi"] = [finding for finding in original
                                 if finding_key(finding)
                                 not in degenerate
                                 and dismissed_key(finding) not in dismissed_keys]
            if original and not decision["uwagi"] and not decision.get("replan"):
                decision["next"] = "ok"
        verdict = aggregate(sha, ci, decisions)
        from lokay.scope import code_scope_issue

        code, changed, err = _git(worktree, ["diff", "--name-only", "origin/main...HEAD"])
        if code != 0:
            raise RuntimeError(err or "scope diff failed")
        files = changed.splitlines()
        plan_path = run_dir(picked["repo"], picked["issue"]) / "plan.md"
        plan_text = plan_path.read_text() if plan_path.is_file() else ""
        scope = code_scope_issue(files, plan_text)
        if scope and dismissed_key(scope) not in dismissed_keys:
            verdict = {**verdict, "result": "plan" if verdict["result"] == "plan" else "fix", "uwagi": [*verdict.get("uwagi", []), scope]}
            rounds_append(picked["repo"], picked["issue"], "Check scope: " + scope["log"])
        check_input = CheckInput(
            repo=picked["repo"], issue=int(picked["issue"]), sha=sha,
            issue_title=saved.get("issue_title") or "", issue_body=saved.get("issue_body") or "",
            plan=plan_text, diff=diff.stdout or "", hunks=rows, ci=ci, worktree=worktree,
        )
        checks_verdict = run_checks(check_input)
        verdict.update(checks=checks_verdict["checks"], failed=checks_verdict["failed"])
        if checks_verdict["failed"]:
            verdict = {**verdict, "result": "fix", "uwagi": [*verdict["uwagi"], *checks_verdict["failed"]]}
        rounds += 1
        check_history = state_read(picked["repo"], picked["issue"]).get("check_history", []) + [{
            "round": rounds, "sha": sha,
            "findings": [finding_summary(row) for row in verdict.get("uwagi", [])],
            "fix_commit_subject": "", "dispute": {},
        }]
        state_update(
            picked["repo"], picked["issue"], node="check", sha=sha,
            check_rounds=rounds, result=verdict["result"], verdict=verdict, test_log=log,
            check_notes=check_notes, check_history=check_history,
        )
        counts = ", ".join(
            f"{kind}={len(decision['uwagi'])}"
            for kind, decision in zip(kinds, decisions)
        )
        rounds_append(
            picked["repo"], picked["issue"],
            f"Check {rounds}: sha={sha}, result={verdict['result']}, uwagi: {counts}, ci={ci['result']}, "
            + "checks=" + dumps(verdict["checks"]),
        )
        lens_notes = [parse_finding(note).lens for note in verdict.get("notes", []) if parse_finding(note).lens]
        if lens_notes:
            rounds_append(picked["repo"], picked["issue"], f"Check {rounds}: notes=" + ", ".join(lens_notes))
        _retry(picked, "check", lambda: check_comment(picked["repo"], pr["number"], rounds, verdict, ci))
        _retry(picked, "check", lambda: refresh_body(picked["repo"], int(picked["issue"])), "updated")
        pending = verdict["result"]
        if pending == "plan":
            findings = verdict["replan"] + verdict["uwagi"]
            reason = "\n".join(item["prompt"] for item in verdict["replan"])
            rounds_append(picked["repo"], picked["issue"], "Check → Plan: " + reason)
            prompt = replan_prompt(picked, reason, findings, head)
            state_update(picked["repo"], picked["issue"], _event={"action": "verdict", "outcome": verdict},
                         plan_prompt=prompt)
            prepared = _prepare({**picked, "node": "plan"})
            if isinstance(prepared, dict):
                return prepared
            worktree, branch, sha, tests, plan_rounds = prepared
            pending = "check"
            continue
        state_update(picked["repo"], picked["issue"], _event={"action": "verdict", "outcome": verdict})

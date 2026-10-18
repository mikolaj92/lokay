from __future__ import annotations

from copy import deepcopy

import json
import time
from pathlib import Path

from lokay import store
from lokay.store import rounds_append, run_dir, state_read, state_update
from lokay.types import (PLAN_RESET, Finding, parse_finding, to_dict, finding_summary,
                         finding_fingerprint, finding_key, dismissed_key)
from lokay.merge import merge_blocked


def sync_head(worktree, branch):
    from lokay.effects.git import git

    for args in (["fetch", "origin", branch], ["merge", "--ff-only", f"origin/{branch}"]):
        git(worktree, *args)


def conflict_fix(picked, sha, files, log):
    finding = {"result": "fix", "sha": sha, "uwagi": [
        {"pytanie": "conflict", "plik": file, "log": log} for file in files
    ]}
    if not finding["uwagi"]:
        raise RuntimeError("merge conflict without PR files")
    state_update(picked["repo"], picked["issue"],
                 _event={"action": "verdict", "outcome": finding},
                 verdict=finding, result="fix", sha=sha)
    return finding


def sync_main(worktree, base):
    from lokay.effects.git import git
    from lokay.effects.git import git_try

    git(worktree, "fetch", "origin", base)
    out = git(worktree, "diff", "--name-only", "--diff-filter=U")
    if out:
        return out.splitlines()
    code, out, err = git_try(worktree, "merge", "--no-edit", f"origin/{base}")
    if code != 0:
        conflict_code, files, conflict_err = git_try(worktree, "diff", "--name-only", "--diff-filter=U")
        if conflict_code == 0 and files.strip():
            return files.splitlines()
        raise RuntimeError(conflict_err or err or out)
    return []


def merge(picked, worktree, branch, sha, verdict, base, plan_rounds, rounds, clone_path, sync_head):
    from lokay.tick import _retry, open_pr_for
    from lokay.effects.git import BASE_BRANCHES
    from lokay.merge import merge_sha

    pr = _retry(picked, "merge", lambda: open_pr_for(picked["repo"], branch))
    if pr and pr.get("baseRefName"):
        base = pr["baseRefName"]
        BASE_BRANCHES[(worktree.resolve(), None)] = base
        BASE_BRANCHES[(worktree.resolve(), branch)] = base
    if pr and pr.get("headRefOid") == sha:
        state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "merge"}}, pr=pr["number"])
        try:
            merged = merge_sha(
                picked["repo"], pr["number"], sha, verdict, worktree,
                picked["repo"].split("/")[0], int(picked["issue"]),
                {"plan_rounds": plan_rounds, "check_rounds": rounds},
                clone_path=clone_path,
            )
        except Exception as exc:
            raise RuntimeError(
                f"merge repo={picked['repo']} pr={pr['number']} sha={sha}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        state_update(picked["repo"], picked["issue"], _event={"action": "merge_complete", "outcome": merged})
        if merged["result"] == "closed":
            return merged, base, sha, "merge", verdict
        if merged["result"] == "merged":
            state_update(picked["repo"], picked["issue"], sha=merged["merge_sha"])
            rounds_append(picked["repo"], picked["issue"], f"Merge: sha={merged['merge_sha']}")
            return merged, base, sha, "merge", verdict
        rounds_append(picked["repo"], picked["issue"], f"Merge: retry, result={merged['result']}")
        if merged["result"] in ("conflict", "merge_limit"):
            pending = "check"
            verdict = None
        else:
            state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "check"}}, verdict=None)
    state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "check"}}, verdict=None)
    if pr and pr.get("headRefOid") and pr["headRefOid"] != sha:
        _retry(picked, "check", sync_head)
        sha = pr["headRefOid"]
    pending = "check"
    return None, base, sha, pending, verdict


def local_checks(picked, worktree, repo, sha, clone_path, base, tests, rows):
    from lokay.tick import _retry, dumps
    from lokay.main_guard import local_baseline, run_repo_tests
    from lokay.check import hunk_finding
    from lokay.setup import prepare_dependencies

    state_update(picked["repo"], picked["issue"], local_ci=None, tested=False)
    setup = prepare_dependencies(worktree, repo, int(picked["issue"]))
    setup = setup if isinstance(setup, dict) else {}
    if setup.get("failed"):
        ci = {"sha": sha, "result": "red", "tested": False, "tested_cwds": [],
              "failed": setup["failed"], "notes": [], "log": setup["log"]}
    else:
        ci = _retry(picked, "check", lambda: run_repo_tests(repo, sha, worktree))
        ci = {**ci, "log": setup.get("log", "") + "\n" + ci["log"]}
    if ci["result"] == "red" and not setup.get("failed"):
        ci = _retry(picked, "check", lambda: local_baseline(picked["repo"], clone_path, ci, base=base))
    ci = {**ci, "argv": list(tests)}
    state_update(picked["repo"], picked["issue"], local_ci=ci)
    if ci["notes"]:
        rounds_append(picked["repo"], picked["issue"], f"Check: sha={sha}, flaky=" + dumps(ci["notes"]))
    if tests and not ci.get("baseline"):
        tested_cwds = set(ci.get("tested_cwds") or [])
        for row in rows:
            finding = hunk_finding(row)
            directory = (Path(worktree) / finding.plik).parent
            while directory != Path(worktree) and directory != directory.parent:
                if (directory / "pyproject.toml").is_file():
                    if str(directory.resolve()) not in tested_cwds:
                        ci = {**ci, "result": "red", "failed": [*ci["failed"], {
                            "warstwa": "tests", "plik": finding.plik,
                            "log": f"no test command ran in changed package: {directory}",
                        }]}
                    break
                directory = directory.parent
    state_update(picked["repo"], picked["issue"], tested=ci.get("tested", False))
    return ci


def remote_checks(picked, branch, sha):
    from lokay.tick import _retry, open_pr_for
    from lokay.effects.gh import pr_checks

    pr = _retry(picked, "check", lambda: open_pr_for(picked["repo"], branch))
    if not pr:
        raise RuntimeError("PR missing during Check")
    pr_number = pr["number"]
    remote = _retry(picked, "check", lambda: pr_checks(picked["repo"], pr_number, sha))
    state_update(picked["repo"], picked["issue"], ci=remote["result"])
    return pr_number, remote


def lenses(picked, worktree, base, sha, saved, diff, rows, ci, rounds):
    from lokay.tick import _retry, dumps
    from lokay.effects.git import git_try
    from lokay.check import QUESTIONS, check_state, classify_multilens, decide_batches, docs_only
    from lokay.checks import CheckInput, run_checks
    from lokay.effects.decide import decide

    def read_stat():
        code, out, err = git_try(worktree, "diff", "--stat", f"origin/{base}...HEAD", timeout=30)
        if code != 0:
            raise RuntimeError(err or "diff stat failed")
        return out

    plan_path = run_dir(picked["repo"], picked["issue"]) / "plan.md"
    plan_text = plan_path.read_text() if plan_path.is_file() else ""
    check_input = CheckInput(
        repo=picked["repo"], issue=int(picked["issue"]), sha=sha,
        issue_title=saved.get("issue_title") or "", issue_body=saved.get("issue_body") or "",
        plan=plan_text, diff=diff or "", hunks=rows, ci=ci, worktree=worktree,
    )
    check_results = run_checks(check_input)
    checks_failed = any(result.status == "fail" for result in check_results)
    directory = run_dir(picked["repo"], picked["issue"])
    decision_state = check_state(directory, rounds + 1, diff or "",
                                 _retry(picked, "check", read_stat), ci,
                                 sha=sha, repo=picked["repo"], issue=picked["issue"],
                                 issue_title=(saved.get("issue_title") or "")[:4000],
                                 issue_body=(saved.get("issue_body") or "")[:4000],
                                 history=saved.get("check_history", [])[-5:])
    decisions = []
    kinds = () if checks_failed else ("docs",) if docs_only(diff or "") else tuple(
        p.stem.removeprefix("check_") for p in sorted(QUESTIONS.glob("check_*.json"))
        if p.stem != "check_docs")
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
    multilens = {key for key, findings in groups.items()
                  if len({item.lens for finding in findings
                          if (item := parse_finding(finding)).lens}) >= 5}
    check_notes = state_read(picked["repo"], picked["issue"]).get("check_notes", [])
    history = saved.get("check_history", [])
    previous = history[-1] if history and history[-1].get("sha") != sha else {}
    previous_fingerprints = {tuple(finding_fingerprint(row)) for row in previous.get("findings", [])}
    amplified = []
    for key in sorted(multilens, key=lambda row: tuple("" if value is None else str(value) for value in row)):
        findings = groups[key]
        parsed = tuple(map(parse_finding, findings))
        categories = sorted({item.lens or "" for item in parsed})
        file_lines = None
        if isinstance(parsed[0], Finding):
            try:
                file_lines = len((worktree / parsed[0].plik).read_text().splitlines())
            except (OSError, UnicodeError):
                pass
        repeated = any(tuple(finding_fingerprint(row)) in previous_fingerprints for row in findings)
        finding = classify_multilens(parsed, file_lines=file_lines, repeated=repeated)
        if finding is not None:
            amplified.append(to_dict(finding))
            continue
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
                             not in multilens
                             and dismissed_key(finding) not in dismissed_keys]
        if original and not decision["uwagi"] and not decision.get("replan"):
            decision["next"] = "ok"
    for finding in amplified:
        if dismissed_key(finding) not in dismissed_keys:
            decisions.append({"sha": sha, "next": "issue", "uwagi": [finding]})
    return decisions, kinds, check_notes, dismissed_keys, plan_text, check_results, checks_failed


def complete_check(picked, worktree, base, sha, ci, decisions, plan_text, checks_failed, dismissed_keys,
                   check_results, pr_number, rounds, check_notes, diff_fingerprint, kinds, conflict_fix):
    from lokay.tick import _retry, dumps, refresh_body
    from lokay.check import validate_sha, verdict as check_verdict
    from lokay.effects.git import git_try
    from lokay.effects.gh import pr_files, check_comment

    validate_sha(sha, ci, decisions)
    from lokay.scope import code_scope_issue

    code, changed, err = git_try(worktree, "diff", "--name-only", f"origin/{base}...HEAD")
    if code != 0:
        raise RuntimeError(err or "scope diff failed")
    files = changed.splitlines()
    code, tracked, err = git_try(worktree, "ls-files", "-z")
    if code != 0:
        raise RuntimeError(err or "scope paths lookup failed")
    repo_files = list(filter(None, tracked.split("\0")))
    scope = code_scope_issue(files, plan_text, repo_files)
    if not checks_failed and scope and dismissed_key(scope) not in dismissed_keys:
        rounds_append(picked["repo"], picked["issue"], "Check scope: " + scope["log"])
    verdict = check_verdict(sha, ci, decisions, check_results, scope, dismissed_keys)
    saved_merge = state_read(picked["repo"], picked["issue"])
    if verdict["result"] == "merge" and merge_blocked(saved_merge, sha):
        verdict = conflict_fix(_retry(picked, "fix", lambda: pr_files(picked["repo"], pr_number)),
                               "Merge conflict on GitHub; change the PR before checking again.")
    rounds += 1
    check_history = state_read(picked["repo"], picked["issue"]).get("check_history", []) + [{
        "round": rounds, "sha": sha,
        "findings": [finding_summary(row) for row in verdict.get("uwagi", [])],
        "fix_commit_subject": "", "dispute": {},
    }]
    state_update(
        picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "check"}}, sha=sha,
        check_rounds=rounds, result=verdict["result"], verdict=verdict, last_check=verdict,
        check_notes=check_notes, check_history=check_history,
        **store.round_fields(state_read(picked["repo"], picked["issue"]),
                             diff_fingerprint=diff_fingerprint, checks=verdict.get("checks"),
                             completed=verdict["result"] not in ("wait", "pending")),
    )
    counts = ", ".join(
        f"{kind}={len(decision['uwagi'])}"
        for kind, decision in zip(kinds, decisions)
    )
    rounds_append(
        picked["repo"], picked["issue"],
        f"Check {rounds}: sha={sha}, result={verdict['result']}, uwagi: {counts}, ci={ci['result']}, "
        + "checks=" + dumps(verdict["checks"], default=store.json_default),
    )
    lens_notes = [parse_finding(note).lens for note in verdict.get("notes", []) if parse_finding(note).lens]
    if lens_notes:
        rounds_append(picked["repo"], picked["issue"], f"Check {rounds}: notes=" + ", ".join(lens_notes))
    checked_verdict = verdict
    _retry(picked, "check", lambda: check_comment(picked["repo"], pr_number, rounds, checked_verdict, ci))
    _retry(picked, "check", lambda: refresh_body(picked["repo"], int(picked["issue"])), "updated")
    return verdict, rounds


def fix(picked, worktree, branch, sha, verdict, diff, head, diff_fingerprint, repo,
        clone_path, base, read_diff, sync_head):
    from lokay.tick import (escalate, dumps, fix_to_build, gh_json,
                            _retry, replan_prompt, fix_step, pushed_pr,
                            needs_help, refresh_body)
    from lokay import graph
    from lokay.types import Run, Progress
    from lokay.check import QUESTIONS
    from lokay.effects.decide import decide
    from lokay.build import fix_code, fix_publish
    from lokay.effects.git import git_try
    import hashlib
    import os

    escalated = escalate(picked, verdict.get("uwagi"))
    if escalated:
        return "return", escalated
    uwagi = verdict["uwagi"]
    if not uwagi:
        state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "check"}}, verdict=None,
                     local_ci=None, fix_fingerprint=None, fix_reason=None,
                     result="check")
        return "return", {"result": "check", "sha": sha}
    findings = {
        dumps([row["name"], row.get("location")] if "name" in row else
                   finding_fingerprint(row))
        for row in uwagi
    }
    fingerprint = hashlib.sha256(dumps(sorted(findings)).encode()).hexdigest()
    hunk_text = "\n".join(line for line in (diff or "").splitlines()
                          if not line.startswith(("@@", "index ")))
    hunk_fingerprint = hashlib.sha256(hunk_text.encode()).hexdigest()
    saved = state_read(picked["repo"], picked["issue"])
    counts = (saved.get("fix_counts", []) + [len(uwagi)])[-3:]
    history = saved.get("fix_history", []) + [uwagi]
    state_update(picked["repo"], picked["issue"], fix_counts=counts, fix_history=history,
                 **store.round_fields(saved, diff_fingerprint=diff_fingerprint, completed=False))
    rounds_append(picked["repo"], picked["issue"],
                  f"Fix progress: findings={fingerprint}, hunk={hunk_fingerprint}, "
                  f"diff={diff_fingerprint}, counts={counts}")
    stalled = graph.step(Run.from_state(saved), Progress(0, outcome={
        "diff_hash": diff_fingerprint, "fingerprint": fingerprint,
        "hunk_fingerprint": hunk_fingerprint, "counts": counts,
    })).no_progress
    test_log = ((saved.get("local_ci") or {}).get("log") or "") if (saved.get("local_ci") or {}).get("sha") == head else ""
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
            return "return", redirected
        rounds_append(picked["repo"], picked["issue"], "Fix → Plan: no progress, findings=" + fingerprint)
        title, body = saved.get("issue_title"), saved.get("issue_body")
        if not title:
            def read_issue():
                return gh_json(["issue", "view", str(picked["issue"]),
                                "--repo", picked["repo"], "--json", "title,body"],
                               error="issue view failed", strip=False)
            issue = _retry(picked, "plan", read_issue)
            title, body = issue["title"], issue.get("body")
        state_update(picked["repo"], picked["issue"], issue_title=title, issue_body=body,
                     fix_counts=[], diff_fingerprint=None)
        prompt = replan_prompt(picked, "Fix made no progress; revise the plan.", uwagi, head)
        prompt += "\n\nTest log:\n" + test_log
        rounds_append(picked["repo"], picked["issue"], "Re-Plan test log:\n" + test_log)
        state_update(picked["repo"], picked["issue"], _event={"action": "replan"}, plan_prompt=prompt)
        pending = "plan"
        return "continue", (sha, pending, verdict)
    prompt = (
        Path(__file__).resolve().parents[2].joinpath("prompts/fix.md").read_text()
        + "\n\nSHA:\n" + sha
        + "\n\nIssue:\n" + (saved.get("issue_title") or "")
        + "\n" + (saved.get("issue_body") or "")[:6000]
        + "\n\nUwagi:\n" + dumps(uwagi)
        + "\n\nDiff:\n" + (diff or "")[:20000]
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
            retry_response = ""
            state_update(picked["repo"], picked["issue"], pi_response=response)
            if can_dispute and sha not in state_read(picked["repo"], picked["issue"]).get("dispute_rechecks", []):
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
                                  "diff": (diff or "")[:20000]},
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
                    current = state_read(picked["repo"], picked["issue"])
                    state_update(picked["repo"], picked["issue"],
                                 dispute_rechecks=current.get("dispute_rechecks", []) + [sha])
                    return {"result": "done", "dispute_rejected": True}
                remaining = [row for row in uwagi if category(row) in upheld]
                retry_prompt = prompt.replace("\n\nUwagi:\n" + dumps(uwagi),
                                              "\n\nUwagi:\n" + dumps(remaining))
                retry_prompt += "\n\nThe finding was upheld after your dispute. Reason to treat it as valid: "
                retry_prompt += dumps(upheld) + "; your dispute was: " + justification
                retry_prompt += ". Make a concrete change.\nRemaining findings:\n"
                retry_prompt += dumps(remaining)
                outcome = fix_code(worktree, sha, retry_prompt, dict(os.environ), clone_path=clone_path)
                retry_response = outcome.get("pi_response") or outcome.get("explanation") or ""
                state_update(picked["repo"], picked["issue"], pi_response=retry_response)
            if outcome.get("result") == "no_changes" or outcome.get("reason") == "no_changes":
                if "## Dispute" in response or "## Dispute" in retry_response:
                    current = state_read(picked["repo"], picked["issue"])
                    rechecks = current.get("dispute_rechecks", [])
                    if sha not in rechecks:
                        state_update(picked["repo"], picked["issue"],
                                     dispute_rechecks=rechecks + [sha])
                        return {"result": "done", "dispute_recheck": True}
                redirected = fix_to_build(picked, worktree)
                if redirected:
                    return redirected
        return outcome
    fixed = fix_step(picked, "fix_code", fix_action, sha)
    if fixed.get("dispute_recheck"):
        state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "check"}}, verdict=None,
                     local_ci=None, fix_reason=None, result="check")
        rounds_append(picked["repo"], picked["issue"], "Fix -> Check: dispute, re-check")
        return "return", {"result": "check", "sha": sha}
    if fixed.get("dispute_rejected"):
        if verdict.get("unknown") or verdict.get("unlocated_fail") or verdict.get("unlocated_findings"):
            state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "check"}}, verdict=None, result="check")
            return "return", {"result": "check", "sha": sha}
        verdict = {**verdict, "result": "merge", "uwagi": []}
        pending = "merge"
        state_update(picked["repo"], picked["issue"], _event={"action": "verdict", "outcome": verdict},
                     result="merge", verdict=verdict)
        return "continue", (sha, pending, verdict)
    if fixed.get("next") in ("build", "plan"):
        return "return", fixed
    if fixed["result"] == "failed":
        return "return", fixed
    state_update(picked["repo"], picked["issue"], pi_response=fixed.get("pi_response") or "")
    pushed = fix_step(picked, "fix_publish", lambda: fix_publish(worktree, branch, sha), sha)
    if pushed["result"] == "failed":
        return "return", pushed
    if pushed["result"] == "remote_moved" and pushed.get("sha"):
        _retry(picked, "check", sync_head)
    previous_sha = sha
    sha = pushed["sha"]
    if sha != previous_sha and pushed["result"] == "pushed":
        def read_fix_subject():
            code, subject, err = git_try(worktree, "log", "--format=%s", f"origin/{base}..HEAD")
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
            return "return", needs_help(picked, "sha mismatch after push", sha)
        _retry(picked, "fix", lambda: refresh_body(picked["repo"], int(picked["issue"])), "updated")
    fixed_diff = _retry(picked, "fix", read_diff)
    state_update(picked["repo"], picked["issue"], sha=sha, fix_reason=None, fix_fingerprint=fingerprint,
                 fix_hunk_fingerprint=hunk_fingerprint, diff_fingerprint=diff_fingerprint,
                 **store.round_fields(state_read(picked["repo"], picked["issue"]),
                                      diff_fingerprint=hashlib.sha256((fixed_diff or "").encode()).hexdigest(),
                                      completed=False))
    rounds_append(picked["repo"], picked["issue"], f"Fix: sha={sha}")
    pending = "check"
    state_update(picked["repo"], picked["issue"], _event={"action": "fix_complete", "outcome": {**pushed, "previous_sha": previous_sha}})
    return "continue", (sha, pending, verdict)


def wait(picked, verdict, head):
    from lokay.tick import escalate, replan_prompt, dumps

    saved = state_read(picked["repo"], picked["issue"])
    if saved.get("wait_escape") == "plan" and saved.get("no_progress", 0) >= 6:
        escalated = escalate(picked, verdict.get("uwagi"), force=True)
        if escalated:
            return escalated
    if saved.get("wait_escape") == "retry" and saved.get("no_progress", 0) >= 6:
        findings = [*verdict.get("notes", []), *verdict.get("uwagi", []),
                    *verdict.get("unlocated_findings", []),
                    *verdict.get("unlocated_fail", []), *verdict.get("unknown", [])]
        prompt = replan_prompt(picked, "Unlocated/unknown wait exhausted retry; revise the plan.",
                               json.loads(dumps(findings, default=store.json_default)), head)
        state_update(picked["repo"], picked["issue"], _event={"action": "replan"},
                     plan_prompt=prompt, wait_escape="plan", awaiting=None, retry_at=0,
                     result="failed", verdict=None, **deepcopy(PLAN_RESET))
        return {"next": "plan"}
    state_update(picked["repo"], picked["issue"], _event={"action": "enter_node", "outcome": {"node": "check"}}, result="wait", verdict=verdict,
                 retry_at=time.time() + 300, awaiting=None, wait_escape="retry")
    return verdict

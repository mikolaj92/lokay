from __future__ import annotations

from copy import deepcopy

import json
import time
from pathlib import Path

from typing import Literal

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

    git(worktree, "fetch", "origin", base, timeout=300)
    out = git(worktree, "diff", "--name-only", "--diff-filter=U")
    if out:
        return out.splitlines()
    code, out, err = git_try(worktree, "merge", "--no-edit", f"origin/{base}", timeout=300)
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
    from lokay.review import recompute_verdict

    verdict = recompute_verdict(sha, state_read(picked["repo"], picked["issue"]))
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
    from lokay.review import hunk_finding
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
    from lokay.review import QUESTIONS, check_state, classify_multilens, decide_batches, docs_only
    from lokay.checks import CheckInput, run_checks
    from lokay.effects.decide import decide

    def read_stat():
        code, out, err = git_try(worktree, "diff", "--stat", f"origin/{base}...HEAD", timeout=30)
        if code != 0:
            raise RuntimeError(err or "diff stat failed")
        return out

    plan_text = saved.get("issue_body") or ""
    check_input = CheckInput(
        repo=picked["repo"], issue=int(picked["issue"]), sha=sha,
        issue_body=saved.get("issue_body") or "",
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
    kinds = () if checks_failed else ("alignment", "docs") if docs_only(diff or "") else tuple(
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
    from lokay.review import validate_sha, verdict as check_verdict
    from lokay.effects.gh import pr_files, check_comment

    validate_sha(sha, ci, decisions)
    scope = None
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
        check_inputs={"sha": sha, "ci": ci, "decisions": decisions, "results": check_results,
                      "scope": scope, "dismissed_keys": dismissed_keys},
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


def removed_assertions(patch: str) -> dict[str, int]:
    from lokay.lint import diff_lines
    from lokay.scope import ASSERTION, is_test

    lines = {}
    counts = {}
    for path, _, kind, text in diff_lines(patch):
        lines.setdefault(path, []).append(text)
        if kind in {"-", "+"} and ASSERTION.match(text):
            counts[path] = counts.get(path, 0) + (1 if kind == "-" else -1)
    return {path: count for path, count in counts.items()
            if count > 0 and is_test(path, lines[path])}


def assertion_base_violations(worktree: Path, base_revision: str, patch: str) -> dict[str, int]:
    from lokay.effects.git import git
    from lokay.scope import ASSERTION

    violations = {}
    for path in removed_assertions(patch):
        base_text = ""
        if git(worktree, "--literal-pathspecs", "ls-tree", "--name-only", base_revision, "--", path):
            base_text = git(worktree, "show", f"{base_revision}:{path}")
        try:
            after_text = (worktree / path).read_text()
        except FileNotFoundError:
            after_text = ""
        count = sum(bool(ASSERTION.match(line)) for line in base_text.splitlines()) - sum(
            bool(ASSERTION.match(line)) for line in after_text.splitlines())
        if count > 0:
            violations[path] = count
    return violations


def fix(picked, worktree, branch, sha, verdict, diff, head, diff_fingerprint, repo,
        clone_path, base, read_diff, sync_head) -> tuple[Literal["return"], dict] | tuple[Literal["continue"], tuple]: 
    from lokay.tick import (escalate, dumps, gh_json, _retry, replan_prompt,
                            fix_step, pushed_pr, needs_help, refresh_body)
    from lokay import graph, h2
    from lokay.types import Run, Progress
    from lokay.build import tidy_and_commit
    from lokay.effects.git import apply_patch, git_try, push, restore_head
    import hashlib

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
    def replan():
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

    if stalled:
        return replan()

    def fix_action():
        current = state_read(picked["repo"], picked["issue"])
        identity = [sha, saved.get("fix_rounds", 0), fingerprint]
        if current.get("h2_fix_identity") == identity and current.get("h2_fix_committed"):
            return {"result": "done"}
        fixed_head = sha
        outcome = {"result": "done"}
        summary = ""
        outcome = h2.run_issue(
            picked["repo"], int(picked["issue"]), clone_path, sha,
            saved.get("issue_title") or "", saved.get("issue_body") or "",
            findings=uwagi,
            fix_round=saved.get("fix_rounds", 0),
        )
        if outcome["result"] != "done":
            return outcome
        summary = outcome.get("summary") or ""
        patch = Path(outcome["patch"])
        state_update(picked["repo"], picked["issue"], pi_response=summary,
                     h2_fix_identity=identity, h2_fix_patch=str(patch), h2_fix_committed=None)
        if patch.read_bytes().strip():
            apply_patch(worktree, patch)
            patch_text = patch.read_text()
            removed = removed_assertions(patch_text)
            if removed:
                from lokay.effects.git import git

                base_revision = git(worktree, "merge-base", f"origin/{base}", sha)
                removed = assertion_base_violations(worktree, base_revision, patch_text)
            if removed:
                restore_head(worktree)
                for path, count in removed.items():
                    rounds_append(picked["repo"], picked["issue"],
                                  f"Fix rejected: removes {count} test assertions in {path}")
                return {"result": "failed", "reason": f"fix_removes_assertions: {next(iter(removed))}"}
            tidy_and_commit(worktree, f"Fix #{picked['issue']}")
            code, fixed_head, err = git_try(worktree, "rev-parse", "HEAD")
            if code:
                raise RuntimeError(err or "fix HEAD lookup failed")
        if fixed_head.strip() == sha:
            rounds_append(picked["repo"], picked["issue"],
                          "Fix: no changes" + (f": {summary.splitlines()[0]}" if summary else ""))
            return {"result": "done", "no_changes": True}
        state_update(picked["repo"], picked["issue"], h2_fix_identity=identity,
                     h2_fix_committed=fixed_head.strip())
        return outcome

    fixed = fix_step(picked, "harness2", fix_action, sha)
    if fixed["result"] == "failed":
        return "return", fixed
    if fixed.get("no_changes"):
        from lokay.effects.decide import decide
        from lokay.review import QUESTIONS
        import re

        current = state_read(picked["repo"], picked["issue"])
        checks = saved.get("local_ci") or {}
        kinds = {path.stem.removeprefix("check_") for path in QUESTIONS.glob("check_*.json")}
        categories = {}
        for row in uwagi:
            kind = parse_finding(row).lens or row.get("warstwa")
            if kind not in kinds or row.get("warstwa") not in (None, "", "scope"):
                return replan()
            categories.setdefault(kind, []).append(row)
        if not (head == sha == verdict.get("sha")
                and checks.get("sha") == sha and checks.get("result") == "green"
                and not checks.get("failed")
                and checks.get("ci", saved.get("ci")) in ("green", "no_ci")
                and sha not in current.get("dispute_rechecks", [])):
            return replan()
        justification = current.get("pi_response") or ""
        section = re.search(r"^## Dispute\s*\n(.*?)(?=^## |\Z)", justification, re.M | re.S)
        if section:
            justification = section.group(1).strip()
        rejected = []
        dispute = {}
        for kind, rows in categories.items():
            answer = _retry(picked, "fix", lambda: decide({
                "state": {"justification": justification, "diff": diff or "",
                          "issue_goal": saved.get("issue_body") or "", "findings": rows},
                "questions": [{"id": "valid", "type": "bool",
                               "instructions": "Is the finding still valid and actionable given the "
                                               "justification, the diff and the issue goal?",
                               "options": {"true": "upheld", "false": "rejected"}}],
            }))["valid"]
            upheld = answer["choice"] == "true"
            dispute[kind] = answer
            rounds_append(picked["repo"], picked["issue"],
                          f"Dispute: {kind} {'upheld' if upheld else 'rejected'} "
                          f"(p={dumps(answer['probabilities'])})")
            if not upheld:
                rejected.extend(rows)
        check_history = deepcopy(current.get("check_history", []))
        if check_history:
            check_history[-1]["dispute"] = dispute
        state_update(picked["repo"], picked["issue"], check_history=check_history)
        if rejected:
            dismissed = current.get("dispute_dismissed") or {}
            keys = list(dismissed.get("keys", [])) if dismissed.get("sha") == sha else []
            notes = list(current.get("check_notes", []))
            for row in rejected:
                if dismissed_key(row) not in keys:
                    keys.append(dismissed_key(row))
                if row not in notes:
                    notes.append(row)
            state_update(picked["repo"], picked["issue"], check_notes=notes,
                         dispute_dismissed={"sha": sha, "keys": keys})
            _retry(picked, "fix", lambda: refresh_body(picked["repo"], int(picked["issue"])), "updated")
        if any(answer["choice"] == "true" for answer in dispute.values()):
            return replan()
        state_update(picked["repo"], picked["issue"],
                     _event={"action": "enter_node", "outcome": {"node": "check"}},
                     dispute_rechecks=[*current.get("dispute_rechecks", []), sha],
                     verdict=None, local_ci=None, fix_reason=None, result="check")
        rounds_append(picked["repo"], picked["issue"], "Fix -> Check: dispute, re-check")
        return "return", {"result": "check", "sha": sha}
    pushed = fix_step(picked, "fix_publish", lambda: push(worktree, branch, sha), sha)
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

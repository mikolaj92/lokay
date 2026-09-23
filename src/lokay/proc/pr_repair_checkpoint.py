"""Verified pre-publication evidence derived from durable Fala journals.

The same reader supports pre-checkpoint runs. Neither ancestry nor a branch name
is authority: the journal must bind the admitted start, exact commit, and the
successful declared-test child to the same repair run and worktree.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from lokay.proc import pr_repair_receipts as receipts
from lokay.proc.pr_repair_push import _git_value
from lokay.repair_worktree_dirt import repair_worktree_dirt

_IDENTITY = (
    "repo", "pr", "branch", "head_sha", "repair_kind", "reviewed_head_sha",
    "task", "findings", "task_identity_sha256", "review_result_sha256", "review",
)


def _rows(ref: dict, path_id: str) -> dict:
    db = Path(ref["db"]).expanduser().resolve(strict=True)
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as conn:
        row = conn.execute(
            "SELECT correlation_path_id FROM runs WHERE id=?", (ref["run_id"],),
        ).fetchone()
        if row != (path_id,) or ref.get("path_id") != path_id:
            raise ValueError("repair journal run/path mismatch")
        rows = conn.execute(
            "SELECT id, status, input_json, output_json FROM processes WHERE run_id=?",
            (ref["run_id"],),
        ).fetchall()
    result = {}
    for ident, status, raw_input, raw_output in rows:
        if not ident.startswith(path_id + ":") or status != "succeeded":
            continue
        envelope = json.loads(raw_output)
        if envelope.get("job") != ident or envelope.get("status") != "ok":
            raise ValueError("repair journal output identity mismatch")
        result[ident.removeprefix(path_id + ":")] = {
            "input": json.loads(raw_input), "output": envelope["payload"],
        }
    return result


def _output(rows: dict, name: str) -> dict:
    value = rows[name]["output"]
    if value.get("ok") is not True:
        raise ValueError("repair journal gate failed: " + name)
    return value


def verify_local(proof: dict, *, require_clean: bool = True) -> None:
    """Read-only exact identity check; never reset, clean, fetch or checkout."""
    from lokay.proc._common import runner
    from lokay.test_cache import cache_key

    run = runner()
    work = Path(proof["worktree"])
    intent = proof["intent"]
    for args, expected in (
        (("rev-parse", "--verify", "HEAD^{commit}"), intent["target_head_sha"]),
        (("symbolic-ref", "--quiet", "--short", "HEAD"), intent["branch"]),
    ):
        status, actual, error = _git_value(run, work, *args)
        if status or error or actual != expected:
            raise ValueError("repair checkpoint local identity drift")
    repo = intent["repo"]
    for flags in ((), ("--push", "--all")):
        status, origin, error = _git_value(run, work, "remote", "get-url", *flags, "origin")
        if status or error or origin.removesuffix(".git") not in {
            "https://github.com/" + repo, "git@github.com:" + repo,
            "ssh://git@github.com/" + repo,
        }:
            raise ValueError("repair checkpoint repository mismatch")
    if require_clean and repair_worktree_dirt(run, work) not in {"clean", "evidence"}:
        raise ValueError("repair checkpoint worktree dirty")
    if not proof["test"]["key"] or cache_key(run, work, tuple(proof["test"]["argv"])) != proof["test"]["key"]:
        raise ValueError("repair checkpoint tested identity drift")


def _verify_scoped_tests(rows: dict, declaration: dict, full: dict, terminal: dict,
                         repo: str, worktree: str) -> None:
    from lokay.proc.derive_changed_test_scope import derive as derive_scope

    names = ("run_declared_tests", "select_declared_test_outcome", "derive_changed_test_scope",
             "run_changed_scope_tests", "select_green_test_result", "write_test_green_cache")
    for name in names:
        child = rows[name]["input"]
        if (child.get("repo") != repo or child.get("worktree") != worktree
                or child.get("changed_scope") is not True):
            raise ValueError("repair scoped test child identity mismatch")
    selected = _output(rows, "select_declared_test_outcome")
    scope = _output(rows, "derive_changed_test_scope")
    executed = _output(rows, "run_changed_scope_tests")
    written = _output(rows, "write_test_green_cache")
    argv = scope.get("argv")
    derived = derive_scope(declaration, selected)
    green = _output(rows, "select_green_test_result")
    if (full.get("route") != "red" or full.get("returncode") in (None, 0)
            or full.get("argv") != declaration["test_argv"]
            or full.get("tests") != " ".join(declaration["test_argv"])
            or selected.get("route") != "scope" or scope.get("route") != "scope"
            or not argv or derived.get("route") != "scope" or derived.get("argv") != argv
            or executed.get("route") != "green" or executed.get("returncode") != 0
            or executed.get("argv") != argv or executed.get("tests") != " ".join(argv)
            or green.get("route") != "green" or green.get("source") != executed
            or written.get("written") is not True or written.get("tests") != executed["tests"]
            or terminal.get("tests") != executed["tests"]
            or terminal.get("full_suite_returncode") != full["returncode"]):
        raise ValueError("repair scoped test evidence mismatch")


def admitted_head(inputs: dict, admitted: dict) -> str:
    """Validate admission; ancestry only admits the starting local revision.

    Publication still requires exact same-run commit and test observations.
    """
    from lokay.proc._common import runner
    from lokay.repair_continuation import repair_head_continues

    start = inputs["head_sha"]
    head = admitted.get("worktree_head_sha")
    if any(admitted.get(k) != v for k, v in {
        "repo": inputs["repo"], "pr": inputs["pr"], "branch": inputs["branch"],
        "repair_start_head_sha": start,
    }.items()) or not isinstance(head, str) or len(head) != 40 or any(
        c not in "0123456789abcdef" for c in head
    ):
        raise ValueError("repair journal admission identity mismatch")
    try:
        continues = repair_head_continues(runner(), Path(admitted["worktree"]), head, start)
    except RuntimeError as exc:
        raise ValueError("repair journal admission ancestry unavailable") from exc
    if not continues:
        raise ValueError("repair journal admission identity mismatch")
    return head


def derive(*, inputs: dict, run_ref: dict) -> dict:
    rows = _rows(run_ref, "pr_repair")
    admitted = _output(rows, "worktree_add")
    if admitted.get("route") != "ready":
        raise ValueError("repair was not admitted")
    original = rows["worktree_add"]["input"]
    for key in _IDENTITY:
        if original.get(key) != inputs.get(key):
            raise ValueError("repair journal handoff mismatch: " + key)
    repo, pr, branch, start = (inputs[k] for k in ("repo", "pr", "branch", "head_sha"))
    admitted_head(inputs, admitted)
    if inputs.get("repair_kind") == "review":
        task = inputs.get("task") or {}
        if (task.get("repo") != repo or task.get("type") != "Issue"
                or task.get("state") != "OPEN" or int(task.get("number") or 0) <= 0):
            raise ValueError("repair journal canonical task mismatch")
        review = inputs.get("review") or {}
        if review.get("verdict") != "request_changes" or any(
            review.get(key) != inputs.get(key)
            for key in ("reviewed_head_sha", "task_identity_sha256", "review_result_sha256")
        ):
            raise ValueError("repair journal review handoff mismatch")
    worktree = admitted["worktree"]
    commit_name = "commit_test_repair" if "commit_test_repair" in rows else "commit_initial_repair"
    test_name = "test_local_recheck" if commit_name == "commit_test_repair" else "test_local"
    for name in (commit_name, test_name, "finalize_repair_tests", "assert_real_diff"):
        if any(rows[name]["input"].get(k) != original.get(k) for k in _IDENTITY):
            raise ValueError("repair journal cross-process lineage mismatch")
    commit = _output(rows, commit_name)
    test = _output(rows, test_name)
    if commit.get("committed") is not True or commit.get("worktree") != worktree:
        raise ValueError("repair journal commit missing")
    from lokay.proc.repair_agent_revision import verified_commit_target

    target = verified_commit_target(commit=commit, inputs=inputs, run_ref=run_ref, worktree=worktree)
    commit = {**commit, "commit": target}
    if (_output(rows, "finalize_repair_tests").get("route") != "publish"
            or _output(rows, "assert_real_diff").get("real") is not True):
        raise ValueError("repair journal publication gates missing")
    if (test.get("tested") is not True or test.get("skipped")
            or test.get("recorded_red") or test.get("worktree") != worktree
            or test.get("repo") != repo):
        raise ValueError("repair journal test missing")
    test_ref = {k: test[k] for k in ("db", "run_id", "path_id")}
    test_rows = _rows(test_ref, "test_local_execution")
    for name in ("inspect_test_declaration", "read_test_green_cache", "select_test_terminal"):
        child_input = test_rows[name]["input"]
        if child_input.get("repo") != repo or child_input.get("worktree") != worktree:
            raise ValueError("repair test child input mismatch")
    declaration = _output(test_rows, "inspect_test_declaration")
    cached = _output(test_rows, "read_test_green_cache")
    terminal = _output(test_rows, "select_test_terminal")["result"]
    if (declaration.get("worktree") != worktree or declaration.get("route") != "test"
            or terminal.get("ok") is not True or terminal.get("tested") is not True
            or terminal.get("skipped") or terminal.get("worktree") != worktree):
        raise ValueError("repair child test identity mismatch")
    if cached.get("route") == "hit":
        green = cached.get("cached") or {}
        if green.get("passed") is not True or green.get("key") != cached.get("key"):
            raise ValueError("repair test cache evidence missing")
    else:
        green = _output(test_rows, "run_declared_tests")
        if terminal.get("scoped") is True:
            _verify_scoped_tests(test_rows, declaration, green, terminal, repo, worktree)
        elif green.get("returncode") != 0 or green.get("route") != "green":
            raise ValueError("repair declared tests not green")
    intent = receipts.build_push_intent(
        repo=repo, pr=pr, branch=branch, repair_kind=inputs["repair_kind"],
        start_head_sha=start, target_head_sha=commit["commit"],
        reviewed_head_sha=str(inputs.get("reviewed_head_sha") or ""),
        task=inputs.get("task") or {}, findings=inputs.get("findings") or [],
        task_identity_sha256=str(inputs.get("task_identity_sha256") or ""),
        review_result_sha256=str(inputs.get("review_result_sha256") or ""),
    )
    proof = {
        "schema": "lokay.pr-repair-checkpoint/1", "intent": intent,
        "worktree": worktree, "run": run_ref,
        "task": inputs.get("task") or {}, "findings": inputs.get("findings") or [],
        "review": {key: (inputs.get("review") or {}).get(key) for key in (
            "verdict", "reviewed_head_sha", "task_identity_sha256", "review_result_sha256",
        )},
        "test": {**test_ref, "argv": declaration["test_argv"], "key": cached["key"]},
        # Preserve the verified evidence even after terminal journal retention.
        "evidence": {
            "repair": {name: hashlib.sha256(receipts._canonical(rows[name])).hexdigest()
                       for name in ("worktree_add", commit_name, test_name, "finalize_repair_tests", "assert_real_diff",
                                    "run_agent", "pr_repair_retry_agent", "evidence_repair_agent", "pr_test_repair_agent",
                                    "commit_initial_repair")
                       if name in rows},
            "test": {name: hashlib.sha256(receipts._canonical(row)).hexdigest()
                     for name, row in test_rows.items()},
        },
    }
    # Preserve the exact tested commit even when post-test dirt blocks pushing.
    # Recovery always repeats the strict dirt gate before any effect.
    verify_local(proof, require_clean=False)
    proof["sha256"] = hashlib.sha256(receipts._canonical(proof)).hexdigest()
    return proof


def recover_legacy(*, repo: str, pr: int, branch: str, state_dir: Path, budget: int) -> dict:
    """Inspect only this PR's journal, then use the normal checkpoint verifier."""
    from lokay.graph_run import pr_journal_dir

    directory = pr_journal_dir("pr_repair", repo, pr)
    if directory is None or not (directory / "state.sqlite").is_file():
        return {"ok": True, "route": "none"}
    db = (directory / "state.sqlite").resolve()
    try:
        with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as conn:
            candidates = conn.execute(
                "SELECT p.run_id, p.input_json FROM processes p JOIN runs r ON r.id=p.run_id "
                "WHERE r.correlation_path_id='pr_repair' AND p.id='pr_repair:worktree_add' "
                "AND p.status='succeeded' ORDER BY p.rowid DESC LIMIT 64"
            ).fetchall()
        proofs = []
        for run_id, raw in candidates:
            inputs = json.loads(raw)
            if (inputs.get("repo"), inputs.get("pr"), inputs.get("branch")) != (repo, pr, branch):
                continue
            ref = {"db": str(db), "run_id": run_id, "path_id": "pr_repair"}
            try:
                proof = derive(inputs=inputs, run_ref=ref)
            except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
                continue
            proofs.append(proof)
        if len(proofs) != 1:
            return {"ok": True, "route": "none" if not proofs else "fail_closed",
                    "reason": "repair_legacy_lineage_unverified"}
        receipt = receipts.read(repo, pr, state_dir=state_dir)
        if receipt.get("last_head_sha") == proofs[0]["intent"]["target_head_sha"]:
            return {"ok": True, "route": "none"}
        return receipts.record_publication_checkpoint(proof=proofs[0], state_dir=state_dir, budget=budget)
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        return {"ok": True, "route": "fail_closed", "reason": "repair_legacy_journal_unavailable"}


def persist(*, inputs: dict, run_ref: dict, state_dir: Path, budget: int) -> dict:
    try:
        proof = derive(inputs=inputs, run_ref=run_ref)
        return receipts.record_publication_checkpoint(proof=proof, state_dir=state_dir, budget=budget)
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        return {"ok": True, "route": "fail_closed", "reason": "repair_checkpoint_unverified", "detail": str(exc)}

#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
if grep -rnE '^(<<<<<<< |>>>>>>> |=======$)' src/ prompts/ sandbox/ scripts/; then
    exit 1
else
    [ "$?" -eq 1 ]
fi
sandbox=$(mktemp -d "${TMPDIR:-/tmp}/lokay-check.XXXXXX")
trap 'rm -rf "$sandbox"' EXIT HUP INT TERM
export UV_CACHE_DIR="$sandbox/cache"
export UV_PROJECT_ENVIRONMENT="$PWD/.venv"
export UV_LOCKED=1
env -u UV_NO_SYNC -u UV_OFFLINE uv sync --locked --all-extras
.venv/bin/python -m compileall -q src
.venv/bin/python -I - <<'PY'
from pathlib import Path
import importlib
import pkgutil

import lokay
import lokay.h2
import yaml

expected = (Path.cwd() / 'src/lokay').resolve()
if lokay.__file__ is None or Path(lokay.__file__).resolve().parent != expected:
    raise SystemExit(f'wrong lokay location: {lokay.__file__}; expected {expected}')
assert 'tick_deadline.get' not in Path(lokay.h2.__file__).read_text()

def import_failed(name):
    raise ImportError(f'cannot import {name}')

for module in pkgutil.walk_packages(lokay.__path__, lokay.__name__ + '.', onerror=import_failed):
    importlib.import_module(module.name)
PY
mkdir -p "$sandbox/home" "$sandbox/tmp" "$sandbox/cache" "$sandbox/bin"
printf '%s\n' '#!/bin/sh' 'echo "unexpected external gh (blocked by local check)" >&2' 'exit 1' > "$sandbox/bin/gh"
chmod +x "$sandbox/bin/gh"
export HOME="$sandbox/home" TMPDIR="$sandbox/tmp" UV_CACHE_DIR="$sandbox/cache"
export UV_NO_SYNC=1 UV_PYTHON_DOWNLOADS=never UV_OFFLINE=1 PATH="$sandbox/bin:$PATH"
.venv/bin/python -m lokay.gh_boundary
.venv/bin/python - <<'PY'
from unittest.mock import patch

from lokay.effects.gh import pr_checks

cancelled = {"__typename": "CheckRun", "workflowName": "workflow", "name": "checks",
             "status": "COMPLETED", "conclusion": "CANCELLED"}
success = dict(cancelled, conclusion="SUCCESS")
running = dict(cancelled, status="IN_PROGRESS", conclusion=None)
for rollup, expected in (([success, cancelled], "green"), ([cancelled], "red"),
                         ([cancelled, running], "pending")):
    with patch("lokay.effects.gh.gh_json", return_value={"headRefOid": "head", "statusCheckRollup": rollup}):
        result = pr_checks("owner/repo", 1, "head")
    assert result["result"] == expected, result
print("superseded checks: green")
PY
.venv/bin/python - <<'PY'
from lokay.review import verdict
from lokay.types import CheckResult

log = "ruff check: Found 43 errors"
failure = {"warstwa": "GitHub CI", "plik": "", "log": log}
ci = {"sha": "head", "result": "red", "ci": "red", "failed": [failure]}
result = verdict("head", ci, [], (CheckResult("ci_green", "fail", log, ()),))
assert result["result"] == "fix", result
assert result["uwagi"] == [failure], result
assert result["uwagi"][0]["log"] == log, result
assert result["unlocated_findings"] == [failure], result
print("unlocated failure checks: green")
PY
(
    fail() { printf '%s\n' "pi sandbox check failed: $*" >&2; exit 1; }
    protected="$sandbox/protected"
    shim="$PWD/sandbox/bin/git"
    /usr/bin/git init -q "$protected" || fail init
    /usr/bin/git -C "$protected" -c user.name=x -c user.email=x@x commit --allow-empty -qm x || fail seed
    LOKAY_PI_WORKTREE=$(CDPATH= cd -- "$protected" && pwd -P)
    LOKAY_PI_GITDIR=$(CDPATH= cd -- "$protected/.git" && pwd -P)
    allowed() {
        LOKAY_PI_WORKTREE="$LOKAY_PI_WORKTREE" LOKAY_PI_GITDIR="$LOKAY_PI_GITDIR" "$shim" "$@" >/dev/null 2>&1 || fail "allowed $*"
    }
    blocked() {
        if LOKAY_PI_WORKTREE="$LOKAY_PI_WORKTREE" LOKAY_PI_GITDIR="$LOKAY_PI_GITDIR" "$shim" "$@" >"$sandbox/blocked" 2>&1; then
            fail "blocked $*"
        else
            [ "$?" -eq 1 ] || fail "blocking status $*"
            [ "$(head -n 2 "$sandbox/blocked")" = 'git: command blocked for pi' ] || fail "blocking message $*"
        fi
    }
    cd "$protected"
    allowed clone "$protected" "$sandbox/foreign"
    allowed -C "$sandbox/foreign" fetch origin
    allowed -c user.name=x -c user.email=x@x -C "$sandbox/foreign" commit --allow-empty -m x
    blocked fetch
    blocked push
    blocked -c user.name=x -c user.email=x@x commit --allow-empty -m x
    blocked reset --hard
    cd "$sandbox"
    blocked -C "$protected" fetch
    GIT_DIR="$protected/.git" blocked fetch
) || exit 1
.venv/bin/python - "$sandbox/protected" <<'PY'
import os
import shutil
import sys

from lokay.effects.pi import pi_env
from lokay.effects.tests import UV_CACHE_DIR

env = pi_env(os.environ, sys.argv[1])
try:
    if env["UV_CACHE_DIR"] != str(UV_CACHE_DIR):
        raise SystemExit("pi sandbox check failed: UV_CACHE_DIR")
finally:
    shutil.rmtree(env["LOKAY_STATE_DIR"])
PY
.venv/bin/python - "$sandbox" <<'PY'
import os
import sys
from pathlib import Path

from lokay.effects.git import git, git_try, merge_base_or_restart

os.environ.update(GIT_AUTHOR_NAME="mikolaj92", GIT_AUTHOR_EMAIL="check@example.invalid",
                  GIT_COMMITTER_NAME="mikolaj92", GIT_COMMITTER_EMAIL="check@example.invalid",
                  GIT_AUTHOR_DATE="2025-01-01T00:00:00+00:00", GIT_COMMITTER_DATE="2025-01-01T00:00:00+00:00")
sandbox = Path(sys.argv[1])
origin = sandbox / "origin.git"
repo = sandbox / "base-merge"
git(sandbox, "init", "--bare", str(origin))
git(sandbox, "init", "-b", "base", str(repo))
git(repo, "remote", "add", "origin", str(origin))
file = repo / "file.txt"
file.write_text("initial\n")
git(repo, "add", "file.txt")
git(repo, "commit", "-m", "initial")
git(repo, "push", "-u", "origin", "base")
git(repo, "checkout", "-b", "lokay/1")
file.write_text("issue\n")
git(repo, "commit", "-am", "issue")
git(repo, "push", "-u", "origin", "lokay/1")
old_head = git(repo, "rev-parse", "HEAD")
git(repo, "checkout", "base")
file.write_text("base\n")
git(repo, "commit", "-am", "base")
git(repo, "push", "origin", "base")
git(repo, "checkout", "lokay/1")
assert merge_base_or_restart(repo, "base") == ["file.txt"]
assert git(repo, "rev-parse", "HEAD^{tree}") == git(repo, "rev-parse", "origin/base^{tree}")
assert git_try(repo, "merge-base", "--is-ancestor", old_head, "HEAD")[0] == 0
assert git_try(repo, "rev-parse", "--verify", "--quiet", "MERGE_HEAD")[0] == 1
git(repo, "push", "origin", "lokay/1")
git(repo, "checkout", "base")
(repo / "clean.txt").write_text("clean\n")
git(repo, "add", "clean.txt")
git(repo, "commit", "-m", "clean base update")
git(repo, "push", "origin", "base")
git(repo, "checkout", "lokay/1")
assert merge_base_or_restart(repo, "base") == []
assert (repo / "clean.txt").read_text() == "clean\n"
print("base merge checks: green")
PY
uv run python - "$sandbox" <<'PY'
import inspect
import os
import sys
from pathlib import Path
from unittest.mock import patch

from lokay import main_guard
from lokay.effects import maintenance
from lokay.effects.git import ensure_worktree, git, worktree_remove

os.environ.update(GIT_AUTHOR_NAME="mikolaj92", GIT_AUTHOR_EMAIL="check@example.invalid",
                  GIT_COMMITTER_NAME="mikolaj92", GIT_COMMITTER_EMAIL="check@example.invalid")
sandbox = Path(sys.argv[1]).resolve()
origin = sandbox / "atomic-origin.git"
seed = sandbox / "atomic-seed"
clone = sandbox / "atomic-clone"
git(sandbox, "init", "--bare", str(origin))
git(sandbox, "init", "-b", "base", str(seed))
files = ("one.txt", "two.txt", "three.txt")
for name in files:
    (seed / name).write_text(f"{name}\n")
git(seed, "add", "--", *files)
git(seed, "commit", "-m", "seed")
git(seed, "remote", "add", "origin", str(origin))
git(seed, "push", "origin", "base", "base:lokay/1", "base:lokay/2")
git(origin, "symbolic-ref", "HEAD", "refs/heads/base")
git(sandbox, "clone", str(origin), str(clone))

def interrupted(directory):
    directory = Path(directory)
    assert directory.parent == clone.parent
    assert directory.name.startswith(f".{clone.name}-wt-")
    assert ".removing-" in directory.name
    (directory / files[0]).unlink()
    raise OSError("interrupted deletion")

for issue, safe in ((1, True), (2, False)):
    branch = f"lokay/{issue}"
    wt = clone.with_name(f"{clone.name}-wt-{issue}")
    assert ensure_worktree(clone, branch, wt)["result"] == "added"
    with patch("lokay.effects.git.shutil.rmtree", side_effect=interrupted) as deletion:
        result = worktree_remove(clone, wt, safe=safe, branch=branch if safe else None)
    assert result["result"] == "removed", result
    deletion.assert_called_once()
    assert not wt.exists()
    assert f"worktree {wt}\n" not in git(clone, "worktree", "list", "--porcelain") + "\n"
    result = ensure_worktree(clone, branch, wt)
    assert result["result"] == "added", result
    assert git(wt, "status", "--porcelain") == ""
    for name in git(wt, "ls-files", "-z").split("\0"):
        if name:
            assert (wt / name).is_file(), name
    assert all((wt / name).read_text() == f"{name}\n" for name in files)
for module in (main_guard, maintenance):
    assert '"worktree", "remove"' not in inspect.getsource(module)
print("atomic worktree removal checks: green")
PY
uv run python - "$sandbox" <<'PY'
import inspect
import os
import sys
from pathlib import Path

from lokay import graph, tick
from lokay.effects.git import git, git_try, restart_from_base

os.environ.update(GIT_AUTHOR_NAME="mikolaj92", GIT_AUTHOR_EMAIL="check@example.invalid",
                  GIT_COMMITTER_NAME="mikolaj92", GIT_COMMITTER_EMAIL="check@example.invalid",
                  GIT_AUTHOR_DATE="2025-01-01T00:00:00+00:00", GIT_COMMITTER_DATE="2025-01-01T00:00:00+00:00")
sandbox = Path(sys.argv[1])
origin = sandbox / "replan-origin.git"
repo = sandbox / "replan-from-base"
git(sandbox, "init", "--bare", str(origin))
git(sandbox, "init", "-b", "base", str(repo))
git(repo, "remote", "add", "origin", str(origin))
file = repo / "file.txt"
file.write_text("initial\n")
git(repo, "add", "file.txt")
git(repo, "commit", "-m", "initial")
git(repo, "push", "-u", "origin", "base")
git(repo, "checkout", "-b", "lokay/1")
file.write_text("issue\n")
git(repo, "commit", "-am", "issue")
git(repo, "push", "-u", "origin", "lokay/1")
old_head = git(repo, "rev-parse", "HEAD")
git(repo, "checkout", "base")
(repo / "clean.txt").write_text("clean\n")
git(repo, "add", "clean.txt")
git(repo, "commit", "-m", "clean base update")
git(repo, "push", "origin", "base")
git(repo, "checkout", "lokay/1")
restart_from_base(repo, "base")
assert git(repo, "rev-parse", "HEAD^{tree}") == git(repo, "rev-parse", "origin/base^{tree}")
assert git_try(repo, "merge-base", "--is-ancestor", old_head, "HEAD")[0] == 0
assert git_try(repo, "merge-base", "--is-ancestor", "origin/base", "HEAD")[0] == 0
assert git_try(repo, "rev-parse", "--verify", "--quiet", "MERGE_HEAD")[0] == 1
git(repo, "push", "origin", "lokay/1")
assert 'if git_try(worktree, "merge-base", "--is-ancestor", "HEAD", f"origin/{base}")[0]:' in inspect.getsource(tick._prepare)
assert not hasattr(graph, "empty_patch_result")
print("replan from base checks: green")
PY
uv run python - <<'PY'
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from lokay.effects.git import git, git_try

with TemporaryDirectory() as directory:
    repo = Path(directory)
    git(repo, "init")
    (repo / "file.txt").write_text("content\n")
    lock = repo / ".git/index.lock"
    lock.touch()
    assert git_try(repo, "add", "file.txt")[0] == 0
    assert not lock.exists()
    lock.touch()
    child = subprocess.Popen(
        ["uv", "run", "python", "-c",
         "import sys, time; f = open(sys.argv[1]); print('ready', flush=True); time.sleep(60)", str(lock)],
        stdout=subprocess.PIPE, text=True,
    )
    try:
        assert child.stdout.readline().strip() == "ready"
        assert git_try(repo, "add", "file.txt")[0] != 0
        assert lock.exists()
    finally:
        child.terminate()
        child.wait(timeout=10)
print("stale index lock checks: green")
PY
.venv/bin/python - <<'PY'
from datetime import datetime, timezone

from lokay import graph
from lokay.store import derive_waiting_on
from lokay.types import RepoSnapshot, Snapshot

now = 1_792_512_000
state = {"result": "pending", "node": "check", "last_attempt": now - 3000}
for age, waiting_on in ((10, "ci"), (400, "ready")):
    state["updated_at"] = datetime.fromtimestamp(now - age, timezone.utc).isoformat()
    snapshot = Snapshot(repos=(RepoSnapshot(name="owner/repo", prs=(), issues=(), states={1: state}),), now=now)
    picked = graph.pick(snapshot)
    assert (picked is None) if age == 10 else (picked is not None and picked.issue == 1 and picked.kind == "issue")
    assert derive_waiting_on(state, now) == waiting_on
for node, pr, age in (("fix", 7, 400), ("plan", 7, 400), ("fix", None, 400), ("fix", 7, 10)):
    state = {"result": "failed", "node": node, "pr": pr, "retry_at": 0,
             "updated_at": datetime.fromtimestamp(now - age, timezone.utc).isoformat()}
    snapshot = Snapshot(repos=(RepoSnapshot(name="owner/repo", prs=(), issues=(), states={1: state}),), now=now)
    picked = graph.pick(snapshot)
    if node == "fix" and pr and age == 400:
        assert picked is not None and picked.issue == 1 and picked.kind == "pr", picked
        assert picked.target["number"] == 7, picked
    else:
        assert picked is None, picked
print("poll interval checks: green")
PY
uv run python - <<'PY'
from lokay import graph
from lokay.types import RepoSnapshot, Snapshot

now = 1_792_512_000
for result in ("failed", "running", "pending", "merged", "closed"):
    snapshot = Snapshot(repos=(
        RepoSnapshot(name="owner/A", status={"status": "red", "issue": 7}, prs=(), issues=(),
                     states={7: {"result": result, "node": "check", "retry_at": now - 10}}),
        RepoSnapshot(name="owner/B", prs=(), issues=(),
                     states={8: {"result": "pending", "node": "check", "retry_at": now - 20}}),
    ), now=now)
    picked = graph.pick(snapshot)
    assert picked is not None, (result, picked)
    if result in ("running", "pending"):
        assert (picked.repo, picked.issue, picked.kind) == ("owner/A", 7, "red_main"), (result, picked)
    else:
        assert picked.kind != "red_main", (result, picked)
        assert (picked.repo, picked.issue) == ("owner/B", 8), (result, picked)
print("red main fairness checks: green")
PY
uv run python - <<'PY'
from lokay import graph
from lokay.types import RepoSnapshot, Snapshot

now = 1_792_512_000
for merged in (False, True):
    states = {
        7: {"result": "pending", "node": "plan", "awaiting": "children", "children": [11, 12]},
        11: {"result": "failed", "node": "plan"},
    }
    if merged:
        states[12] = {"result": "merged"}
    snapshot = Snapshot(repos=(
        RepoSnapshot(name="owner/A", status={"status": "red", "issue": 7}, prs=(), issues=(),
                     states=states),
        RepoSnapshot(name="owner/B", prs=(), issues=(),
                     states={8: {"result": "pending", "node": "check", "retry_at": now - 20}}),
    ), now=now)
    picked = graph.pick(snapshot)
    assert picked is not None, (merged, picked)
    if merged:
        assert picked.kind != "red_main", picked
        assert (picked.repo, picked.issue) == ("owner/B", 8), picked
    else:
        assert (picked.repo, picked.issue, picked.kind) == ("owner/A", 12, "red_main"), picked
print("red main children checks: green")
PY
.venv/bin/python - <<'PY'
from lokay import graph
from lokay.types import Fixed, Run

sha = "unchanged-head"
event = Fixed(0, outcome={"result": "pushed", "sha": sha, "previous_sha": sha})
first = graph.step(Run.from_state({"node": "fix", "sha": sha}), event)
assert first.state["node"] == "check", first.state
assert sha in first.state["dispute_rechecks"], first.state
second = graph.step(Run.from_state({**first.state, "node": "fix"}), event)
assert second.state["node"] == "plan", second.state
print("Fix dispute checks: green")
PY
.venv/bin/python - <<'PY'
from lokay import graph
from lokay.finish import removed_assertions
from lokay.types import Failed, Run

patch = "--- a/tests/test_x.py\n+++ b/tests/test_x.py\n@@ -1,2 +1 @@\n-assert x\n-assert y\n+assert (x, y) == (True, True)\n"
assert removed_assertions(patch) == {"tests/test_x.py": 1}
assert removed_assertions("--- a/tests/test_x.py\n+++ b/tests/test_x.py\n@@ -0,0 +1 @@\n+assert x\n") == {}
assert removed_assertions(patch.replace("tests/test_x.py", "src/x.py")) == {}
reason = "harness2: {'result': 'failed', 'reason': 'fix_removes_assertions: tests/test_x.py'}"
result = graph.step(Run.from_state({"node": "fix"}), Failed(0, outcome={"reason": reason}))
assert result.state["node"] == "plan", result.state
print("Fix assertion checks: green")
PY
.venv/bin/python - <<'PY'
from pathlib import Path
from unittest.mock import patch

from lokay.checks import CheckInput, weakened_tests

diff = "diff --git a/tests/test_x.py b/tests/test_x.py\n--- a/tests/test_x.py\n+++ b/tests/test_x.py\n@@ -1,2 +1 @@\n-assert x\n-assert y\n+assert (x, y) == (True, True)\n"
with patch("lokay.config.repo", return_value={"test": ["pytest"]}), \
        patch("lokay.effects.tests.base_tests_on_head", return_value={"result": "green"}):
    for added, expected in (("", "fail"), ("+assert y\n", "pass")):
        for checks in ("green", "red"):
            change = diff if not added else diff.replace("+1 @@", "+1,2 @@") + added
            x = CheckInput("owner/repo", 1, "head", "tests/test_x.py", "", change, [],
                           {"result": checks, "ci": checks, "sha": "head"}, Path.cwd())
            result = weakened_tests(x)
            assert result.status == expected, result
            if expected == "fail":
                assert "Removes 1 test assertions" in result.reason, result
print("weakened test assertion checks: green")
PY
uv run python - <<'PY'
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from lokay import graph, tick
from lokay.checks import CHECKS, CheckInput, deleted_files
from lokay.types import PLAN_RESET, Run, parse_event, to_dict

paths = ["src/old.py", "assets/old name.txt"]
diff = ('diff --git a/src/old.py b/src/old.py\ndeleted file mode 100644\n'
        '--- a/src/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n'
        'diff --git "a/assets/old name.txt" "b/assets/old name.txt"\n'
        'deleted file mode 100644\n--- "a/assets/old name.txt"\n'
        '+++ /dev/null\n@@ -1 +0,0 @@\n-old\n')
x = CheckInput("owner/repo", 1, "head", "unrelated change", "", diff, [], {}, Path.cwd())
assert deleted_files in CHECKS
failed = deleted_files(x)
assert failed.status == "fail", failed
assert failed.reason == "deleted files not named by the issue or plan: 2 (assets/old name.txt, src/old.py)"
assert {finding.plik for finding in failed.findings} == set(paths)
assert all(finding.lens == "deleted_files" for finding in failed.findings)
for names in ("src/old.py, assets/old name.txt", "old.py, old name.txt"):
    for field in ("issue_body", "plan"):
        result = deleted_files(replace(x, **{field: names}))
        assert result.status == "pass", result
        assert result.reason == "deleted files named by the issue or plan", result
assert deleted_files(replace(x, issue_body="src/old.py")).status == "fail"
assert deleted_files(replace(x, plan="prefixold.py old name.txt.bak")).status == "fail"
result = deleted_files(replace(x, diff=diff.replace("deleted file mode 100644\n", "")))
assert (result.status, result.reason) == ("pass", "no deleted files"), result
run = Run.from_state({"node": "check", "pr": 7, "sha": "head", "plan_accepted_sha": "head"})

def update(repo, issue, _event, **fields):
    global run
    run = graph.step(run, parse_event({"ts": 1, **_event, "fields": fields}))

verdict = {"result": "fix", "uwagi": [to_dict(finding) for finding in failed.findings]}
with patch("lokay.tick.state_update", side_effect=update), \
        patch("lokay.tick.replan_prompt", return_value="revised plan") as prompt:
    assert tick.replan_deleted_files({"repo": x.repo, "issue": x.issue}, verdict, x.sha)
    assert run.state["node"] == "plan", run.state
    assert all(run.state[key] == value for key, value in PLAN_RESET.items()), run.state
    assert run.state["pr"] == 7 and run.state["sha"] == "head", run.state
    assert failed.reason in prompt.call_args.args[1], prompt.call_args
    assert prompt.call_args.args[2] == verdict["uwagi"], prompt.call_args
    prompt.reset_mock()
    assert not tick.replan_deleted_files({"repo": x.repo, "issue": x.issue},
                                         {"result": "fix", "uwagi": [{"pytanie": "weakened_tests"}]}, x.sha)
    prompt.assert_not_called()
print("deleted files scope checks: green")
PY
uv run python - <<'PY'
from lokay import graph
from lokay.types import PLAN_RESET, Run, event_record, parse_event

closed = Run.from_state({"result": "closed", "node": "merge", "sha": "old", "pr": 35,
                         "verdict": {"result": "merge"}, "failures": 3, "retry_at": 99,
                         "reason": "empty PR diff", "last_error": "error",
                         "waiting_on": "children", "awaiting": "children",
                         "fix_counts": [4, 4, 4], "no_progress": 6})
raw = {"ts": 1, "fields": {}, "action": "reopened", "outcome": {"sha": "new", "pr": 36}}
event = parse_event(raw)
assert event_record(event) == raw
live = graph.step(closed, event).state
assert (live["result"], live["node"], live["sha"], live["pr"]) == ("check", "check", "new", 36)
assert all(live[key] is None for key in ("verdict", "reason", "last_error", "waiting_on", "awaiting"))
assert live["failures"] == live["retry_at"] == 0
assert live["fix_counts"] == [] and live["no_progress"] == 0
other = parse_event({"ts": 1, "fields": {}, "action": "enter_node", "outcome": {"node": "plan"}})
assert graph.step(closed, other).state == closed.state
merged = Run.from_state({**closed.state, "result": "merged"})
assert graph.step(merged, event).state == merged.state
issue = graph.step(closed, parse_event({**raw, "outcome": {"issue": True}})).state
assert (issue["result"], issue["node"], issue["pr"], issue["sha"]) == ("check", "plan", None, None)
assert all(issue[key] == value for key, value in PLAN_RESET.items())
assert not graph.reopen_pr_allowed(closed.state, {"headRefOid": "old"}, True)
assert not graph.reopen_pr_allowed(closed.state, {"headRefOid": "new"}, False)
assert graph.reopen_pr_allowed(closed.state, {"headRefOid": "new"}, True)
assert not graph.reopen_pr_allowed(merged.state, {"headRefOid": "new"}, True)
assert not graph.reopen_issue_allowed(closed.state, True, False, False, False)
marked = {**closed.state, "closed_on_github": True}
assert graph.reopen_pr_allowed(marked, {"headRefOid": "old", "state": "OPEN"}, True)
assert not graph.reopen_pr_allowed(marked, {"headRefOid": "old", "state": "OPEN"}, False)
replanned = Run.from_state({"node": "build", "sha": "pr-head", "dispute_rechecks": ["pr-head"]})
fresh_check = parse_event({"ts": 1, "fields": {"sha": "pr-head"}, "action": "enter_node",
                           "outcome": {"node": "check", "previous_sha": None}})
assert graph.step(replanned, fresh_check).state["node"] == "check"
assert graph.step(Run.from_state(marked), event).state["closed_on_github"] is None
assert graph.reopen_issue_allowed(marked, True, False, False, False)
assert not graph.reopen_issue_allowed(marked, False, False, False, False)
assert not graph.reopen_issue_allowed(marked, True, True, False, False)
assert graph.reopen_issue_allowed(marked, True, False, True, False)
print("reopen checks: green")
PY
uv run python - <<'PY'
from unittest.mock import patch

from lokay import graph, store, tick
from lokay.types import Run, parse_event

name = "owner/reopen-all"
issues = [{"number": issue, "state": "OPEN"} for issue in (1, 2, 3)]
states = {
    1: {},
    2: {"result": "closed", "node": "check", "pr": 22, "sha": "old-2"},
    3: {"result": "closed", "node": "merge", "pr": 33, "sha": "old-3"},
}
events = []
reopened = set()

def read(repo, issue):
    assert repo == name
    saved = dict(states[issue])
    store.normalize_state(saved)
    saved["waiting_on"] = store.derive_waiting_on(saved)
    return saved

def update(repo, issue, **fields):
    assert repo == name
    event = {"ts": 1, **fields.pop("_event", {}), "fields": fields}
    states[issue] = graph.step(Run.from_state(states[issue]), parse_event(event)).state
    events.append((issue, event))

def remote(args, **kwargs):
    branch = args[args.index("--head") + 1]
    assert args == ["pr", "list", "--repo", name, "--head", branch,
                    "--state", "closed", "--limit", "100", "--json", "number,mergedAt"]
    return {"lokay/2": [{"number": 22, "mergedAt": None}],
            "lokay/3": [{"number": 33, "mergedAt": "2026-10-21T09:00:00Z"}]}[branch]

with patch.object(tick, "state_read", side_effect=read), \
        patch.object(tick, "state_update", side_effect=update), \
        patch.object(tick, "list_prs", return_value=[]) as prs, \
        patch.object(tick, "gh_json", side_effect=remote):
    assert read(name, 1)["waiting_on"] == "ready"
    tick.reopen_closed_issues(name, issues, reopened)
    assert [(issue, event["action"]) for issue, event in events] == [(2, "reopened")]
    assert reopened == {(name, 2)}
    assert (states[2]["node"], states[2]["pr"], states[2]["sha"]) == ("plan", None, None)
    assert states[3]["result"] == "closed"
    prs.assert_called_once_with(name)
    tick.reopen_closed_issues(name, issues, reopened)
    assert [(issue, event["action"]) for issue, event in events] == [(2, "reopened")]
    prs.reset_mock()
    tick.reopen_closed_issues(name, issues[:2], reopened)
    prs.assert_not_called()
print("reopen all closed issues checks: green")
PY
uv run python - <<'PY'
from lokay.effects.pi import OneHarnessRunDone, TickExpired, start_harness_run, tick_harness_started

assert tick_harness_started.get() is None
start_harness_run()
start_harness_run()
for _ in range(2):
    token = tick_harness_started.set(False)
    try:
        start_harness_run()
        assert tick_harness_started.get() is True
        try:
            start_harness_run()
        except TickExpired as exc:
            assert isinstance(exc, OneHarnessRunDone)
        else:
            raise AssertionError("second harness2 start allowed in one tick")
    finally:
        tick_harness_started.reset(token)
assert tick_harness_started.get() is None
start_harness_run()
start_harness_run()
print("one harness2 per tick checks: green")
PY
uv run python - "$sandbox" <<'PY'
import os
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from lokay import graph, store, tick
from lokay.effects.git import git, git_try, merge_base_or_restart, restart_from_base
from lokay.types import PLAN_RESET

sandbox = Path(sys.argv[1]).resolve()
state_dir = sandbox / "fresh-state"
name = "owner/fresh"
config = {"name": name, "clone_path": str(sandbox / "absent-clone"), "merge": "off"}
remote_issue = "OPEN"
closed_prs = []
original_pick = graph.pick

def select(snapshot):
    selected = original_pick(snapshot)
    return selected if selected is None or selected.kind in ("prs", "issues") else None

def remote(args, **kwargs):
    if args[:2] == ["api", "graphql"]:
        assert "prc_" not in " ".join(args), args
        return {"data": {"repository": {"issue_1": {"state": remote_issue}, "pr_7": {"state": "CLOSED"}}}}
    assert args[:2] == ["pr", "list"], args
    if "closed" in args:
        assert args[args.index("--json") + 1] == "number,mergedAt", args
        assert int(args[args.index("--limit") + 1]) >= 100, args
        return closed_prs
    return []

with ExitStack() as stack:
    stack.enter_context(patch.dict(os.environ, {"LOKAY_STATE_DIR": str(state_dir)}))
    for key, value in (("HOME", state_dir), ("RUNS", state_dir / "runs"), ("LOCKS", state_dir / "locks")):
        stack.enter_context(patch.object(store, key, value))
    stack.enter_context(patch.object(tick.maintenance, "sweep"))
    stack.enter_context(patch.object(tick, "probes", return_value={"host": "ok"}))
    stack.enter_context(patch.object(tick, "load_repos", return_value=[config]))
    stack.enter_context(patch.object(tick, "gh_json", side_effect=remote))
    stack.enter_context(patch.object(tick, "open_issues", side_effect=lambda _: [
        {"number": 1, "state": "OPEN"}] if remote_issue == "OPEN" else []))
    stack.enter_context(patch.object(tick, "open_pr_for", return_value=None))
    stack.enter_context(patch.object(graph, "pick", side_effect=select))
    updates = stack.enter_context(patch.object(tick, "state_update", wraps=store.state_update))
    env = {"LOKAY2_REPO": name, "LOKAY2_ISSUE": "1"}

    def poll():
        updates.reset_mock()
        tick.pick(env)
        return [call.kwargs["_event"]["action"] for call in updates.call_args_list if "_event" in call.kwargs]

    def fresh():
        saved = store.state_read(name, 1)
        assert saved["node"] == "plan" and saved["result"] != "closed", saved
        assert saved["pr"] is None and saved["sha"] is None, saved
        assert all(saved[key] == value for key, value in PLAN_RESET.items()), saved
        return saved

    store.state_update(name, 1, _event={"action": "enter_node", "outcome": {"node": "check"}},
                       result="check", pr=7, sha="old", branch="lokay/1", h2_start="old")
    assert poll() == ["reopened"]
    before = fresh()
    assert poll() == []
    assert store.state_read(name, 1) == before
    store.state_update(name, 1, _event={"action": "closed"}, closed_on_github=False)
    closed_prs = [{"number": 7, "mergedAt": None}]
    assert poll() == ["reopened"]
    before = fresh()
    assert poll() == []
    assert store.state_read(name, 1) == before
    store.state_update(name, 1, _event={"action": "closed"}, closed_on_github=False)
    closed_prs = []
    assert poll() == []
    assert store.state_read(name, 1)["result"] == "closed"
    closed_prs = [{"number": 7, "mergedAt": "2026-10-21T09:00:00Z"}]
    for marked in (False, True):
        store.state_update(name, 1, _event={"action": "closed"}, closed_on_github=marked)
        before = store.state_read(name, 1)
        assert poll() == []
        assert store.state_read(name, 1) == before
    closed_prs = [{"number": 6, "mergedAt": None}, *closed_prs]
    assert poll() == []
    assert store.state_read(name, 1) == before
    store.state_update(name, 1, _event={"action": "reopened", "outcome": {"issue": True}})
    remote_issue = "CLOSED"
    assert poll() == ["closed"]
    assert store.state_read(name, 1)["result"] == "closed"
    assert store.state_read(name, 1)["closed_on_github"] is True

    os.environ.update(GIT_AUTHOR_NAME="mikolaj92", GIT_AUTHOR_EMAIL="check@example.invalid",
                      GIT_COMMITTER_NAME="mikolaj92", GIT_COMMITTER_EMAIL="check@example.invalid")
    origin = sandbox / "fresh-origin.git"
    repo = sandbox / "fresh-build"
    git(sandbox, "init", "--bare", str(origin))
    git(sandbox, "init", "-b", "base", str(repo))
    git(repo, "remote", "add", "origin", str(origin))
    (repo / "keep.txt").write_text("keep\n")
    git(repo, "add", "keep.txt")
    git(repo, "commit", "-m", "initial")
    git(repo, "push", "-u", "origin", "base")
    git(origin, "symbolic-ref", "HEAD", "refs/heads/base")
    git(repo, "remote", "set-head", "origin", "base")
    git(repo, "checkout", "-b", "lokay/1")
    git(repo, "rm", "keep.txt")
    git(repo, "commit", "-m", "delete")
    git(repo, "push", "-u", "origin", "lokay/1")
    old_head = git(repo, "rev-parse", "HEAD")

    class BuildStarted(Exception):
        pass

    stack.enter_context(patch.object(tick, "repo_config", return_value=config))
    stack.enter_context(patch.object(tick, "_repo_paths", return_value=(repo, repo)))
    stack.enter_context(patch.object(tick, "_ensure_worktree"))
    stack.enter_context(patch("lokay.h2.run_issue", side_effect=BuildStarted))
    restart = stack.enter_context(patch.object(tick, "restart_from_base", wraps=restart_from_base))
    merge = stack.enter_context(patch.object(tick, "merge_base_or_restart", wraps=merge_base_or_restart))
    for issue, branch in ((1, "lokay/1"), (2, "lokay/2")):
        if issue == 2:
            git(repo, "checkout", "-b", branch, "origin/base")
        store.state_update(name, issue, _event={"action": "reopened", "outcome": {"issue": True}})
        store.state_update(name, issue, issue_title="Restore content", issue_body="Restore keep.txt", difficulty="easy", pr=None)
        restart.reset_mock()
        merge.reset_mock()
        try:
            tick._prepare({"repo": name, "issue": issue})
        except BuildStarted:
            pass
        else:
            raise AssertionError("Build did not start")
        assert git(repo, "rev-parse", "HEAD^{tree}") == git(repo, "rev-parse", "origin/base^{tree}")
        if issue == 1:
            restart.assert_called_once_with(repo, "base")
            merge.assert_not_called()
            assert git_try(repo, "merge-base", "--is-ancestor", old_head, "HEAD")[0] == 0
            git(repo, "push", "origin", branch)
        else:
            restart.assert_not_called()
            merge.assert_called_once_with(repo, "base")
print("fresh start after closed PR checks: green")
PY
uv run python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import main_guard

with TemporaryDirectory(prefix="lokay-tested-red-") as temporary:
    cwd = Path(temporary).resolve()
    cases = (
        ("printf '2 failed, 5 passed\\n'; exit 1", "red", True, False),
        ("printf 'no tests ran\\n'; exit 5", "red", False, False),
        ("printf '5 passed\\n'", "green", True, False),
        ("if [ -f retried ]; then printf '5 passed\\n'; else touch retried; "
         "printf '1 failed, 4 passed\\n'; exit 1; fi", "green", True, True),
        ("printf '0 passed\\n'", "red", False, False),
        ("true", "red", False, False),
        ("printf 'LOKAY_TEST_CWD=%s\\n2 failed, 5 passed\\n' \"$PWD\"; exit 1",
         "red", True, False),
        ("printf 'LOKAY_TEST_CWD=%s\\n5 passed\\nLOKAY_TEST_CWD=%s/empty\\n' \"$PWD\" \"$PWD\"",
         "red", False, False),
    )
    for command, expected, tested, flaky in cases:
        result = main_guard.run_repo_tests({"test": ["sh", "-c", command]}, "head", cwd)
        assert result["result"] == expected, result
        assert result["tested"] is tested, result
        assert result["tested_cwds"] == ([str(cwd)] if tested else []), result
        assert bool(result["notes"]) is flaky, result
        assert bool(result["failed"]) is (expected == "red"), result
        assert ("Retry:" in result["log"]) is (expected == "red" or flaky), result
        if command == cases[0][0]:
            red = result
            assert result["log"].count("2 failed, 5 passed") == 2, result
    baseline = {"sha": "head", "argv": ["sh"], "guard_version": main_guard.GUARD_VERSION,
                "ci": red, "lockfile": {"status": "pass", "findings": [], "reason": "ok"}}
    with patch.object(main_guard, "git", return_value="head"), \
            patch.object(main_guard, "main_status", return_value={"owner/repo": {"baseline": baseline}}), \
            patch.object(main_guard, "save_main_status"), \
            patch.object(main_guard, "guard_issue", return_value=7) as issue:
        status = main_guard.check_main("owner/repo", cwd, base="main", config={"test": ["sh"]})
    assert status["status"] == "red", status
    assert status["issue"] == 7, status
    issue.assert_called_once()
print("tested red checks: green")
PY
uv run lokay replay fixtures/replay/
uv run lokay replay fixtures/ticks/

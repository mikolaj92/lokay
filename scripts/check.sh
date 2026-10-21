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
assert 'if saved.get("pr"):\n                restart_from_base(worktree, base)' in inspect.getsource(tick._prepare)
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
assert not graph.reopen_issue_allowed(closed.state, True, False, False)
marked = {**closed.state, "closed_on_github": True}
assert graph.reopen_pr_allowed(marked, {"headRefOid": "old", "state": "OPEN"}, True)
assert not graph.reopen_pr_allowed(marked, {"headRefOid": "old", "state": "OPEN"}, False)
replanned = Run.from_state({"node": "build", "sha": "pr-head", "dispute_rechecks": ["pr-head"]})
fresh_check = parse_event({"ts": 1, "fields": {"sha": "pr-head"}, "action": "enter_node",
                           "outcome": {"node": "check", "previous_sha": None}})
assert graph.step(replanned, fresh_check).state["node"] == "check"
assert graph.step(Run.from_state(marked), event).state["closed_on_github"] is None
assert graph.reopen_issue_allowed(marked, True, False, False)
assert not graph.reopen_issue_allowed(marked, False, False, False)
assert not graph.reopen_issue_allowed(marked, True, True, False)
assert not graph.reopen_issue_allowed(marked, True, False, True)
print("reopen checks: green")
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
uv run python - <<'PY'
from lokay import graph
from lokay.types import RepoSnapshot, Snapshot

now = 10_000
state = {"result": "pending", "node": "fix", "reason": "tick yields after one harness2 run",
         "pr": 206, "branch": "lokay/141", "sha": "abc", "last_attempt": 1_000, "retry_at": 0}
for changes, expected in (({}, True), ({"last_attempt": now - 10}, False),
                          ({"result": "running"}, False), ({"result": "closed"}, False),
                          ({"node": "check"}, True)):
    snapshot = Snapshot(now=now, repos=(RepoSnapshot(
        name="o/r", last_attempt=9_999, prs=(), issues=(), states={141: {**state, **changes}},
    ),))
    picked = graph.pick(snapshot)
    if expected:
        assert picked is not None, changes
        assert picked.kind == "pr" and picked.issue == 141, picked
        assert picked.target["number"] == 206 and picked.target["headRefOid"] == "abc", picked
    else:
        assert picked is None, picked
print("pending fix due checks: green")
PY
uv run lokay replay fixtures/replay/
uv run lokay replay fixtures/ticks/

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

from lokay.effects.git import git, git_try, merge_base_or_restart, restore_paths

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
origin = sandbox / "restore-origin.git"
repo = sandbox / "restore-tests"
git(sandbox, "init", "--bare", str(origin))
git(sandbox, "init", "-b", "base", str(repo))
git(repo, "remote", "add", "origin", str(origin))
file = repo / "test_existing.py"
file.write_text("base\n")
git(repo, "add", "test_existing.py")
git(repo, "commit", "-m", "base test")
git(repo, "push", "-u", "origin", "base")
git(repo, "checkout", "-b", "lokay/2")
file.write_text("changed\n")
new = repo / "test_new.py"
new.write_text("new\n")
git(repo, "add", "test_existing.py", "test_new.py")
git(repo, "commit", "-m", "changed tests")
paths = ["test_existing.py", "test_new.py"]
assert restore_paths(repo, "base", paths)
assert file.read_text() == "base\n"
assert not restore_paths(repo, "base", paths)
assert new.read_text() == "new\n"
assert git(repo, "diff", "--cached", "--name-only") == "test_existing.py"
print("restore unapproved test checks: green")
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
uv run lokay replay fixtures/replay/
uv run lokay replay fixtures/ticks/

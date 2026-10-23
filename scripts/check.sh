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
uv run python - <<'PY'
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay.setup import repair_venvs

for outcome, kept in ((subprocess.TimeoutExpired("probe", 10), True),
                      (subprocess.CompletedProcess([], 1), False),
                      (OSError("missing python"), False),
                      (subprocess.CompletedProcess([], 0), True)):
    with TemporaryDirectory() as directory:
        worktree = Path(directory)
        (worktree / "pyproject.toml").touch()
        venv = worktree / ".venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "bin/python").touch()
        with patch("lokay.setup.run_process", side_effect=outcome if isinstance(outcome, Exception) else None,
                   return_value=outcome), patch("lokay.setup.git", return_value=""):
            repair_venvs(worktree)
        assert venv.is_dir() == kept, outcome
print("venv repair checks: ok")
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
uv run python - <<'PY'
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from lokay.effects.git import ensure_worktree, git, plan_checkout, samefile, worktree_remove

os.environ.update(GIT_AUTHOR_NAME="mikolaj92", GIT_AUTHOR_EMAIL="check@example.invalid",
                  GIT_COMMITTER_NAME="mikolaj92", GIT_COMMITTER_EMAIL="check@example.invalid",
                  GIT_AUTHOR_DATE="2025-01-01T00:00:00+00:00", GIT_COMMITTER_DATE="2025-01-01T00:00:00+00:00")
with TemporaryDirectory(prefix="lokay-samefile-") as directory:
    temporary = Path(directory)
    real = temporary / "Real"
    real.mkdir()
    assert (temporary / "real").is_dir(), "samefile path checks require a case-insensitive filesystem"
    (temporary / "link").symlink_to(temporary / "real", target_is_directory=True)
    origin = temporary / "origin.git"
    clone = real / "repo"
    git(temporary, "init", "--bare", str(origin))
    git(temporary, "clone", str(origin), str(clone))
    git(clone, "checkout", "-b", "main")
    git(clone, "commit", "--allow-empty", "-m", "seed")
    git(clone, "push", "-u", "origin", "HEAD")
    git(origin, "symbolic-ref", "HEAD", "refs/heads/main")
    git(clone, "remote", "set-head", "origin", "main")
    root = temporary / "link/repo"
    assert samefile(root, clone)
    assert not samefile(root, temporary / "missing")
    worktree = root.parent / "repo-wt-5"
    for _ in range(2):
        result = ensure_worktree(root, "lokay/5", worktree)
        assert result["result"] == "added", result
    checkout = plan_checkout(root)
    assert checkout.name == "repo-plan" and samefile(checkout, real / "repo-plan"), checkout
    assert samefile(plan_checkout(root), checkout)
    foreign = temporary / "foreign"
    git(temporary, "clone", str(origin), str(foreign))
    inside = foreign / "inside"
    inside.mkdir()
    result = ensure_worktree(inside, "lokay/5", foreign / "inside-wt-5")
    assert result["result"] == "failed" and "repository top-level mismatch" in result["error"], result
    try:
        plan_checkout(inside)
    except ValueError as exc:
        assert "plan checkout repository mismatch" in str(exc), exc
    else:
        raise AssertionError("plan checkout accepted a different repository top-level")
    wrong = root.parent / "repo-wt-6"
    git(foreign, "worktree", "add", "-b", "lokay/6", str(wrong))
    result = ensure_worktree(root, "lokay/6", wrong)
    assert result["result"] == "failed" and "registration" in result["error"], result
    result = worktree_remove(root, wrong, safe=True, branch="lokay/6")
    assert result["result"] == "failed" and "repository mismatch" in result["error"], result
    assert wrong.is_dir()
    result = worktree_remove(root, worktree, safe=True, branch="lokay/5")
    assert result["result"] == "removed", result
print("samefile path checks: green")
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
uv run python - <<'PY'
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import store
from lokay.effects.git import git, lsof_path, worktree_remove

with TemporaryDirectory() as directory:
    home = Path(directory)
    repo = home / "repo"
    env = {"LOKAY_ROOT": str(repo), "GIT_AUTHOR_NAME": "mikolaj92",
           "GIT_AUTHOR_EMAIL": "checks@example.invalid", "GIT_COMMITTER_NAME": "mikolaj92",
           "GIT_COMMITTER_EMAIL": "checks@example.invalid"}
    with patch.dict(os.environ, env):
        os.environ.pop("LOKAY_VERSION", None)
        git(home, "init", "-b", "main", str(repo))
        git(repo, "commit", "--allow-empty", "-m", "initial")
        git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        with patch.object(store, "HOME", home), patch.object(store, "main_status", return_value={}):
            assert store.write_heartbeat()["version"] == git(repo, "rev-parse", "HEAD")
        with patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}):
            if Path("/usr/sbin/lsof").exists():
                assert lsof_path() == "/usr/sbin/lsof"
        worktree = home / "repo-wt-5"
        git(repo, "worktree", "add", "-b", "lokay/5", str(worktree))
        raw = b"\xda\xff\n"
        store.write_artifact(worktree / "invalid.txt", raw)
        store.write_artifact(worktree / "binary.bin", b"\xda\xff\x00")
        artifact = home / "cleanup.patch"
        result = worktree_remove(repo, worktree, safe=True, branch="lokay/5", patch_path=artifact)
        assert result["result"] == "removed", result
        saved = artifact.read_bytes()
        assert raw in saved and b"GIT binary patch" in saved, saved
        assert not worktree.exists()
        git(repo, "apply", str(artifact))
        assert (repo / "invalid.txt").read_bytes() == raw
        assert (repo / "binary.bin").read_bytes() == b"\xda\xff\x00"
print("worker version and binary cleanup checks: green")
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
from pathlib import Path
from unittest.mock import patch

from lokay import graph, merge, tick
from lokay.effects.pi import TickExpired
from lokay.types import Run, parse_event

rounds = {"plan_rounds": 2, "check_rounds": 3}
merged_fields = {**rounds, "result": "merged", "sha": "merge-sha",
                 "failures": 0, "retry_at": 0, "reason": None, "last_error": None}

with patch.object(merge, "state_read", return_value={}), \
        patch.object(merge, "state_update") as update, \
        patch.object(merge, "merge_allowed", return_value=True), \
        patch("lokay.review.recompute_verdict", return_value={"result": "merge", "sha": "head"}), \
        patch.object(merge, "pr_files", return_value=["file.py"]), \
        patch.object(merge, "base_branch", return_value="main"), \
        patch.object(merge, "gh_merge", return_value={"result": "merged", "merge_sha": "merge-sha"}), \
        patch.object(merge, "worktree_remove") as cleanup:
    def expired(*args, **kwargs):
        update.assert_any_call("owner/repo", 1, **merged_fields)
        raise TickExpired()

    with patch.object(merge, "check_main", side_effect=expired) as check:
        try:
            merge.merge_sha("owner/repo", 7, "head", None, Path("worktree"), "owner", 1,
                            rounds, clone_path=Path("clone"))
        except TickExpired:
            pass
        else:
            raise AssertionError("check_main did not expire")
    check.assert_called_once_with("owner/repo", Path("clone"), "merge-sha", 7, base="main")
    cleanup.assert_not_called()

for pr_state, issue_state, expected in (
        ("MERGED", "CLOSED", ("merged", "merge-sha")),
        ("MERGED", "OPEN", ("merged", "merge-sha")),
        ("CLOSED", "OPEN", ("reopened", None)),
        ("CLOSED", "CLOSED", ("closed", None)),
        ("OPEN", "OPEN", (None, None))):
    remote = {"issue_1": {"state": issue_state},
              "pr_7": {"state": pr_state, "mergeCommit": {"oid": "merge-sha"}}}
    assert tick.poll_outcome({"pr": 7}, remote, 1) == expected, (pr_state, issue_state)

event = parse_event({"ts": 1, "action": "merge_complete",
                     "outcome": {"result": "merged", "merge_sha": "merge-sha"},
                     "fields": {"sha": "merge-sha", "failures": 0, "retry_at": 0,
                                "reason": None, "last_error": None}})
run = graph.step(Run.from_state({"node": "merge", "result": "pending"}), event)
assert run.state["result"] == "merged", run.state
assert run.state["sha"] == "merge-sha", run.state
print("merged state checks: green")
PY
uv run python - <<'PY'
import os
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import graph, merge, store
from lokay.types import RepoSnapshot, Snapshot

with TemporaryDirectory() as directory, ExitStack() as stack:
    home = Path(directory)
    stack.enter_context(patch.dict(os.environ, {"LOKAY_STATE_DIR": directory, "HOME": directory}))
    for key, value in (("HOME", home), ("RUNS", home / "runs"), ("LOCKS", home / "locks")):
        stack.enter_context(patch.object(store, key, value))
    gh_merge = stack.enter_context(patch.object(merge, "gh_merge", return_value={
        "result": "merged", "merge_sha": "merged-S"}))
    files = stack.enter_context(patch.object(merge, "pr_files", return_value=["file.py"]))
    stack.enter_context(patch.object(merge, "check_main", return_value={}))
    stack.enter_context(patch.object(merge, "worktree_remove", return_value={"result": "removed"}))
    stack.enter_context(patch.object(merge, "base_branch", return_value="main"))
    stack.enter_context(patch("lokay.review.recompute_verdict", side_effect=lambda sha, state: state["verdict"]))
    name = "owner/red"
    verdict = {"result": "merge", "sha": "S"}
    red = {"status": "red", "issue": 9}
    store.save_main_status(name, red)
    store.state_update(name, 9, children=[11])
    for issue in (3, 9, 11):
        store.state_update(name, issue, _event={"action": "enter_node", "outcome": {"node": "merge"}},
                           sha="S", verdict=verdict, result="running", pr=issue + 100)
    def merge_issue(issue):
        return merge.merge_sha(name, issue + 100, "S", verdict, None, "owner", issue, {}, clone_path=home)

    blocked = merge_issue(3)
    assert blocked == {"result": "main_red", "merge_sha": None}, blocked
    gh_merge.assert_not_called()
    files.assert_not_called()
    saved = store.state_read(name, 3)
    assert saved["node"] == "merge" and saved["result"] == "pending", saved
    assert saved["reason"] == "main red: merge waits for green main", saved
    assert saved["verdict"] == verdict, saved
    snapshot = Snapshot(repos=(RepoSnapshot(name=name, prs=(), issues=(), states={3: saved}),),
                        now=store.last_activity(saved) + 301)
    assert graph.pick(snapshot) is None
    for issue in (9, 11):
        gh_merge.reset_mock()
        assert merge_issue(issue)["result"] == "merged"
        gh_merge.assert_called_once_with(name, issue + 100, "S")
    store.save_main_status(name, {"status": "green"})
    gh_merge.reset_mock()
    assert merge_issue(3)["result"] == "merged"
    gh_merge.assert_called_once_with(name, 103, "S")
    assert graph.red_main_allows({"status": "green"}, 3, [])
    for issue, expected in ((9, True), (11, True), (3, False)):
        assert graph.red_main_allows(red, issue, [11]) is expected
print("red main merge invariant: green")
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
        assert picked == graph.Pick("owner/A", 7, "red_main"), picked
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
uv run python - <<'PY'
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import finish, tick
from lokay.effects import git

picked = {"repo": "owner/repo", "issue": 1}
sha, new_sha = "old-head", "new-head"
verdict = {"result": "fix", "uwagi": [{"pytanie": "checks", "plik": "src/x.py", "log": "failure"}]}
reason = "Fix made no progress; revise the plan."
for changed, stalled in ((False, False), (True, False), (False, True)):
    saved = {"node": "fix", "sha": sha, "issue_title": "Repair", "issue_body": "Repair x",
             "local_ci": {"sha": sha, "log": "failed checks"}}
    if stalled:
        saved["diff_fingerprint"] = "same-diff"
    events = []

    def update(repo, issue, **fields):
        event = fields.pop("_event", None)
        saved.update(fields)
        if event:
            events.append({**event, "fields": fields})

    with TemporaryDirectory() as directory, ExitStack() as stack:
        worktree = Path(directory)
        patch_file = worktree / "fix.patch"
        patch_file.write_text("--- a/src/x.py\n+++ b/src/x.py\n@@ -1 +1 @@\n-old\n+new\n" if changed else "")
        stack.enter_context(patch.object(finish, "state_read", side_effect=lambda *args: dict(saved)))
        stack.enter_context(patch.object(finish, "state_update", side_effect=update))
        rounds = stack.enter_context(patch.object(finish, "rounds_append"))
        stack.enter_context(patch.object(tick, "escalate", return_value=None))
        stack.enter_context(patch.object(tick, "_ensure_worktree"))
        stack.enter_context(patch.object(tick, "check_deadline"))
        prompt = stack.enter_context(patch.object(tick, "replan_prompt", return_value=reason))
        stack.enter_context(patch.object(tick, "pushed_pr", return_value=True))
        stack.enter_context(patch.object(tick, "refresh_body", return_value={"result": "updated"}))
        harness = stack.enter_context(patch("lokay.h2.run_issue", return_value={
            "result": "done", "patch": str(patch_file), "summary": "Fixed" if changed else "Bez zmian"}))
        apply = stack.enter_context(patch.object(git, "apply_patch"))
        commit = stack.enter_context(patch("lokay.build.tidy_and_commit"))
        stack.enter_context(patch.object(git, "git_try", side_effect=lambda cwd, *args:
            (0, new_sha if args == ("rev-parse", "HEAD") else "Fix #1", "")))
        push = stack.enter_context(patch.object(git, "push", return_value={"result": "pushed", "sha": new_sha}))
        result = finish.fix(picked, worktree, "lokay/1", sha, verdict, "old diff", sha,
                            "same-diff", {}, worktree, "main", lambda: "new diff", lambda: None)
        if changed:
            assert result == ("continue", (new_sha, "check", verdict)), result
            push.assert_called_once_with(worktree, "lokay/1", sha)
            harness.assert_called_once()
            apply.assert_called_once_with(worktree, patch_file)
            commit.assert_called_once()
            assert [event["action"] for event in events] == ["fix_complete"], events
            assert events[0]["outcome"] == {"result": "pushed", "sha": new_sha, "previous_sha": sha}
            prompt.assert_not_called()
        else:
            assert result == ("continue", (sha, "plan", verdict)), result
            push.assert_not_called()
            apply.assert_not_called()
            commit.assert_not_called()
            assert [event["action"] for event in events] == ["replan"], events
            assert events[0]["fields"]["plan_prompt"] == reason + "\n\nTest log:\nfailed checks", events
            prompt.assert_called_once_with(picked, reason, verdict["uwagi"], sha)
            assert saved["fix_counts"] == [] and saved["diff_fingerprint"] is None, saved
            assert any(call.args[2].startswith("Fix → Plan: no progress, findings=")
                       for call in rounds.call_args_list), rounds.call_args_list
            if stalled:
                harness.assert_not_called()
            else:
                harness.assert_called_once()
                rounds.assert_any_call(picked["repo"], picked["issue"], "Fix: no changes: Bez zmian")
print("fix no change checks: green")
PY
uv run python - <<'PY'
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import finish, graph, review, tick
from lokay.types import Run, dismissed_key, parse_event

picked = {"repo": "owner/repo", "issue": 1}
sha = "checked-head"
findings = [{"pytanie": kind, "plik": "src/x.py", "linia_od": 1, "linia_do": 1,
             "zmiana": "already resolved"} for kind in ("correctness", "scope")]
for choice, checks, failure, eligible in (
    ("false", "green", False, True), ("true", "green", False, True),
    ("false", "red", False, False), ("false", "green", True, False),
    ("false", "remote-red", False, False), ("false", "rechecked", False, False),
    ("false", "stale", False, False),
):
    rows = findings + ([{"warstwa": "tests", "plik": "src/x.py", "log": "failure"}] if failure else [])
    verdict = {"result": "fix", "sha": sha, "uwagi": rows}
    saved = {"node": "fix", "sha": sha, "issue_title": "Repair", "issue_body": "Repair x",
             "local_ci": {"sha": "old" if checks == "stale" else sha,
                          "result": "red" if checks == "red" else "green", "failed": [],
                          "ci": "red" if checks == "remote-red" else "no_ci"},
             "check_history": [{"sha": sha, "dispute": {}}],
             "dispute_rechecks": [sha] if checks == "rechecked" else []}

    def update(repo, issue, **fields):
        event = fields.pop("_event", None)
        if event:
            saved.update(graph.step(Run.from_state(saved), parse_event({"ts": 0, **event, "fields": fields})).state)
        saved.update(fields)

    with TemporaryDirectory() as directory, ExitStack() as stack:
        worktree = Path(directory)
        patch_file = worktree / "fix.patch"
        patch_file.write_text("")
        stack.enter_context(patch.object(finish, "state_read", side_effect=lambda *args: deepcopy(saved)))
        stack.enter_context(patch.object(finish, "state_update", side_effect=update))
        rounds = stack.enter_context(patch.object(finish, "rounds_append"))
        stack.enter_context(patch.object(tick, "escalate", return_value=None))
        stack.enter_context(patch.object(tick, "fix_step", side_effect=lambda picked, node, action, sha: action()))
        stack.enter_context(patch.object(tick, "_retry", side_effect=lambda picked, node, action, *args: action()))
        prompt = stack.enter_context(patch.object(tick, "replan_prompt", return_value="revise plan"))
        refresh = stack.enter_context(patch.object(tick, "refresh_body", return_value={"result": "updated"}))
        stack.enter_context(patch("lokay.h2.run_issue", return_value={
            "result": "done", "patch": str(patch_file),
            "summary": "No changes\n## Dispute\nAlready resolved.\n## Other\nNot justification."}))
        decide = stack.enter_context(patch("lokay.effects.decide.decide", side_effect=lambda request: {
            "valid": {"choice": choice, "probabilities": {"true": float(choice == "true"),
                                                        "false": float(choice == "false")}}}))
        git = stack.enter_context(patch("lokay.effects.git.git", side_effect=AssertionError("unexpected git")))
        stack.enter_context(patch("lokay.effects.git.git_try", side_effect=AssertionError("unexpected git")))
        stack.enter_context(patch.object(tick, "gh_json", side_effect=AssertionError("unexpected gh")))
        result = finish.fix(picked, worktree, "lokay/1", sha, verdict, "diff", sha,
                            "diff-hash", {}, worktree, "main", lambda: "diff", lambda: None)
        assert decide.call_count == (2 if eligible else 0), decide.call_args_list
        if eligible:
            assert all(call.args[0]["state"]["justification"] == "Already resolved."
                       for call in decide.call_args_list)
            assert set(saved["check_history"][-1]["dispute"]) == {"correctness", "scope"}
        if eligible and choice == "false":
            keys = [dismissed_key(row) for row in findings]
            assert saved["dispute_dismissed"] == {"sha": sha, "keys": keys}, saved
            assert saved["check_notes"] == findings, saved
            assert saved["dispute_rechecks"] == [sha] and saved["node"] == "check", saved
            assert saved["verdict"] is None and saved["local_ci"] is None and saved["fix_reason"] is None
            assert result == ("return", {"result": "check", "sha": sha}), result
            prompt.assert_not_called()
            refresh.assert_called_once()
            decisions = [{"sha": sha, "next": "issue", "uwagi": findings}]
            assert review.verdict(sha, {"sha": sha, "result": "green"}, decisions, ())["result"] == "fix"
            assert review.verdict(sha, {"sha": sha, "result": "green"}, decisions, (),
                                  dismissed_keys=keys)["result"] == "merge"
        else:
            assert saved["node"] == "plan" and saved["plan_prompt"].startswith("revise plan"), saved
            assert "dispute_dismissed" not in saved, saved
            prompt.assert_called_once()
            refresh.assert_not_called()
            assert result == ("continue", (sha, "plan", verdict)), result
print("dispute exit checks: green")
PY
uv run python - <<'PY'
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import finish, graph, tick
from lokay.effects import git
from lokay.types import Checked, Run, parse_event

picked = {"repo": "owner/repo", "issue": 1}
rows = [{"pytanie": "no_new_comments", "plik": "src/x.py", "linie": [1, 1],
         "zmiana": "docstring -> delete it"},
        {"lens": "weakened_tests", "plik": "tests/existing.py", "linia_od": 1,
         "zmiana": "existing test changed but the issue body does not name it"}]
for mode in ("empty", "changed", "mixed", "stalled"):
    with TemporaryDirectory() as directory, ExitStack() as stack:
        root = Path(directory)
        worktree = root / "repo"
        worktree.mkdir()
        git.git(worktree, "init", "-b", "main")
        git.git(worktree, "config", "user.name", "mikolaj92")
        git.git(worktree, "config", "user.email", "checks@example.invalid")
        (worktree / "src").mkdir()
        (worktree / "tests").mkdir()
        source = worktree / "src/x.py"
        test = worktree / "tests/existing.py"
        source.write_text("value = 1\n")
        original_test = "assert value == 1\n"
        test.write_text(original_test)
        git.git(worktree, "add", "--", "src/x.py", "tests/existing.py")
        git.git(worktree, "commit", "-m", "Base")
        base = git.head(worktree)
        git.git(worktree, "update-ref", "refs/remotes/origin/main", base)
        if mode == "empty":
            from lokay.gates import remove_comment

            for text, line, expected in (
                ('def f():\n    """Only body."""\n', 2, 'def f():\n    pass\n'),
                ('value = "# literal"  # trailing\n', 1, 'value = "# literal"  \n'),
                ('# full line\nvalue = 1\n', 1, 'value = 1\n'),
            ):
                assert remove_comment(text, line, True) == expected
            source.unlink()
            test.write_text("assert True\n")
            generated = worktree / "generated.py"
            generated.write_text("generated = True\n")
            git.git(worktree, "add", "--", "src/x.py", "tests/existing.py", "generated.py")
            git.git(worktree, "commit", "-m", "Gate examples")
            cases = [{"name": "junk", "plik": "src/x.py"},
                     {"lens": "junk", "plik": "tests/existing.py"},
                     {"lens": "no_unit_tests", "plik": "generated.py"}]
            git.revert_gates(worktree, git.gate_tasks(worktree, "main", git.head(worktree), cases))
            assert source.read_text() == "value = 1\n"
            assert test.read_text() == original_test and not generated.exists()
            git.git(worktree, "commit", "-m", "Revert examples")
        source.write_text('"""Added text."""\nvalue = 1\n')
        test.write_text("assert True\n")
        git.git(worktree, "add", "--", "src/x.py", "tests/existing.py")
        git.git(worktree, "commit", "-m", "Change")
        sha = git.head(worktree)
        findings = rows + ([{"pytanie": "check_correctness", "plik": "src/x.py",
                             "linia_od": 2, "zmiana": "wrong value"}] if mode == "mixed" else [])
        verdict = {"sha": sha, "result": "fix", "uwagi": findings}
        saved = {"node": "fix", "sha": sha, "issue_title": "Repair", "issue_body": "Repair x",
                 "no_progress": 6 if mode == "stalled" else 0,
                 "diff_fingerprint": "same" if mode == "stalled" else None}
        events = []

        def update(repo, issue, **fields):
            event = fields.pop("_event", None)
            if event:
                events.append(event)
                saved.update(graph.step(Run.from_state(saved), parse_event({
                    "ts": 0, **event, "fields": fields})).state)
            saved.update(fields)

        patch_file = root / "fix.patch"
        patch_file.write_text("diff --git a/src/x.py b/src/x.py\n--- a/src/x.py\n+++ b/src/x.py\n"
                              '@@ -1,2 +1 @@\n-"""Added text."""\n value = 1\n' if mode == "changed" else "")
        stack.enter_context(patch.object(finish, "state_read", side_effect=lambda *args: deepcopy(saved)))
        stack.enter_context(patch.object(finish, "state_update", side_effect=update))
        rounds = stack.enter_context(patch.object(finish, "rounds_append"))
        escalate = stack.enter_context(patch.object(tick, "escalate", return_value=None))
        help_call = stack.enter_context(patch.object(tick, "needs_help"))
        stack.enter_context(patch.object(tick, "fix_step", side_effect=lambda picked, node, action, sha: action()))
        stack.enter_context(patch.object(tick, "_retry", side_effect=lambda picked, node, action, *args: action()))
        prompt = stack.enter_context(patch.object(tick, "replan_prompt", return_value="revise plan"))
        stack.enter_context(patch.object(tick, "pushed_pr", return_value=True))
        stack.enter_context(patch.object(tick, "refresh_body", return_value={"result": "updated"}))
        harness = stack.enter_context(patch("lokay.h2.run_issue", return_value={
            "result": "done", "patch": str(patch_file), "summary": "No changes"}))
        stack.enter_context(patch.object(git, "base_branch", return_value="main"))
        stack.enter_context(patch("lokay.build.base_branch", return_value="main"))
        push = stack.enter_context(patch.object(git, "push", side_effect=lambda *args: {
            "result": "pushed", "sha": git.head(worktree)}))
        result = finish.fix(picked, worktree, "lokay/1", sha, verdict, "diff", sha,
                            "same", {}, worktree, "main", lambda: "new diff", lambda: None)
        logs = [call.args[2] for call in rounds.call_args_list]
        if mode == "mixed":
            assert result == ("continue", (sha, "plan", verdict)), result
            assert "gate_task" not in saved
            assert not any(log.startswith("Fix: gate") for log in logs)
            assert harness.call_args.kwargs["findings"] == findings
            escalate.assert_called_once()
            push.assert_not_called()
            continue
        new_sha = git.head(worktree)
        assert new_sha != sha and saved["h2_fix_committed"] == new_sha
        assert result == ("continue", (new_sha, "check", verdict)), result
        assert source.read_text() == "value = 1\n" or source.read_text() == "\nvalue = 1\n"
        assert test.read_text() == ("assert True\n" if mode == "changed" else original_test)
        tasks = harness.call_args.kwargs["findings"]
        assert all(task.items() <= enriched.items() for task, enriched in zip(rows, tasks))
        assert "MUST" in tasks[0]["instruction"] and "src/x.py:1" in tasks[0]["instruction"]
        assert "MUST restore tests/existing.py:1" in tasks[1]["instruction"]
        assert base[:12] in tasks[1]["instruction"]
        assert any(log.startswith("Fix: gate revert:") for log in logs) == (mode != "changed")
        assert saved["gate_task"] == {"sha": sha, "rows": tasks}
        assert [event["action"] for event in events] == ["gate_task", "fix_complete"]
        prompt.assert_not_called()
        escalate.assert_not_called()
        help_call.assert_not_called()
        push.assert_called_once_with(worktree, "lokay/1", sha)
        if mode == "empty":
            resumed = finish.fix(picked, worktree, "lokay/1", sha, verdict, "diff", sha,
                                 "same", {}, worktree, "main", lambda: "new diff", lambda: None)
            assert resumed == result and git.head(worktree) == new_sha
            harness.assert_called_once()
for findings, expected in ((rows, "fix"), (rows + [{"pytanie": "check_correctness", "plik": "src/x.py"}], "plan")):
    for hits in (0, 1):
        run = graph.step(Run.from_state({"node": "check", "fix_rounds": graph.FIX_ROUND_LIMIT - 1,
                                        "fix_limit_hits": hits}),
                         Checked(0, outcome={"result": "fix", "uwagi": findings}))
        assert run.state["node"] == expected, run.state
        assert bool(run.state.get("split_pending")) == (expected == "plan" and hits == 1)
gate_uwagi = [{"pytanie": "weakened_tests", "plik": "tests/test_version.py", "linie": [36, 36],
               "zmiana": "Removes 2 test assertions: tests/test_version.py", "uzasadnienie": ""}]
for findings, expected in ((gate_uwagi, None),
                           ([{"pytanie": "scope", "zmiana": "Restore the requested behavior"}],
                            {"result": "pending", "next": "plan"})):
    saved = {"node": "fix", "fix_history": [{} for _ in range(6)], "no_progress": 6,
             "ladder_since": 1, "verdict": {"uwagi": findings}}
    with patch("lokay.tick.state_read", return_value=saved), \
         patch("lokay.tick.state_update") as update, \
         patch("lokay.tick.rounds_append"), \
         patch("lokay.tick.replan_prompt", return_value="revise plan"), \
         patch("lokay.tick.time.time", return_value=1000000), \
         patch.dict("os.environ", {"LOKAY2_LADDER_HOURS": "6"}):
        assert tick.escalate(picked) == expected
        if expected is None:
            assert tick.escalate(picked, gate_uwagi, force=True) is None
            update.assert_not_called()
print("gate exit checks: green")
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

from lokay.checks import CheckInput, _count_weakened_tests, weakened_tests
from lokay.effects import git
from lokay.gates import dead_test_candidates, dead_tests

path = "tests/test_gone.py"
source = "from pkg.gone import Thing\ndef test_thing():\n    assert Thing()\n"
base = {"src/pkg/__init__.py": "", "src/pkg/gone.py": "class Thing: pass\n", path: source}
head = {"src/pkg/__init__.py": "", "pyproject.toml": ""}
def deletion(name, text):
    return (f"diff --git a/{name} b/{name}\ndeleted file mode 100644\n"
            f"--- a/{name}\n+++ /dev/null\n@@ -1,{len(text.splitlines())} +0,0 @@\n"
            + "".join("-" + line + "\n" for line in text.splitlines()))

production_diff = deletion("src/pkg/gone.py", base["src/pkg/gone.py"])
diff = deletion(path, source) + production_diff

def prove(text=source, body="pkg.gone", before=None, after=None, change=None):
    old = dict(base if before is None else before)
    old[path] = text
    new = head if after is None else after
    if change is None:
        production = production_diff if before is None else (
            "diff --git a/src/pkg/mod.py b/src/pkg/mod.py\n"
            "--- a/src/pkg/mod.py\n+++ b/src/pkg/mod.py\n@@ -1 +0,0 @@\n-class Old: pass\n")
        change = deletion(path, text) + production
    result = dead_tests(change, body, old, new, old.get, new.get)
    assert result <= dead_test_candidates(change)
    return result

assert dead_test_candidates(diff) == frozenset({path})
assert prove() == frozenset({path})
assert not prove(body="remove obsolete code")
assert not prove(source + "import pkg\n")
symbol_base = {"src/pkg/__init__.py": "", "src/pkg/mod.py": "class Old: pass\n", path: ""}
symbol_head = {"src/pkg/__init__.py": "", "src/pkg/mod.py": "", "src/pkg/new.py": "class Old: pass\n"}
symbol_test = "from pkg.mod import Old\ndef test_old():\n    assert Old()\n"
assert not prove(symbol_test, "Old", symbol_base, symbol_head)
symbol_head["src/pkg/new.py"] = ""
assert prove(symbol_test, "Old", symbol_base, symbol_head) == frozenset({path})
assert not prove(symbol_test, "pkg.mod", symbol_base, symbol_head)
assert prove(symbol_test, "pkg.mod.Old", symbol_base, symbol_head) == frozenset({path})
symbol_base["src/pkg/mod.py"] = "Old = Kept\n"
assert not prove(symbol_test, "Old", symbol_base, symbol_head)
assert not prove(source.replace("test_thing()", "test_thing(client)"))
assert not prove(source.replace("test_thing()", "test_thing(self)"))
method_source = "from pkg.gone import Thing\nclass TestThing:\n    def test_thing(self):\n        assert Thing()\n"
assert prove(method_source) == frozenset({path})
assert prove(method_source.replace("self", "cls")) == frozenset({path})
assert not prove(method_source.replace("self", "tmp_path, self"))
assert not prove(method_source.replace("self", "*, self"))
assert not prove(method_source + "    def helper(self):\n        def test_nested(self):\n            assert Thing()\n")
for name in ("tests/conftest.py", "tests/helper.py"):
    change = deletion(name, source) + production_diff
    assert not dead_test_candidates(change)
    assert not dead_tests(change, "pkg.gone", {**base, name: source}, head,
                          {**base, name: source}.get, head.get)
assert prove(source.replace("test_thing()", "test_thing(monkeypatch, tmp_path)")) == frozenset({path})
for expression in ('"pkg"', '"pyproject.toml"', "__file__"):
    assert not prove(source + expression + "\n")
assert not prove(change=diff.replace("deleted file mode 100644\n", ""))
for extra in ("from .other import X\n", "from pkg.gone import *\n", "__import__('os')\n",
              "import importlib\nimportlib.import_module('os')\n", "pytest.mark.usefixtures('client')\n"):
    assert not prove(source + extra)
assert not prove(body="pkg.gone_extra")
assert not prove(text="syntax error !")
assert not prove(source, after={**head, "src/pkg/gone.py": base["src/pkg/gone.py"]})
assert prove(source.replace("test_thing()", "test_thing(local)")
             + "@pytest.fixture\ndef local(tmp_path):\n    return tmp_path\n") == frozenset({path})

x = CheckInput("owner/repo", 1, "head", "pkg.gone", "", diff, [], {}, Path.cwd())

def fake_git(worktree, *args):
    if args[0] == "merge-base":
        return 0, "base\n", ""
    if args[0] == "ls-tree":
        return 0, "\n".join(base if args[-1] == "base" else head), ""
    if args[0] == "show":
        revision, name = args[1].split(":", 1)
        text = (base if revision == "base" else head).get(name)
        return (1, "", "missing") if text is None else (0, text, "")
    raise AssertionError(args)

kept_import = source + "import pkg\n"
kept_diff = deletion(path, kept_import) + production_diff
assert not dead_test_candidates(kept_diff)
with patch.object(git, "git_try", side_effect=AssertionError("unexpected git")) as calls, patch(
        "lokay.checks.dead_tests", side_effect=AssertionError("unexpected proof")) as proof:
    result = weakened_tests(replace(x, diff=kept_diff))
    assert result.status == "fail"
    assert result.reason == "existing test changed but the issue body does not name it: " + path
    calls.assert_not_called()
    proof.assert_not_called()
with patch.object(git, "base_branch", return_value="main"), patch.object(git, "git_try", side_effect=fake_git), patch(
        "lokay.checks.dead_tests", return_value=frozenset()) as proof:
    assert weakened_tests(x).status == "fail"
    proof.assert_called_once()
with patch.object(git, "base_branch", return_value="main"), patch.object(git, "git_try", side_effect=fake_git):
    assert weakened_tests(x).status == "pass"
    result = weakened_tests(replace(x, issue_body="remove obsolete code", plan="pkg.gone"))
    assert result.status == "fail"
    assert result.reason == "existing test changed but the issue body does not name it: " + path
    base[path] += "import pkg\n"
    assert weakened_tests(x).status == "fail"
    base[path] = source
assert _count_weakened_tests(x).status == "fail"
assert _count_weakened_tests(x, frozenset({path})).status == "pass"
for failure in ((1, "", "failed"), RuntimeError("unavailable")):
    with patch.object(git, "base_branch", return_value="main"), patch.object(git, "git_try", side_effect=(
            failure if isinstance(failure, Exception) else lambda *args: failure)):
        assert weakened_tests(x).status == "fail"
with patch.object(git, "git_try", side_effect=AssertionError("unexpected git")), patch.object(
        git, "base_branch", side_effect=AssertionError("unexpected base branch")):
    assert weakened_tests(replace(x, diff=diff.replace("deleted file mode 100644\n", ""))).status == "fail"
print("dead test checks: green")
PY
uv run python - <<'PY'
from collections import Counter
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from lokay.checks import CheckInput, weakened_tests
from lokay.gates import dead_tests, moved_test_candidates, moved_tests
from lokay.lint import lint_diff, unit_test_hints

path = "tests/test_fala_store.py"
target = "tests/test_import.py"
imports = "import builtins\nimport pytest\n"
helper = ("def _block(monkeypatch):\n"
          "    original = builtins.__import__\n"
          "    monkeypatch.setattr(builtins, \"__import__\", original)\n")
import_test = ("def test_import_ok(monkeypatch):\n"
               "    # Given\n"
               "    _block(monkeypatch)\n"
               "    import pkg\n"
               "    assert pkg.__name__ == 'pkg'\n")
remaining = ("def test_requires(monkeypatch):\n"
             "    from pkg.fala import FalaStore\n"
             "    _block(monkeypatch)\n"
             "    assert FalaStore()\n"
             "def test_round_trip():\n"
             "    from pkg import Store\n"
             "    from pkg.fala import FalaStore\n"
             "    assert isinstance(FalaStore(), Store)\n")
base = {"src/pkg/__init__.py": "from pkg.protocols import Store\n",
        "src/pkg/protocols.py": "from typing import Protocol\nclass Store(Protocol):\n    def save(self): ...\n",
        "src/pkg/fala.py": "from pkg.protocols import Store\nclass FalaStore(Store): pass\nclass Backend: pass\n",
        path: imports + helper + import_test + remaining}
head = {name: source for name, source in base.items() if name != path}
head["src/pkg/fala.py"] = "from pkg.protocols import Store\nclass Backend: pass\n"
head[target] = imports + helper + import_test
body = ("Remove FalaStore from pkg.fala and delete tests/test_fala_store.py; "
        "move test_import_ok with _block to tests/test_import.py")

def change(before, after):
    old, new = before[path], after[target]
    return (f"diff --git a/{path} b/{path}\ndeleted file mode 100644\n"
            f"--- a/{path}\n+++ /dev/null\n@@ -1,{len(old.splitlines())} +0,0 @@\n"
            + "".join("-" + line + "\n" for line in old.splitlines())
            + f"diff --git a/{target} b/{target}\nnew file mode 100644\n"
            f"--- /dev/null\n+++ b/{target}\n@@ -0,0 +1,{len(new.splitlines())} @@\n"
            + "".join("+" + line + "\n" for line in new.splitlines())
            + "diff --git a/src/pkg/fala.py b/src/pkg/fala.py\n"
            "--- a/src/pkg/fala.py\n+++ b/src/pkg/fala.py\n@@ -1,3 +1,2 @@\n"
            " from pkg.protocols import Store\n"
            + "-" + before["src/pkg/fala.py"].splitlines()[1] + "\n"
            " class Backend: pass\n")

diff = change(base, head)
moved = moved_tests(diff, base, head, base.get, head.get)
assert moved_test_candidates(diff)
assert moved["names"] == {path: frozenset({"_block", "test_import_ok"})}
assert moved["added"] == {target: frozenset(range(1, len(head[target].splitlines()) + 1))}
assert moved["removed"] == {path: Counter((helper + import_test).splitlines())}
assert dead_tests(diff, body, base, head, base.get, head.get, moved=moved["names"]) == {path}
assert unit_test_hints(diff, moved["added"]) == {}
assert target in unit_test_hints(diff)
with patch("lokay.lint.git_output", side_effect=lambda cwd, args: head[args[-1].split(":", 1)[1]]):
    assert not any(target in error for error in lint_diff(diff, "head", Path.cwd(), False, neutral=moved["added"]))
    errors = lint_diff(diff, "head", Path.cwd(), False)
    assert any(target in error and "comment" in error for error in errors)
    assert any(target in error and "unit test" in error for error in errors)
x = CheckInput("owner/repo", 2245, "head", body, "", diff, [], {}, Path.cwd())
with patch("lokay.checks._revisions", return_value=(base, head, base.get, head.get)):
    assert weakened_tests(x).status == "pass"
changed_head = {**head, target: head[target].replace("== 'pkg'", "!= 'other'")}
changed_diff = change(base, changed_head)
rejected = moved_tests(changed_diff, base, changed_head, base.get, changed_head.get)
assert rejected == {"names": {}, "added": {}, "removed": {}}
assert target in unit_test_hints(changed_diff, rejected["added"])
assert not dead_tests(changed_diff, body, base, changed_head, base.get, changed_head.get, moved=rejected["names"])
with patch("lokay.checks._revisions", return_value=(base, changed_head, base.get, changed_head.get)), patch(
        "lokay.config.repo", return_value={}):
    assert weakened_tests(replace(x, diff=changed_diff)).status == "fail"
for before in (
        {**base, path: base[path] + "    from pkg.fala import Backend\n"},
        {**base, "src/pkg/fala.py": base["src/pkg/fala.py"].replace("FalaStore(Store)", "FalaStore")},
        {**base, path: base[path] + "    x = _block\n"}):
    negative = change(before, head)
    moves = moved_tests(negative, before, head, before.get, head.get)
    assert moves["names"] == moved["names"]
    assert not dead_tests(negative, body, before, head, before.get, head.get, moved=moves["names"])
docs = "docs/test_import.py"
docs_head = {name: source for name, source in head.items() if name != target}
docs_head[docs] = head[target]
docs_diff = diff.replace(target, docs)
docs_moves = moved_tests(docs_diff, base, docs_head, base.get, docs_head.get)
assert docs_moves["names"] == {}
assert docs in unit_test_hints(docs_diff, docs_moves["added"])
print("moved test checks: green")
PY
uv run python - <<'PY'
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from lokay.checks import CheckInput, weakened_tests
from lokay.gates import gate_contract, named_test
from lokay.h2 import LokayAdapter, run_issue
from lokay.safety import untrusted_issue_block

paths = ["tests/test_version.py", "tests/test_other.py", "src/x.py"]
body = "Update tests/test_version.py"
contract = gate_contract(paths, body)
assert contract.splitlines()[1] == "Existing test files you may change: tests/test_version.py"
assert gate_contract(paths, "Update behaviour").splitlines()[1] == "Existing test files you may change: none"
assert gate_contract(reversed(paths), body) == contract
assert gate_contract(paths, "test_other.py, test_version.py").splitlines()[1] == (
    "Existing test files you may change: tests/test_other.py, tests/test_version.py")
for path in ("tests/test_other.py", "tests/test_special[1].py"):
    name = Path(path).name
    diff = (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            "@@ -1 +1 @@\n-assert old\n+assert current\n")
    for text, expected in (("", False), (path, True), (name, True), (f"`{path}`", True),
                           (f"({name})", True), (f"prefix{name}", False),
                           (f"{path}.bak", False), (f"other/{name}", False),
                           (f"-{name}", False), (f"{name}_", False),
                           (f"/{path}", False), (f"{name}-suffix", False)):
        assert named_test(path, text) == expected, (path, text)
        with patch("lokay.config.repo", return_value={"test": ["pytest"]}), \
                patch("lokay.effects.tests.base_tests_on_head", return_value={"result": "green"}):
            x = CheckInput("owner/repo", 1, "head", text, "", diff, [],
                           {"result": "green", "sha": "head"}, Path.cwd())
            assert (weakened_tests(x).status == "fail") == (not named_test(path, text)), (path, text)
findings = [{"plik": "src/x.py", "zmiana": "repair"}]
for rows in (None, findings):
    with patch("lokay.h2.git.git", side_effect=["start-sha", "\n".join(paths)]) as tracked, \
            patch("lokay.h2.PiSubstrate"), patch("lokay.h2.Library"):
        adapter = LokayAdapter("owner/repo", 1, Path.cwd(), "HEAD", "Repair", body, findings=rows)
    assert tracked.call_args_list == [call(Path.cwd(), "rev-parse", "HEAD"),
                                     call(Path.cwd(), "ls-tree", "-r", "--name-only", "start-sha")]
    prefix = untrusted_issue_block("Repair", body) + "\n\n" + contract
    assert adapter.prompt.startswith(prefix)
    if rows is not None:
        assert adapter.prompt[len(prefix):].startswith("\n\nCheck findings:\n")
    else:
        assert adapter.prompt == prefix
prompt = "PROMPT\n=== GATE CONTRACT (lokay; overrides the issue where they conflict) ===\nX\n=== END GATE CONTRACT ==="
for rows in (None, findings):
    adapter = MagicMock()
    adapter.prompt = prompt
    adapter.substrate.preflight.side_effect = RuntimeError("stop")
    with patch("lokay.h2.LokayAdapter", return_value=adapter), \
            patch("lokay.h2.store.rounds_append") as rounds_append, \
            patch("lokay.h2.start_harness_run"):
        try:
            run_issue("owner/repo", 1, Path.cwd(), "HEAD", "Repair", body, findings=rows)
        except RuntimeError as error:
            assert str(error) == "stop"
        assert rounds_append.call_args_list == [
            call("owner/repo", 1, ("Fix" if rows is not None else "Build") + " prompt:\n" + prompt)]
print("gate contract checks: green")
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
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay.checks import CheckInput, intent, run_checks
from lokay.retro import CATEGORIES
from lokay.types import Finding

diff = ("diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n"
        "@@ -1 +1 @@\n-old\n+new\n")
with TemporaryDirectory() as directory:
    x = CheckInput("owner/repo", 1, "head", "", "", diff, [], {}, Path(directory),
                   title="[code-audit] X")
    result = intent(x)
    assert result.status == "fail", result
    assert "docs/plan only instead of code" in result.reason, result
    assert result.findings == (Finding("README.md", 1, 1,
        "issue needs a code change; implement it instead of editing docs", "intent"),)
    with patch("lokay.effects.git.merge_conflicts", return_value=[]), \
            patch("lokay.lint.git_output", return_value=""):
        assert any(row.name == "intent" and row.status == "fail" for row in run_checks(x))
    assert intent(replace(x, diff=diff.replace("README.md", "src/x.py"))).status == "pass"
    assert intent(replace(x, title="", red_main=True,
                          diff=diff.replace("README.md", "docs/plan.md"))).status == "fail"
    docs = replace(x, title="[docs-audit] X")
    assert intent(docs).status == "pass"
    assert intent(replace(docs, issue_body="Change src/x.py and Tests/A.swift",
                          plan="Change src/x.py and Tests/A.swift")).status == "pass"
    assert intent(replace(x, diff="")).status == "pass"
assert "docs/plan only instead of code" in CATEGORIES
print("intent check: green")
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
                    "--state", "closed", "--limit", "100", "--json", "number,mergedAt,closedAt"]
    return {"lokay/2": [{"number": 22, "mergedAt": None}],
            "lokay/3": [{"number": 33, "mergedAt": "2026-10-21T09:00:00Z"}]}[branch]

with patch.object(tick, "state_read", side_effect=read), \
        patch.object(tick, "state_update", side_effect=update), \
        patch.object(tick, "list_prs", return_value=[]) as prs, \
        patch.object(tick, "gh_json", side_effect=remote), \
        patch.object(tick, "pr_closed_by_factory", return_value=True):
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
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import graph, store, tick
from lokay.effects import gh
from lokay.types import Run, parse_event

name = "owner/human-close"
for nodes, expected in (([{"actor": {"login": "factory"}}], True),
                        ([{"actor": {"login": "human"}}], False), ([], False)):
    payload = {"data": {"viewer": {"login": "factory"}, "repository": {
        "pullRequest": {"timelineItems": {"nodes": nodes}}}}}
    with patch.object(gh, "gh_json", return_value=payload) as query:
        assert gh.pr_closed_by_factory(name, 7) is expected
        query.assert_called_once()

for factory in (True, False):
    states = {1: {"result": "closed", "node": "check", "pr": 7}}
    events = []
    def update(repo, issue, **fields):
        event = {"ts": 1, **fields.pop("_event"), "fields": fields}
        states[issue] = graph.step(Run.from_state(states[issue]), parse_event(event)).state
        events.append(event)
    with patch.object(tick, "state_read", side_effect=lambda repo, issue: states[issue]), \
            patch.object(tick, "state_update", side_effect=update), \
            patch.object(tick, "list_prs", return_value=[]), \
            patch.object(tick, "gh_json", return_value=[
                {"number": 7, "mergedAt": None, "closedAt": "2026-10-21"},
                {"number": 8, "mergedAt": None, "closedAt": "2026-10-20"}]), \
            patch.object(tick, "pr_closed_by_factory", side_effect=lambda repo, pr: factory if pr == 7 else not factory):
        reopened = set()
        for _ in range(2):
            tick.reopen_closed_issues(name, [{"number": 1}], reopened)
        assert [event["action"] for event in events] == (["reopened"] if factory else [])

for factory in (True, False):
    for polling in (True, False):
        with TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            for key, value in (("HOME", root), ("RUNS", root / "runs"), ("LOCKS", root / "locks")):
                stack.enter_context(patch.object(store, key, value))
            config = {"name": name, "clone_path": str(root / "absent"), "merge": "off"}
            stack.enter_context(patch.object(tick.maintenance, "sweep"))
            stack.enter_context(patch.object(tick, "probes", return_value={"host": "ok"}))
            stack.enter_context(patch.object(tick, "load_repos", return_value=[config]))
            stack.enter_context(patch.object(tick, "list_prs", return_value=[]))
            stack.enter_context(patch.object(tick, "open_issues", return_value=[{"number": 1, "state": "OPEN"}]))
            stack.enter_context(patch.object(tick, "open_pr_for", return_value=None))
            stack.enter_context(patch.object(tick, "pr_closed_by_factory", return_value=factory))
            plan = stack.enter_context(patch.object(tick, "_prepare", side_effect=AssertionError("unexpected Plan")))
            def remote(args, **kwargs):
                if args[:2] == ["api", "graphql"]:
                    return {"data": {"repository": {"issue_1": {"state": "OPEN"}, "pr_7": {"state": "CLOSED"}}}}
                assert args[:2] == ["pr", "list"] and "closed" in args
                return [{"number": 6, "mergedAt": None, "closedAt": "2026-10-20"},
                        {"number": 7, "mergedAt": None, "closedAt": "2026-10-21"}]
            stack.enter_context(patch.object(tick, "gh_json", side_effect=remote))
            store.state_update(name, 1, _event={"action": "enter_node", "outcome": {"node": "plan"}},
                               result="check", pr=7 if polling else None)
            updates = stack.enter_context(patch.object(tick, "state_update", wraps=store.state_update))
            picked = tick.pick({"LOKAY2_REPO": name, "LOKAY2_ISSUE": "1"})
            events = [call.kwargs for call in updates.call_args_list if "_event" in call.kwargs]
            if factory:
                assert picked["result"] == "picked" and picked["node"] == "plan", picked
                tick.release_lock(picked["held"])
                if polling:
                    assert events[0]["_event"]["action"] == "reopened", events
            else:
                assert picked["result"] == "idle", picked
                assert [event["_event"]["action"] for event in events] == ["closed"], events
                assert "closed_on_github" not in events[0]
                assert store.state_read(name, 1)["result"] == "closed"
                updates.reset_mock()
                assert tick.pick({"LOKAY2_REPO": name, "LOKAY2_ISSUE": "1"})["result"] == "idle"
                updates.assert_not_called()
            plan.assert_not_called()
print("human close checks: green")
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
from unittest.mock import patch

from lokay import store, tick

now = 1_800_000_000
picked = {"repo": "owner/repo", "issue": 1}
for age, idle, expected in ((8 * 3600, 8 * 3600, None),
                             (7 * 3600, 60, {"result": "pending", "next": "plan"})):
    saved = {"node": "fix", "result": "pending", "diff_changed_at": now - age,
             "last_attempt": now - idle}
    fields = store.pick_ladder_fields(saved, now)
    assert abs(fields["ladder_since"] - (now - age + idle)) <= 1, fields
    saved.update(fields, last_attempt=now)
    repeated = store.pick_ladder_fields(saved, now)
    assert abs(repeated["ladder_since"] - fields["ladder_since"]) <= 1, repeated
    with patch("lokay.tick.time.time", return_value=now), \
         patch.dict("os.environ", {"LOKAY2_LADDER_HOURS": "6"}), \
         patch("lokay.tick.state_read", return_value=saved), \
         patch("lokay.tick.state_update") as update, \
         patch("lokay.tick.rounds_append"), \
         patch("lokay.tick.replan_prompt", return_value="replan"):
        result = tick.escalate(picked)
    assert result == expected, result
    if expected is None:
        update.assert_not_called()
    else:
        assert update.call_args.kwargs["_event"]["outcome"]["node"] == "plan"
assert store.pick_ladder_fields({"last_attempt": now - 3600}, now) == {}
assert store.pick_ladder_fields({"diff_changed_at": now - 3600}, now) == {}
print("ladder wait checks: green")
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
    if args[:2] == ["issue", "view"]:
        return {"title": "Restore content", "body": "Restore keep.txt"}
    if args[:2] == ["api", "graphql"]:
        assert "prc_" not in " ".join(args), args
        return {"data": {"repository": {"issue_1": {"state": remote_issue}, "pr_7": {"state": "CLOSED"}}}}
    assert args[:2] == ["pr", "list"], args
    if "closed" in args:
        assert args[args.index("--json") + 1] == "number,mergedAt,closedAt", args
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
    stack.enter_context(patch.object(tick, "pr_closed_by_factory", return_value=True))
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
import os
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import store, tick

class Prepared(Exception):
    pass

with TemporaryDirectory() as directory, ExitStack() as stack:
    state_dir = Path(directory)
    stack.enter_context(patch.dict(os.environ, {"LOKAY_STATE_DIR": directory}))
    for key, value in (("HOME", state_dir), ("RUNS", state_dir / "runs"), ("LOCKS", state_dir / "locks")):
        stack.enter_context(patch.object(store, key, value))
    name = "owner/refresh"
    config = {"name": name, "clone_path": directory, "merge": "off"}
    stack.enter_context(patch.object(tick, "repo_config", return_value=config))
    stack.enter_context(patch.object(tick, "_repo_paths", return_value=(state_dir, state_dir)))
    stack.enter_context(patch.object(tick, "_ensure_worktree", side_effect=Prepared))
    remote = stack.enter_context(patch.object(tick, "gh_json", return_value={"title": "Title", "body": "Body"}))
    updates = stack.enter_context(patch.object(tick, "state_update", wraps=store.state_update))
    for issue, title, body, changed in (
        (1, "Title", "Old body", True),
        (2, "Title", "Body", False),
        (3, "Title", "Body" + tick.RECOVERY_EVIDENCE + "{}", False),
        (4, "Old title", "Body", True),
    ):
        store.state_update(name, issue, issue_title=title, issue_body=body,
                           difficulty="easy", pr=None, plan_prompt="old prompt")
        before = store.state_read(name, issue)
        updates.reset_mock()
        remote.reset_mock()
        try:
            tick._prepare({"repo": name, "issue": issue})
        except Prepared:
            pass
        else:
            raise AssertionError("Prepare did not reach worktree setup")
        remote.assert_called_once_with(
            ["issue", "view", str(issue), "--repo", name, "--json", "title,body"],
            error="issue view failed")
        saved = store.state_read(name, issue)
        rounds = store.run_dir(name, issue) / "rounds.md"
        line = "Plan: issue changed on GitHub; refreshed issue text and reset plan prompt"
        if changed:
            assert saved["issue_title"] == "Title", saved
            assert saved["issue_body"] == "Body", saved
            assert saved["plan_prompt"] is None, saved
            assert line in rounds.read_text()
        else:
            assert saved == before, saved
            updates.assert_not_called()
            assert not rounds.exists() or line not in rounds.read_text()
print("issue refresh checks: green")
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
        ("printf \"LOKAY_TEST_CWD=%s\\n=== FAILURES ===\\n"
         "E       FileNotFoundError: [Errno 2] No such file or directory: 'x'\\n"
         "=== short test summary info ===\\nFAILED t.py::a\\n1 failed, 5 passed\\n\" \"$PWD\"; exit 1",
         "red", True, False),
        ("printf \"LOKAY_TEST_CWD=%s\\n=== ERRORS ===\\n"
         "E       FileNotFoundError: [Errno 2] No such file or directory: 'x'\\n"
         "=== short test summary info ===\\n5 passed\\n\" \"$PWD\"; exit 1",
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
uv run python - <<'PY'
from difflib import unified_diff
from pathlib import Path
from unittest.mock import patch

from lokay.checks import CheckInput, no_new_comments
from lokay.lint import lint_diff

for suffix in (".mojo", ".🔥"):
    path = f"mojo/takt/plant{suffix}"
    for delimiter in ('"""', "'''"):
        module = (delimiter + "\nPlant metadata.\n\n"
                  "Each node may carry parent_id, layer, and kind so hosts can model documents,\n"
                  "code trees, and multi-layer cascades without domain parsers inside takt.\n"
                  + delimiter + "\nvar n = 1\n")
        changed = module.replace(
            "Each node may carry parent_id, layer, and kind so hosts can model documents,\n"
            "code trees, and multi-layer cascades without domain parsers inside takt.\n",
            "Each node may carry parent_id, layer, and kind as host metadata.\n"
            "TreeNode.layer does not select a regulator; evaluation starts at the chain root.\n")
        function = f"fn run():\n    {delimiter}\n    Old text.\n    {delimiter}\n    pass\n"
        cases = (
            ("", "# comment\n", "fail", None),
            ("# old comment\n", "# new comment\n", "fail", None),
            ("", module, "fail", 1),
            (module, changed, "fail", 1),
            (function, function.replace("Old text.", "New text."), "fail", 2),
            ("# comment\n", "", "pass", None),
            (module, "var n = 1\n", "pass", None),
            (module, module.replace("Plant metadata.\n", ""), "pass", None),
            (module, module.replace("var n = 1", "var n = 2"), "pass", None),
            ("", f"var s = {delimiter}text{delimiter}\n", "pass", None),
            ("", f"{delimiter}text{delimiter}\n", "fail", 1),
        )
        for before, after, expected, start in cases:
            diff = "".join(unified_diff(before.splitlines(True), after.splitlines(True),
                                        fromfile=f"a/{path}", tofile=f"b/{path}", n=0))
            x = CheckInput("owner/repo", 1, "head", "", "", diff, [], {}, Path.cwd())
            with patch("lokay.lint.git_output", return_value=after):
                errors = lint_diff(diff, x.sha, x.worktree, lokay_rules=False)
                result = no_new_comments(x)
            assert errors == ([f"{path}:{start}: docstring -> delete it"] if start else []), errors
            assert result.status == expected, (diff, result)
print("mojo comment checks: green")
PY
uv run python - <<'PY'
import os
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import call, patch

from lokay import plan, store, tick
from lokay.effects import gh, git

with TemporaryDirectory(prefix="lokay-split-checks-") as temporary, ExitStack() as stack:
    directory = Path(temporary)
    stack.enter_context(patch.dict(os.environ, {"LOKAY_STATE_DIR": str(directory)}))
    for key, value in (("HOME", directory), ("RUNS", directory / "runs"), ("LOCKS", directory / "locks")):
        stack.enter_context(patch.object(store, key, value))
    name = "owner/split"
    root = directory / "clone"
    config = {"name": name, "clone_path": str(root)}
    tasks = [{"title": "First task", "body": "Implement first part"},
             {"title": "Second task", "body": "Implement second part"}]
    stack.enter_context(patch.object(tick, "repo_config", return_value=config))
    stack.enter_context(patch.object(tick, "gh_json", return_value={"title": "Parent", "body": "Implement both parts"}))
    setup = stack.enter_context(patch.object(git, "ensure_worktree", side_effect=RuntimeError("repository top-level mismatch")))
    checkout = stack.enter_context(patch.object(git, "plan_checkout", return_value=root))
    split = stack.enter_context(patch.object(plan, "split_tasks", return_value={"result": "done", "tasks": tasks}))
    child = stack.enter_context(patch.object(gh, "create_child_issue", side_effect=[101, 102, 201, 202]))
    for issue, resumed, children in ((1, False, [101, 102]), (2, True, [201, 202])):
        store.state_update(name, issue, difficulty="too_big", **({"split_tasks": tasks} if resumed else {}))
        picked = {"repo": name, "issue": issue, "node": "plan"}
        outcome = tick._prepare(picked)
        assert outcome == {"result": "pending", "children": children}, outcome
        saved = store.state_read(name, issue)
        assert saved["children"] == children and saved["awaiting"] == "children", saved
        assert child.call_args_list == [call(name, issue, index, task, 0) for index, task in enumerate(tasks)]
        child.reset_mock()
        setup.assert_not_called()
        if resumed:
            split.assert_not_called()
            checkout.assert_not_called()
        else:
            split.assert_called_once_with(plan.prompt_for("Parent", "Implement both parts"),
                                          store.run_dir(name, issue) / "split.json", cwd=root)
            checkout.assert_called_once_with(root)
        split.reset_mock()
        checkout.reset_mock()
    store.state_update(name, 3, difficulty="easy")
    try:
        tick._prepare({"repo": name, "issue": 3, "node": "plan"})
    except RuntimeError as exc:
        assert str(exc) == "repository top-level mismatch", exc
    else:
        raise AssertionError("Build skipped worktree setup")
    setup.assert_called_once_with(root, "lokay/3", directory / "clone-wt-3")
    split.assert_not_called()
    child.assert_not_called()
print("split before worktree checks: green")
PY
uv run python - <<'PY'
import json
import os
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import plan, store, tick
from lokay.effects import decide, gh, git

with TemporaryDirectory(prefix="lokay-issue-only-checks-") as temporary, ExitStack() as stack:
    directory = Path(temporary)
    stack.enter_context(patch.dict(os.environ, {"LOKAY_STATE_DIR": str(directory)}))
    for key, value in (("HOME", directory), ("RUNS", directory / "runs"), ("LOCKS", directory / "locks")):
        stack.enter_context(patch.object(store, key, value))
    name = "owner/issue-only"
    fields = {"pr": 7, "difficulty": "too_big", "awaiting": "children", "children": [8],
              "split_tasks": [{"title": "Part", "body": "Implement part"}], "node": "fix", "result": "pending"}
    store.save_run(name, 1, dict(fields))
    path = store.run_dir(name, 1) / "state.json"
    expected = {**fields, "difficulty": "hard"}
    assert json.loads(path.read_text()) == expected
    store.state_update(name, 1, difficulty="too_big")
    assert json.loads(path.read_text())["difficulty"] == "hard"
    store.write_json(path, fields)
    saved = store.state_read(name, 1)
    assert {key: saved[key] for key in fields} == expected, saved
    for state, difficulty in (({"difficulty": "hard", "pr": 7}, "hard"),
                              ({"difficulty": "too_big", "pr": 7}, "hard"),
                              ({"difficulty": "hard"}, "too_big"),
                              ({"difficulty": "hard", "pr": None}, "too_big")):
        assert store.escalation_fields(state)["difficulty"] == difficulty, state
    root = directory / "clone"
    tasks = [{"title": "First task", "body": "Implement first part"},
             {"title": "Second task", "body": "Implement second part"}]
    stack.enter_context(patch.object(tick, "repo_config", return_value={"name": name, "clone_path": str(root)}))
    stack.enter_context(patch.object(tick, "gh_json", return_value={"title": "Parent", "body": "Implement both parts"}))
    setup = stack.enter_context(patch.object(git, "ensure_worktree", side_effect=RuntimeError("worktree reached")))
    stack.enter_context(patch.object(git, "plan_checkout", return_value=root))
    split = stack.enter_context(patch.object(plan, "split_tasks", return_value={"result": "done", "tasks": tasks}))
    child = stack.enter_context(patch.object(gh, "create_child_issue", side_effect=[101, 102]))
    store.state_update(name, 2, difficulty="too_big")
    outcome = tick._prepare({"repo": name, "issue": 2, "node": "plan"})
    assert outcome == {"result": "pending", "children": [101, 102]}, outcome
    setup.assert_not_called()
    split.assert_called_once()
    assert child.call_count == 2
    stack.enter_context(patch.object(decide, "decide", return_value={"difficulty": {"choice": "too_big"}}))
    store.state_update(name, 3, pr=9)
    setup.side_effect = [{"result": "added"}, RuntimeError("worktree reached")]
    try:
        tick._prepare({"repo": name, "issue": 3, "node": "plan"})
    except RuntimeError as exc:
        assert str(exc) == "worktree reached", exc
    else:
        raise AssertionError("Build skipped worktree setup")
    saved = store.state_read(name, 3)
    assert saved["difficulty"] == saved["difficulty_decision"]["choice"] == "hard", saved
print("issue-only too_big checks: green")
PY
uv run python - <<'PY'
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock

from harness2.core.library import Library

from lokay import h2, store

base = (h2.BASE / "AGENTS.md").read_text()
comments = next(line for line in base.splitlines() if line.startswith("No new comments"))
docs = next(line for line in base.splitlines() if line.startswith("Docs describe"))
drifted = base.replace(comments, "No unsolicited comments, docstrings, test files, or unit test functions. "
                       "When the issue requests tests, persist them in the named test file...")
drifted_docs = base.replace(docs, "Add requested documentation without deleting unrelated, nonduplicate contracts.")
adapter = h2.LokayAdapter.__new__(h2.LokayAdapter)
for text, missing in (("", None), (drifted, comments), (drifted_docs, docs)):
    try:
        adapter.validate_tree({"AGENTS.md": text})
    except ValueError as exc:
        assert missing in str(exc) if missing else "nonempty" in str(exc), exc
    else:
        raise AssertionError("Invalid harness instructions accepted")
adapter.validate_tree({"AGENTS.md": base + "\nRead the repository skill before editing.\n"})
with TemporaryDirectory(prefix="lokay-harness-rule-checks-") as temporary:
    root = Path(temporary)
    adapter.library = Library(root / "library", "owner__repo", h2.PI_SURFACE)
    older = adapter.library.entry_dir("older")
    newer = adapter.library.entry_dir("newer")
    store.write_artifact(older / "harness/AGENTS.md", base)
    store.write_artifact(newer / "harness/AGENTS.md", drifted)
    os.utime(older, ns=(1000000000, 1000000000))
    os.utime(newer, ns=(2000000000, 2000000000))
    assert adapter.base_harness() == older / "harness"
    store.write_artifact(older / "harness/AGENTS.md", drifted_docs)
    assert adapter.base_harness() == h2.BASE
    assert (newer / "harness/AGENTS.md").read_text() == drifted
    assert (older / "harness/AGENTS.md").read_text() == drifted_docs
    adapter.spec = SimpleNamespace(runs_root=root / "runs")
    adapter.substrate = Mock()
    try:
        adapter.execute("owner/repo#1", newer / "harness", "rule-checks")
    except ValueError as exc:
        assert comments in str(exc), exc
    else:
        raise AssertionError("Drifted harness execution accepted")
    adapter.substrate.materialise.assert_not_called()
    adapter.substrate.execute.assert_not_called()
print("harness rule checks: green")
PY
.venv/bin/python - <<'PY'
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from lokay import store
from lokay.effects.git import git
from lokay.finish import assertion_base_violations

os.environ.update(GIT_AUTHOR_NAME="mikolaj92", GIT_AUTHOR_EMAIL="check@example.invalid",
                  GIT_COMMITTER_NAME="mikolaj92", GIT_COMMITTER_EMAIL="check@example.invalid",
                  GIT_AUTHOR_DATE="2025-01-01T00:00:00+00:00", GIT_COMMITTER_DATE="2025-01-01T00:00:00+00:00")
with TemporaryDirectory(prefix="lokay-fix-assertion-base-checks-") as temporary:
    repo = Path(temporary)
    git(repo, "init", "-b", "main")
    test = repo / "test_example.py"
    source = repo / "example.py"
    base_text = "assert True\nassert 1 == 1\n"
    store.write_artifact(test, base_text)
    store.write_artifact(source, "assert True\n")
    git(repo, "add", "--", test.name, source.name)
    git(repo, "commit", "-m", "base")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    store.write_artifact(test, base_text + "assert 2 == 2\nassert 3 == 3\nassert 4 == 4\n")
    git(repo, "commit", "-am", "PR assertions")
    sha = git(repo, "rev-parse", "HEAD")
    base_revision = git(repo, "merge-base", "origin/main", sha)
    for text, expected in ((base_text, {}), ("assert True\n", {test.name: 1})):
        store.write_artifact(test, text)
        patch = git(repo, "diff", "HEAD", "--", test.name)
        assert assertion_base_violations(repo, base_revision, patch) == expected
    store.write_artifact(source, "")
    patch = git(repo, "diff", "HEAD", "--", source.name)
    assert assertion_base_violations(repo, base_revision, patch) == {}
print("fix assertion base checks: green")
PY
uv run python - <<'PY'
import gzip
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import observe

script = Path("scripts/lokay-service.sh").read_text()
path_line = next(line for line in script.splitlines() if line.startswith("export PATH="))
loop = script[script.index("while true; do"):]
assert 'if [[ "$LOKAY2_WORKER" == "0" ]]; then\n    monitor_ticks=' in loop
assert 'if (( monitor_ticks % monitor_every == 0 )); then\n      run_child "$ROOT/.venv/bin/lokay" monitor' in loop
assert loop.index('" monitor </dev/null') < loop.rindex('run_child sleep "$LOKAY_TICK_SECONDS"')
validation = script[script.index("monitor_ticks=0"):script.index('active=""')]
rejected = subprocess.run(["/bin/bash", "-c", validation], env={"LOKAY_MONITOR_TICKS": "0"},
                          capture_output=True, text=True)
assert rejected.returncode == 64 and "LOKAY_MONITOR_TICKS" in rejected.stderr, rejected
with TemporaryDirectory() as directory:
    root = Path(directory)
    ticks = root / "ticks"
    ticks.mkdir()
    now = 1_800_000_000
    def transition(ts, reason):
        return {"kind": "transition", "repo": "owner/repo", "issue": 7,
                "before": {"node": "fix"},
                "event": {"action": "needs_help", "ts": ts, "reason": reason}}
    older = ticks / "2026-10-19.jsonl"
    older.write_text(json.dumps(transition(now + 1000, "older file")) + "\n")
    newest_help = ticks / "2026-10-20.jsonl.gz"
    with gzip.open(newest_help, "wt") as stream:
        stream.write("broken\n" + json.dumps(transition(now - 20, "latest help")) + "\n"
                     + json.dumps(transition(now - 30, "earlier help")) + "\n")
    newest = ticks / "2026-10-21.jsonl"
    newest.write_text('{"kind": "other"}\n')
    opened = []
    original_open = open
    def tracked_open(path, *args, **kwargs):
        path = Path(path)
        assert path != older, "older tick file was read"
        opened.append(path)
        return original_open(path, *args, **kwargs)
    with patch.object(observe, "HOME", root), patch.object(observe, "RUNS", root / "runs"), \
            patch.object(observe.time, "time", return_value=now), \
            patch.dict(os.environ, {"LOKAY_ALARM_REPO": "mikolaj92/lokay", "LOKAY_HEARTBEAT_MINUTES": "5"}), \
            patch("builtins.open", side_effect=tracked_open):
        help_result = observe.latest_needs_help()
        assert help_result["latest_needs_help"]["event"]["reason"] == "latest help", help_result
        assert help_result["unreadable_records_or_files"] == 1, help_result
        assert opened == [newest, newest_help], opened
        beat = {"time": datetime.fromtimestamp(now - 600, timezone.utc).isoformat()}
        (root / "heartbeat.json").write_text(json.dumps(beat))
        with patch.object(observe, "gh_json", return_value=[]) as lookup, \
                patch.object(observe, "gh_ok") as action:
            result = observe.monitor()
            assert result["result"] == "stalled", result
            action.assert_called_once()
            args = action.call_args.args[0]
            assert args[:2] == ["issue", "create"], args
            assert args[args.index("--repo") + 1] == "mikolaj92/lokay", args
            assert args[args.index("--title") + 1] == "lokay-stalled", args
            body = args[args.index("--body") + 1]
            assert all(reason in body for reason in result["reasons"]), body
            assert "latest help" in body and beat["time"] in body, body
            lookup.return_value = [{"number": 42, "title": "lokay-stalled"}]
            action.reset_mock()
            assert observe.monitor()["result"] == "stalled"
            action.assert_not_called()
            beat["time"] = datetime.fromtimestamp(now, timezone.utc).isoformat()
            (root / "heartbeat.json").write_text(json.dumps(beat))
            assert observe.monitor() == {"result": "ok", "closed": [42]}
            action.assert_called_once()
            args = action.call_args.args[0]
            assert args[:3] == ["issue", "close", "42"], args
            assert beat["time"] in args[args.index("--comment") + 1], args
    command = path_line + '\nprintf "%s" "$PATH"'
    first = subprocess.check_output(["/usr/bin/env", "-i", f"HOME={root}", "PATH=/usr/bin:/bin",
                                     "/bin/bash", "-c", command], text=True)
    second = subprocess.check_output(["/usr/bin/env", "-i", f"HOME={root}", f"PATH={first}",
                                      "/bin/bash", "-c", command], text=True)
    assert "/usr/sbin" in first.split(":") and "/sbin" in first.split(":"), first
    assert first == second and len(first.split(":")) == len(set(first.split(":"))), (first, second)
print("monitor loop checks: green")
PY
uv run python - <<'PY'
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import build, checks, graph, main_guard, setup, store, tick
from lokay.effects import git as git_effects
from lokay.types import CheckResult, RepoSnapshot, Snapshot

name = "mikolaj92/Temida"
now = 10000
for age in (3599, 3600, 3601):
    snapshot = Snapshot(repos=(RepoSnapshot(
        name=name, status={"status": "unknown", "since": now - age, "issue": 7},
        prs=(), issues=(), states={7: {"result": "running", "node": "build"}}),), now=now)
    picked = graph.pick(snapshot)
    assert (picked is not None and picked.kind == "red_main") == (age >= 3600), picked

with TemporaryDirectory() as directory, ExitStack() as stack:
    root = Path(directory)
    for key, value in (("HOME", root), ("RUNS", root / "runs"), ("LOCKS", root / "locks")):
        stack.enter_context(patch.object(store, key, value))
    config = {"name": name, "clone_path": str(root), "merge": "on", "test": ["checks"]}
    stack.enter_context(patch.object(tick.maintenance, "sweep"))
    stack.enter_context(patch.object(tick, "probes", return_value={"host": "ok"}))
    stack.enter_context(patch.object(tick, "load_repos", return_value=[config]))
    stack.enter_context(patch.object(tick, "list_prs", return_value=[]))
    stack.enter_context(patch.object(tick, "open_issues", return_value=[]))
    guard = stack.enter_context(patch.object(main_guard, "check_main"))
    assert tick.pick({})["result"] == "idle"
    assert guard.call_args.args[:2] == (name, root), guard.call_args
    assert guard.call_args.kwargs["force"] is True

ci = {"result": "red", "tested": True, "executed": 1, "failed": [], "log": "setup log evidence"}
lock = {"status": "pass", "reason": "lockfile evidence", "findings": [], "name": "lockfile"}
baseline = {"sha": "head", "argv": ["checks"], "ci": ci, "lockfile": lock}
main = {"status": "red", "baseline": baseline, "issue": 7, "culprit": {"sha": "merge", "pr": 42}}
for scenario in ("revert", "no culprit", "parent red", "setup", "lock", "exhausted", "green"):
    with TemporaryDirectory() as directory, ExitStack() as stack:
        root = Path(directory)
        for key, value in (("HOME", root), ("RUNS", root / "runs"), ("LOCKS", root / "locks")):
            stack.enter_context(patch.object(store, key, value))
        artifact = root / "empty.patch"
        store.write_artifact(artifact, "")
        context = hashlib.sha256(json.dumps(["repair", "spec", "easy", []]).encode()).hexdigest()
        store.state_update(name, 7, awaiting="children", children=[11, 12], result="pending")
        store.state_update(name, 12, _event={"action": "closed"})
        store.state_update(name, 11, issue_title="repair", issue_body="spec", difficulty="easy",
                           h2_context=context, h2_patch=str(artifact), h2_start="start",
                           h2_all_ran=True, h2_summary="complete",
                           recovery_sha="head" if scenario == "exhausted" else None)
        status = deepcopy(main)
        if scenario == "no culprit":
            status["culprit"] = None
        if scenario == "green":
            status["status"] = "green"
        if scenario == "setup":
            status["baseline"]["ci"]["failed"] = [{"warstwa": "setup"}]
        if scenario == "lock":
            status["baseline"]["lockfile"]["status"] = "fail"
        store.save_main_status(name, status)
        def diagnose(repo, clone, **kwargs):
            assert kwargs["force"] is True
            revision = kwargs.get("revision")
            if revision:
                return {"status": "red" if revision == "merge" or scenario == "parent red" else "green",
                        "baseline": deepcopy(baseline)}
            return status
        guard = stack.enter_context(patch.object(main_guard, "check_main", side_effect=diagnose))
        stack.enter_context(patch.object(tick, "repo_config", return_value={"test": ["checks"]}))
        stack.enter_context(patch.object(tick, "_repo_paths", return_value=(root, root)))
        stack.enter_context(patch.object(tick, "_ensure_worktree"))
        stack.enter_context(patch.object(tick, "check_deadline"))
        stack.enter_context(patch.object(tick, "base_branch", return_value="main"))
        stack.enter_context(patch.object(git_effects, "git_try", return_value=(0, "", "")))
        def git(path, *args, **kwargs):
            if args[0] == "rev-list":
                return "merge parent other"
            if args[0] == "diff":
                return "revert patch"
            assert args == ("revert", "--no-commit", "-m", "1", "merge"), args
            return ""
        commands = stack.enter_context(patch.object(tick, "git", side_effect=git))
        stack.enter_context(patch.object(tick, "git_head", return_value="revert-sha"))
        commit = stack.enter_context(patch.object(build, "tidy_and_commit"))
        stack.enter_context(patch.object(tick, "open_pr_for", return_value=None))
        stack.enter_context(patch.object(build, "build_publish", return_value={"result": "pr_open", "sha": "revert-sha", "pr": 99}))
        stack.enter_context(patch.object(tick, "_retry", side_effect=lambda picked, node, fn, *args: fn()))
        remote = stack.enter_context(patch.object(tick, "gh_ok"))
        stack.enter_context(patch.object(tick, "gh_json", return_value={"title": "repair", "body": "spec"}))
        result = tick._prepare({"repo": name, "issue": 11})
        saved = store.state_read(name, 11)
        if scenario == "revert":
            assert isinstance(result, tuple), result
            assert saved["h2_committed"] == "revert-sha" and saved["node"] == "check", saved
            assert saved["h2_summary"] == "Revert culprit PR #42", saved
            commit.assert_called_once_with(root, "Revert culprit PR #42")
            assert artifact.read_text() == "revert patch"
            assert [call.kwargs.get("revision") for call in guard.call_args_list] == [None, "merge", "merge^1"]
        elif scenario == "exhausted":
            assert result["result"] == "closed" and saved["recovery_exhausted"], (result, saved)
            assert store.state_read(name, 7)["recovery_exhausted"]
            exhausted = store.main_status()[name]
            assert exhausted["exhausted_sha"] == "head", exhausted
            snapshot = Snapshot(repos=(RepoSnapshot(name=name, status=exhausted, prs=(),
                issues=({"number": 20},), states={7: store.state_read(name, 7), 11: saved, 20: {}}),), now=now)
            assert graph.pick(snapshot).issue == 20
            remote.assert_called_once()
        elif scenario == "green":
            assert result["result"] == "closed" and saved["closed_on_github"], (result, saved)
            assert "main green" in result["reason"]
            remote.assert_called_once()
        else:
            assert result == {"result": "pending", "next": "build"}, result
            assert saved["node"] == "build" and saved["recovery_sha"] == "head", saved
            assert "setup log evidence" in saved["issue_body"] and "lockfile evidence" in saved["issue_body"]
            commit.assert_not_called()
            remote.assert_not_called()

with TemporaryDirectory() as directory, ExitStack() as stack:
    root = Path(directory)
    for key, value in (("HOME", root), ("RUNS", root / "runs"), ("LOCKS", root / "locks")):
        stack.enter_context(patch.object(store, key, value))
    current_sha = "head"
    def git(path, *args, **kwargs):
        if args[0] == "rev-parse":
            return "parent" if args[1] == "merge^1" else current_sha
        return ""
    commands = stack.enter_context(patch.object(main_guard, "git", side_effect=git))
    stack.enter_context(patch.object(main_guard, "worktree_remove", return_value={"result": "removed"}))
    stack.enter_context(patch.object(setup, "prepare_dependencies", return_value={"log": "setup"}))
    tests = stack.enter_context(patch.object(main_guard, "run_repo_tests", side_effect=lambda *args: deepcopy(ci)))
    stack.enter_context(patch.object(checks, "lockfile", return_value=CheckResult("lockfile", "pass", "lockfile evidence", [])))
    lookup = stack.enter_context(patch.object(main_guard, "gh_json", return_value=[
        {"number": 42, "merged_at": "today", "merge_commit_sha": "head"}]))
    issue = stack.enter_context(patch.object(main_guard, "guard_issue", return_value=7))
    config = {"test": ["checks"]}
    result = main_guard.check_main(name, root, base="main", config=config, force=True, revision="merge^1")
    assert result["baseline"]["sha"] == "parent"
    assert tests.call_args.args[1] == "parent"
    added = [call for call in commands.call_args_list if call.args[1:3] == ("worktree", "add")]
    assert added[-1].args[-1] == "parent", added
    assert store.main_status() == {}
    result = main_guard.check_main(name, root, base="main", config=config, force=True)
    assert result["culprit"] == {"sha": "head", "pr": 42}, result
    store.state_update(name, 7, _event={"action": "closed"}, recovery_exhausted=True)
    store.save_main_status(name, {**result, "exhausted_sha": "head"})
    issue.reset_mock()
    main_guard.check_main(name, root, base="main", config=config, force=True)
    issue.assert_not_called()
    current_sha = "new-head"
    result = main_guard.check_main(name, root, base="main", config=config, force=True)
    issue.assert_called_once()
    assert result["exhausted_sha"] is None and result["culprit"] is None, result
    assert not store.state_read(name, 7)["recovery_exhausted"]
    for age in (3599, 3600):
        unknown = {**deepcopy(ci), "tested": False}
        tests.side_effect = lambda *args: deepcopy(unknown)
        store.save_main_status(name, {"status": "unknown", "since": now - age,
                                     "baseline": {"sha": current_sha}, "issue": 7})
        issue.reset_mock()
        with patch.object(main_guard.time, "time", return_value=now):
            result = main_guard.check_main(name, root, base="main", config=config, force=True)
        assert result["status"] == "unknown"
        assert issue.call_count == (1 if age >= 3600 else 0), (age, issue.call_args_list)
print("main recovery checks: green")
PY
uv run python - <<'PY'
from contextlib import ExitStack
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import finish, graph, lint, plan, retro, store, tick
from lokay.effects import gh, git as git_effects
from lokay.types import Checked, RepoSnapshot, Run, Snapshot

real_retry = tick._retry
name = "owner/split"
sha = "a" * 40
finding = {"plik": "src/a.py", "linia_od": 1, "linia_do": 1,
           "zmiana": "logic bug", "pytanie": "correctness", "uzasadnienie": "quoted evidence"}
findings = [dict(finding, uzasadnienie=f"finding {index} " + "x" * 1000) for index in range(30)]
verdict = {"result": "fix", "sha": sha, "uwagi": [finding]}
tasks = [{"title": "first", "body": "first spec"}, {"title": "second", "body": "second spec"}]
with TemporaryDirectory() as directory, ExitStack() as stack:
    root = Path(directory)
    for key, value in (("HOME", root), ("RUNS", root / "runs"), ("LOCKS", root / "locks")):
        stack.enter_context(patch.object(store, key, value))
    calls = []
    def remote(args, **kwargs):
        calls.append(args)
        assert args[:2] in (["issue", "create"], ["issue", "comment"]), args
        return f"https://github.com/{name}/issues/{100 + len(calls)}"
    stack.enter_context(patch.object(gh, "gh_json", return_value=[]))
    stack.enter_context(patch.object(gh, "gh_ok", side_effect=remote))
    stack.enter_context(patch.object(tick, "gh_ok", side_effect=remote))
    texts = {3: {"title": "existing PR", "body": "spec"}, 2: {"title": "ops", "body": "<!-- lokay-host-ops: repair -->"}}
    def view(args, **kwargs):
        assert args[:2] == ["issue", "view"] and args[3:] == ["--repo", name, "--json", "title,body"], args
        return texts[int(args[2])]
    stack.enter_context(patch.object(tick, "gh_json", side_effect=view))
    stack.enter_context(patch.object(tick, "repo_config", return_value={"test": []}))
    stack.enter_context(patch.object(tick, "_repo_paths", return_value=(root, root)))
    stack.enter_context(patch.object(tick, "_retry", side_effect=lambda picked, node, fn, *args, **kwargs: fn()))
    stack.enter_context(patch.object(tick, "check_deadline"))
    stack.enter_context(patch.object(tick, "base_branch", return_value="main"))
    stack.enter_context(patch.object(tick, "escalate", return_value=None))
    stack.enter_context(patch.object(tick, "fix_step", return_value={"result": "pushed", "sha": sha}))
    stack.enter_context(patch.object(tick, "pushed_pr", return_value={"number": 7}))
    stack.enter_context(patch.object(tick, "refresh_body", return_value={"result": "updated"}))
    stack.enter_context(patch.object(finish, "sync_main", return_value=[]))
    stack.enter_context(patch.object(git_effects, "git_try", side_effect=lambda path, *args, **kwargs:
        (0, sha if args[0] == "rev-parse" else "", "")))
    stack.enter_context(patch.object(git_effects, "plan_checkout", return_value=root))
    stack.enter_context(patch.object(finish, "local_checks", return_value={"result": "green", "failed": [], "notes": []}))
    stack.enter_context(patch.object(finish, "remote_checks", return_value=(7, {"result": "green"})))
    stack.enter_context(patch.object(finish, "lenses", return_value=([], [], [], [], "", [], False)))
    stack.enter_context(patch.object(finish, "complete_check", return_value=(verdict, 8)))
    splitter = stack.enter_context(patch.object(plan, "split_tasks", return_value={"result": "done", "tasks": tasks}))
    publisher = stack.enter_context(patch.object(retro, "publish"))
    picked = {"repo": name, "issue": 1}
    for hits in (0, 1):
        store.state_update(name, 1, _event={"action": "enter_node", "outcome": {"node": "check"}},
                           result="pending", difficulty="hard", issue_title="split issue", issue_body="spec",
                           pr=None, sha=sha, fix_rounds=graph.FIX_ROUND_LIMIT - 1, fix_limit_hits=hits,
                           check_history=[{"sha": sha, "findings": findings}])
        result = tick._finish(picked, root, "lokay/1", sha, [])
        saved = store.state_read(name, 1)
        assert saved["difficulty"] == "hard" and saved["pr"] is None, saved
        assert all(item["uzasadnienie"] in saved["plan_prompt"] for item in findings)
        if hits == 0:
            assert result == {"result": "pending", "next": "plan"}, result
            assert saved["node"] == "plan" and saved["fix_limit_hits"] == 1
            splitter.assert_not_called()
            assert calls == []
        else:
            assert len(result["children"]) == 2 and saved["awaiting"] == "children", saved
            assert all(item["uzasadnienie"] in splitter.call_args.args[0] for item in findings)
            assert [args[:2] for args in calls] == [["issue", "create"]] * 2, calls
            for index, args in enumerate(calls):
                assert f"Lokay parent: #1; split: 0; task: {index}" in args[args.index("--body") + 1].splitlines()
        assert publisher.call_count == hits + 1
    with ExitStack() as checks:
        for hits in (1, 2, 5):
            derived = graph.step(Run.from_state({"pr": 7, "node": "check",
                "fix_rounds": graph.FIX_ROUND_LIMIT - 1, "fix_limit_hits": hits}),
                Checked(1, outcome=verdict)).state
            assert derived["node"] == "plan" and derived["fix_rounds"] == 0, derived
            assert derived["fix_limit_hits"] == hits + 1 and derived["pr"] == 7, derived
            assert not derived.get("split_pending"), derived
            assert "children" not in derived and "split_tasks" not in derived, derived
        calls.clear()
        splitter.reset_mock()
        picked_pr = {"repo": name, "issue": 3}
        store.state_update(name, 3, _event={"action": "enter_node", "outcome": {"node": "check"}},
                           result="pending", difficulty="hard", issue_title="existing PR", issue_body="spec",
                           pr=7, sha=sha, fix_rounds=graph.FIX_ROUND_LIMIT - 1, fix_limit_hits=1,
                           check_history=[{"sha": sha, "findings": findings}])
        result = tick._finish(picked_pr, root, "lokay/3", sha, [])
        saved = store.state_read(name, 3)
        assert result == {"result": "pending", "next": "plan"}, result
        assert saved["pr"] == 7 and saved["node"] == "plan", saved
        assert "Split this issue" not in saved["plan_prompt"], saved["plan_prompt"]
        assert calls == [], calls
        splitter.assert_not_called()
        store.state_update(name, 3, split_pending=True)
        split_issue = checks.enter_context(patch.object(tick, "_split_issue"))
        sentinel = RuntimeError("normal prepare path reached")
        ensure = checks.enter_context(patch.object(tick, "_ensure_worktree", side_effect=sentinel))
        try:
            tick._prepare(picked_pr)
        except RuntimeError as exc:
            assert exc is sentinel, exc
        else:
            raise AssertionError("normal prepare path not reached")
        ensure.assert_called_once_with(picked_pr)
        split_issue.assert_not_called()
        splitter.assert_not_called()
        assert not store.state_read(name, 3).get("split_pending")
        assert calls == [], calls
        print("existing PR fix round limit checks: ok")
        with patch.object(tick, "_retry", real_retry), patch.object(tick, "_ensure_worktree"):
            store.state_update(name, 3, _event={"action": "enter_node", "outcome": {"node": "check"}},
                               result="pending", difficulty="hard", issue_title="existing PR", issue_body="spec",
                               pr=7, sha=sha, fix_rounds=graph.FIX_ROUND_LIMIT - 1, fix_limit_hits=1,
                               check_history=[{"sha": sha, "findings": findings}])
            result = tick._finish(picked_pr, root, "lokay/3", sha, [])
            saved = store.state_read(name, 3)
            assert result == {"result": "pending", "next": "plan"}, result
            assert saved["node"] == "plan" and saved["pr"] == 7, saved
            snapshot = Snapshot(repos=(RepoSnapshot(name=name, prs=(), issues=(), states={3: saved}),),
                                now=store.last_activity(saved) + 301)
            assert graph.pick(snapshot) is None
            print("round limit keeps plan node: green")
    for hits in (0, 1, 2, 99):
        normalized = {"pr": 7, "difficulty": "too_big", "fix_limit_hits": hits}
        store.normalize_state(normalized)
        assert normalized["difficulty"] == "hard"
    calls.clear()
    store.state_update(name, 2, issue_title="ops", issue_body="<!-- lokay-host-ops: repair -->")
    assert tick._prepare({"repo": name, "issue": 2})["result"] == "closed"
    assert store.state_read(name, 2)["host_ops"] is True
    assert [args[:2] for args in calls] == [["issue", "comment"]], calls

with TemporaryDirectory() as directory, ExitStack() as stack:
    root = Path(directory)
    stack.enter_context(patch.object(store, "RUNS", root / "runs"))
    rows = []
    created = []
    def create(args, **kwargs):
        created.append(args)
        rows.append({"number": 10, "body": args[args.index("--body") + 1]})
    stack.enter_context(patch.object(retro, "gh_json", side_effect=lambda *args, **kwargs: rows))
    stack.enter_context(patch.object(retro, "gh_ok", side_effect=create))
    for index in range(3):
        state = {"sha": sha, "pr": 7, "last_check": verdict}
        row = {"kind": "transition", "repo": f"owner/repo{index}", "issue": 1, "after": state}
        store.write_artifact(root / "ticks" / f"{index}.jsonl", (json.dumps(row) + "\n") * 2)
        retro.publish()
        assert len(created) == (1 if index == 2 else 0)
    retro.publish()
    assert len(created) == 1
    args = created[0]
    assert args[args.index("--repo") + 1] == "mikolaj92/lokay"
    assert args[args.index("--title") + 1] == "nowy check w checks.py: logic bug"
    body = rows[0]["body"]
    assert body.splitlines()[0].startswith("Lokay retro: ")
    assert all(f"owner/repo{index}/issues/1" in body and f"owner/repo{index}/pull/7" in body for index in range(3))
    assert sha in body and "> quoted evidence" in body

for parked in (True, False):
    with TemporaryDirectory() as directory, ExitStack() as stack:
        root = Path(directory)
        for key, value in (("HOME", root), ("RUNS", root / "runs"), ("LOCKS", root / "locks")):
            stack.enter_context(patch.object(store, key, value))
        config = {"name": name, "clone_path": str(root / "absent"), "merge": "off"}
        pr = {"number": 7, "headRefName": "lokay/1", "headRefOid": sha,
              "labels": [] if parked else [{"name": "lokay-parked"}]}
        store.state_update(name, 1, _event={"action": "enter_node", "outcome": {"node": "check"}},
                           pr=7, sha=sha, result="parked" if parked else "check", no_progress=3)
        stack.enter_context(patch.object(tick.maintenance, "sweep"))
        stack.enter_context(patch.object(tick, "probes", return_value={"host": "ok"}))
        stack.enter_context(patch.object(tick, "load_repos", return_value=[config]))
        stack.enter_context(patch.object(tick, "list_prs", return_value=[pr]))
        stack.enter_context(patch.object(tick, "open_issues", return_value=[]))
        stack.enter_context(patch.object(tick, "gh_json", return_value={"data": {"repository": {}}}))
        remote = stack.enter_context(patch.object(tick, "gh_ok"))
        result = tick.pick({"LOKAY2_REPO": name})
        if parked:
            assert result["result"] == "picked" and result["node"] == "plan", result
            assert store.state_read(name, 1)["no_progress"] == 0
            tick.release_lock(result["held"])
        else:
            assert result["result"] == "picked" and result["node"] == "check", result
            assert store.state_read(name, 1)["no_progress"] == 3
            tick.release_lock(result["held"])
            remote.assert_called_once()
            assert remote.call_args.args[0][-2:] == ["--remove-label", "lokay-parked"]
        if parked:
            remote.assert_not_called()

for line, rejected in (("args = ['--add-label', 'lokay-x']", True),
                       ('args = ["label", "create", "lokay-x"]', True),
                       ("args = ['--remove-label', 'lokay-x']", False)):
    diff = "diff --git a/src/example.py b/src/example.py\n--- a/src/example.py\n+++ b/src/example.py\n@@ -0,0 +1 @@\n+" + line + "\n"
    with patch.object(lint, "git_output", return_value=line + "\n"):
        errors = lint.lint_diff(diff, "head", Path.cwd(), lokay_rules=True)
    assert bool(errors) is rejected, errors
print("split and label checks: green")
PY
uv run python - <<'PY'
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import store, tick
from lokay.effects import git as effects

service = Path("scripts/lokay-service.sh").read_text()
startup = 'export LOKAY_VERSION="$(git -C "$ROOT" rev-parse HEAD)"'
assert service.index(startup) < service.index('while true; do')
assert service.count('export LOKAY_VERSION=') == 2
name = "owner/hygiene"
for scenario in ("dirty", "unpushed", "write failed", "remove failed"):
    with TemporaryDirectory() as directory, ExitStack() as stack:
        home = Path(directory)
        root = home / "repo"
        worktree = home / "repo-wt-5"
        root.mkdir()
        (root / ".git").mkdir()
        worktree.mkdir()
        store.write_artifact(worktree / ".git", "gitdir: unused")
        for key, value in (("HOME", home), ("RUNS", home / "runs"), ("LOCKS", home / "locks")):
            stack.enter_context(patch.object(store, key, value))
        store.state_update(name, 5, _event={"action": "closed"})
        config = {"name": name, "clone_path": str(root), "merge": "on"}
        stack.enter_context(patch.object(tick.maintenance, "sweep"))
        stack.enter_context(patch.object(tick, "probes", return_value={"host": "ok"}))
        stack.enter_context(patch.object(tick, "load_repos", return_value=[config]))
        stack.enter_context(patch.object(store, "main_status", return_value={name: {"checked_at": tick.time.time()}}))
        stack.enter_context(patch.object(tick, "list_prs", return_value=[]))
        stack.enter_context(patch.object(tick, "open_issues", return_value=[]))
        stack.enter_context(patch.object(effects, "base_branch", return_value="main"))
        commands = []
        def fake_git(where, *args, **kwargs):
            commands.append(args)
            if args[0] == "for-each-ref":
                return (0, "refs/heads/lokay/5\n", "") if len(args) == 3 else (0, "" if scenario == "unpushed" else "refs/remotes/origin/main", "")
            if args[:2] == ("rev-parse", "--show-toplevel"):
                return 0, str(where), ""
            if args[:2] == ("rev-parse", "--git-common-dir"):
                return 0, str(root / ".git"), ""
            if args[0] == "rev-parse":
                return (1, "", "") if args[-1].endswith("@{upstream}") else (0, "head", "")
            if args[0] == "symbolic-ref":
                return 0, "refs/heads/lokay/5", ""
            if args[:2] == ("worktree", "list"):
                return 0, f"worktree {worktree}\0branch refs/heads/lokay/5\0\0", ""
            if args[0] == "status":
                return 0, "" if scenario == "unpushed" else " M tracked", ""
            if args[0] == "ls-files":
                return 0, "new file\0", ""
            if args[0] == "diff":
                return (1, "untracked bytes\n", "") if "--no-index" in args else (0, "committed and working bytes\n", "")
            return 0, "", ""
        def fake_command(where, args, **kwargs):
            from subprocess import CompletedProcess

            code, out, err = fake_git(where, *args)
            return CompletedProcess(args, code, out.encode(), err.encode())
        stack.enter_context(patch.object(effects, "_command", side_effect=fake_command))
        stack.enter_context(patch.object(effects, "git_try", side_effect=fake_git))
        stack.enter_context(patch.object(tick, "git_try", side_effect=fake_git))
        events = stack.enter_context(patch.object(store, "log_event"))
        if scenario == "write failed":
            stack.enter_context(patch.object(store, "write_artifact", side_effect=OSError("full")))
        if scenario == "remove failed":
            stack.enter_context(patch.object(effects.os, "rename", side_effect=OSError("busy")))
        assert tick.pick({})["result"] == "idle"
        expected = "failed" if "failed" in scenario else "done"
        assert store.state_read(name, 5)["cleanup"] == expected
        if scenario != "write failed":
            text = (store.run_dir(name, 5) / "cleanup.patch").read_text()
            assert "committed and working bytes" in text and "untracked bytes" in text
        assert worktree.exists() == (expected == "failed")
        assert sum(call.args == ("closed_cleanup",) for call in events.call_args_list) == 1
        before = len(commands)
        tick.pick({})
        assert len(commands) == before
        assert sum(call.args == ("closed_cleanup",) for call in events.call_args_list) == 1

with TemporaryDirectory() as directory, ExitStack() as stack:
    home = Path(directory)
    for key, value in (("HOME", home), ("RUNS", home / "runs"), ("LOCKS", home / "locks")):
        stack.enter_context(patch.object(store, key, value))
    store.state_update(name, 6, result="merged")
    stack.enter_context(patch.object(tick.maintenance, "sweep"))
    stack.enter_context(patch.object(tick, "probes", return_value={"host": "ok"}))
    stack.enter_context(patch.object(tick, "load_repos", return_value=[{"name": name, "clone_path": str(home), "merge": "on"}]))
    stack.enter_context(patch.object(store, "main_status", return_value={name: {"checked_at": tick.time.time()}}))
    prs = [{"number": n, "headRefName": branch, "headRefOid": "head", "state": "OPEN"}
           for n, branch in ((15, "lokay/5"), (16, "lokay/6"), (17, "fix-something"), (18, "lokay/8"), (19, "lokay/9"))]
    stack.enter_context(patch.object(tick, "list_prs", side_effect=lambda name: tuple(prs)))
    stack.enter_context(patch.object(tick, "open_issues", return_value=[{"number": 9, "state": "OPEN"}]))
    looked = []
    def remote(args, **kwargs):
        assert args[:2] == ["issue", "view"], args
        looked.append(args[2])
        return {"state": "CLOSED" if args[2] == "5" else "OPEN", "closedAt": "2026-06-01T12:00:00Z", "url": "https://github.com/owner/hygiene/issues/5"}
    stack.enter_context(patch.object(tick, "gh_json", side_effect=remote))
    closed = stack.enter_context(patch.object(tick, "gh_ok", side_effect=AssertionError("unexpected gh_ok")))
    events = stack.enter_context(patch.object(store, "log_event"))
    stack.enter_context(patch.object(tick, "graph", wraps=tick.graph))
    stack.enter_context(patch.object(tick.graph, "pick", side_effect=[type("Selection", (), {"repo": name, "issue": None, "kind": "prs"})(), None] * 2))
    tick.pick({})
    tick.pick({})
    closed.assert_not_called()
    assert "6" not in looked
    assert any(row["number"] == 15 for row in prs)
    assert "9" not in looked
    assert any(row["number"] == 19 for row in prs)
    assert sum(call.args == ("orphan_pr_skipped",) for call in events.call_args_list) == 2
print("hygiene checks: green")
PY
uv run python - <<'PY'
import io
import json
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import config, measure, merge, retro, store, tick
from lokay.effects import gh

with TemporaryDirectory() as directory, ExitStack() as stack:
    home = Path(directory)
    for key, value in (("HOME", home), ("RUNS", home / "runs"), ("LOCKS", home / "locks")):
        stack.enter_context(patch.object(store, key, value))
    stack.enter_context(patch.object(config, "HOME", home))
    argv = []
    def remote(args, **kwargs):
        argv.append(args)
        return (0, json.dumps({"mergeCommit": {"oid": "M"}}) if args[:2] == ["pr", "view"] else "", "")
    stack.enter_context(patch.object(gh, "_gh", side_effect=remote))
    assert gh.merge("o/r", 5, "S")["merge_sha"] == "M"
    assert argv[0][argv[0].index("--body") + 1] == "Lokay-Merge: " + store.TICK
    pr = {"number": 5, "headRefName": "lokay/1", "headRefOid": "S", "labels": []}
    store.state_update("o/r", 1, _event={"action": "enter_node", "outcome": {"node": "check"}}, pr=5)
    for target, name, value in ((tick.maintenance, "sweep", None), (tick, "probes", {"host": "ok"}),
                               (tick, "load_repos", [{"name": "o/r", "clone_path": str(home / "absent"), "merge": "off"}]),
                               (tick, "list_prs", [pr]), (tick, "open_issues", []),
                               (tick, "gh_json", {"data": {"repository": {}}})):
        stack.enter_context(patch.object(target, name, return_value=value))
    picked = tick.pick({"LOKAY2_REPO": "o/r"})
    assert picked["result"] == "picked", picked
    tick.release_lock(picked["held"])
    pick = measure.ledger(home)[0]
    assert pick["kind"] == "pick" and pick["issue"] == 1 and pick["reason"] == "pr", pick
    for day, values in ((pick["ts"][:10], (1000, 2000)), ("2000-01-01", (99999,))):
        store.write_text_atomic(home / "ticks" / (day + ".jsonl"), "".join(json.dumps(
            {"kind": "call", "call": "pi", "repo": "o/r", "issue": 1, "ts": pick["ts"], "ms": ms}) + "\n"
            for ms in values))
    stack.enter_context(patch.object(merge, "merge_allowed", return_value=True))
    stack.enter_context(patch("lokay.review.recompute_verdict", return_value={"result": "merge", "sha": "S"}))
    stack.enter_context(patch.object(merge, "pr_files", return_value=["src/app.py"]))
    stack.enter_context(patch.object(merge, "base_branch", return_value="main"))
    stack.enter_context(patch.object(merge, "check_main"))
    outcome = merge.merge_sha("o/r", 5, "S", None, None, "o", 1,
                              {"plan_rounds": 1, "check_rounds": 2}, clone_path=home)
    assert outcome["result"] == "merged", outcome
    merged = measure.ledger(home)[-1]
    assert (merged["kind"], merged["sha"], merged["pr"], merged["fix_rounds"], merged["pi_ms"],
            merged["picked_at"], merged["change_kind"]) == ("merged", "M", 5, 2, 3000, pick["ts"], "code"), merged
    old = datetime.now(timezone.utc) - timedelta(hours=49)
    store.write_text_atomic(home / "ledger.jsonl", "".join(json.dumps(row) + "\n" for row in (
        {**merged, "ts": old.isoformat(), "picked_at": (old - timedelta(minutes=20)).isoformat()},
        {**merged, "issue": 2, "sha": "N", "change_kind": "docs"})))
    def lookup(args, **kwargs):
        if args[0] == "issue":
            return {"state": "OPEN", "stateReason": "REOPENED"}
        assert args == ["api", f"repos/o/r/commits?sha=main&since={old.isoformat()}", "--paginate", "--slurp"], args
        return [[]]
    lookups = stack.enter_context(patch.object(measure, "gh_json", side_effect=lookup))
    output = io.StringIO()
    with redirect_stdout(output):
        assert measure.main([]) == 0
    assert all(text in output.getvalue() for text in ("escape_rate_48h=1/1", "p50", "merges_per_day")), output.getvalue()
    calls = lookups.call_count
    with redirect_stdout(io.StringIO()):
        assert measure.main([]) == 0
    assert lookups.call_count == calls
    assert len([row for row in measure.ledger(home) if row["kind"] == "escape_check"]) == 1
    store.ledger_append({**merged, "sha": "FAIL"})
    rows = measure.ledger(home)
    rows[-1]["ts"] = old.isoformat()
    store.write_text_atomic(home / "ledger.jsonl", "".join(json.dumps(row) + "\n" for row in rows))
    with patch.object(measure, "gh_json", side_effect=RuntimeError("offline")):
        assert len(measure.escapes(home)) == 1
    assert not any(row["kind"] == "escape_check" and row["sha"] == "FAIL" for row in measure.ledger(home))
    with redirect_stdout(io.StringIO()), patch.object(measure, "merges", side_effect=lambda home, ticks: (
            ticks.extend([old - timedelta(hours=2), old]) or [])):
        assert measure.main(["--baseline", (old - timedelta(hours=3)).isoformat(),
                             "--since", (old - timedelta(hours=1)).isoformat()]) == 0
    evidence = [{"repo": "o/r", "issue": issue, "pr": 5, "sha": "M", "why": ["issue reopened"]}
                for issue in (1, 2, 3)]
    assert ("escape", "logic bug") in retro.proposals(home / "ticks", escapes=evidence)
print("ledger and measure checks: green")
PY
uv run python - <<'PY'
import ast
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import finish, graph, merge, store, tick
from lokay.types import RepoSnapshot, Snapshot

for path in Path('src/lokay').rglob('*.py'):
    for node in ast.walk(ast.parse(path.read_text())):
        bad = isinstance(node, ast.Constant) and isinstance(node.value, str) and 'pr close' in node.value
        if isinstance(node, (ast.List, ast.Tuple)):
            values = [item.value if isinstance(item, ast.Constant) else None for item in node.elts]
            bad |= any(values[index:index + 2] == ['pr', 'close'] for index in range(len(values)))
        assert not bad, f'{path}:{node.lineno}'

with TemporaryDirectory() as directory, ExitStack() as stack:
    root = Path(directory)
    for key, value in (('HOME', root), ('RUNS', root / 'runs'), ('LOCKS', root / 'locks')):
        stack.enter_context(patch.object(store, key, value))
    name, issue, sha = 'owner/empty', 310, 'main-sha'
    stack.enter_context(patch('lokay.config.repo', return_value={'clone_path': str(root)}))
    stack.enter_context(patch('lokay.effects.git.base_branch', return_value='main'))
    stack.enter_context(patch('lokay.effects.git.git', return_value=sha))
    store.state_update(name, issue, _event={'action': 'enter_node', 'outcome': {'node': 'build'}}, pr=38, last_check={'result': 'merge', 'sha': 'head'})
    assert store.empty_patch(name, issue, sha)['result'] == 'parked'
    remote = stack.enter_context(patch.object(tick, 'gh_ok', side_effect=AssertionError('unexpected gh')))
    assert tick.close_empty_patch(name, issue, store.state_read(name, issue), {'sha': sha})['result'] == 'empty_patch'
    stack.enter_context(patch.object(merge, 'pr_files', return_value=[]))
    stack.enter_context(patch('lokay.review.recompute_verdict', return_value={'result': 'merge', 'sha': 'head'}))
    stack.enter_context(patch.object(merge, 'main_status', return_value={}))
    stack.enter_context(patch.object(tick, 'open_pr_for', return_value={'number': 38, 'headRefOid': 'head'}))
    stack.enter_context(patch.object(tick, '_ensure_worktree'))
    stack.enter_context(patch.object(tick, 'check_deadline'))
    events = stack.enter_context(patch.object(store, 'log_event'))
    stack.enter_context(patch.object(finish, 'rounds_append', side_effect=AssertionError('unexpected merge round')))
    store.state_update(name, issue, empty_main_sha=None)
    for expected in ('parked', 'empty_patch'):
        merged, *_ = finish.merge({'repo': name, 'issue': issue}, root, 'lokay/310', 'head', None,
                                  'main', [], [], root, None)
        assert merged['result'] == expected
        assert store.state_read(name, issue)['node'] == 'build'
    assert not any(call.kwargs.get('event', {}).get('action') == 'merge_complete'
                   for call in events.call_args_list)
    state = store.state_read(name, issue)
    assert state['empty_main_sha'] == sha and state['result'] == 'empty_patch'
    assert state['node'] == 'build'
    for prs in ((), ({'number': 38, 'headRefName': 'lokay/310'},)):
        repo = RepoSnapshot(name, 0, {'baseline': {'sha': 'guard-sha'}}, states={issue: state},
                            prs=prs, issues=({'number': issue},), main_sha=sha)
        assert graph.pick(Snapshot((repo,), 1000)) is None
        assert graph.pick(Snapshot((replace(repo, main_sha=None),), 1000)) is None
        moved = replace(repo, main_sha='new-main')
        assert graph.pick(Snapshot((moved,), 1000)).issue == issue
    patch_file = root / 'build.patch'
    store.write_artifact(patch_file, 'patch')
    store.state_update(name, issue, issue_title='Title', issue_body='Body', difficulty='easy',
                       h2_patch=str(patch_file), h2_start='head', h2_committed='head')
    stack.enter_context(patch.object(tick, 'gh_json', return_value={'title': 'Title', 'body': 'Body'}))
    stack.enter_context(patch.object(tick, 'repo_config', return_value={'test': []}))
    stack.enter_context(patch.object(tick, '_repo_paths', return_value=(root, root)))
    stack.enter_context(patch.object(tick, '_ensure_worktree'))
    stack.enter_context(patch.object(tick, 'check_deadline'))
    stack.enter_context(patch.object(tick, 'base_branch', return_value='main'))
    stack.enter_context(patch.object(tick, 'git', side_effect=lambda path, *args, **kwargs: '' if args[0] == 'rev-list' else sha))
    stack.enter_context(patch.object(tick, 'git_head', return_value='head'))
    stack.enter_context(patch('lokay.build.tidy_and_commit'))
    create = stack.enter_context(patch('lokay.effects.gh.pr_create', side_effect=AssertionError('unexpected publish')))
    import hashlib
    from json import dumps
    store.state_update(name, issue, h2_context=hashlib.sha256(dumps(['Title', 'Body', 'easy', []]).encode()).hexdigest())
    assert tick._prepare({'repo': name, 'issue': issue})['result'] == 'empty_patch'
    assert store.state_read(name, issue)['empty_main_sha'] == sha
    from lokay.types import Run
    stack.enter_context(patch.object(tick, '_prepare', side_effect=lambda picked: store.empty_patch(name, issue, sha)))
    stack.enter_context(patch.object(tick, 'published_cleanup'))
    assert tick.act(Run.from_state({'repo': name, 'issue': issue, 'node': 'build'})).outcome['result'] == 'empty_patch'
    assert store.state_read(name, issue)['result'] == 'empty_patch'
    create.assert_not_called()
    remote.assert_not_called()
    orphan = {'number': 99, 'headRefName': 'lokay/9', 'headRefOid': 'head'}
    stack.enter_context(patch.object(tick.maintenance, 'sweep'))
    stack.enter_context(patch.object(tick, 'probes', return_value={'host': 'ok'}))
    stack.enter_context(patch.object(tick, 'load_repos', return_value=[{
        'name': name, 'clone_path': str(root / 'absent'), 'merge': 'off'}]))
    stack.enter_context(patch.object(tick, 'list_prs', return_value=[orphan]))
    stack.enter_context(patch.object(tick, 'open_issues', return_value=[]))
    stack.enter_context(patch.object(tick, 'gh_json', side_effect=lambda args, **kwargs: {'data': {'repository': {}}} if args[0] == 'api' else {'state': 'CLOSED'}))
    from lokay.types import Pick
    stack.enter_context(patch.object(tick.graph, 'pick', side_effect=[Pick(name, 0, 'prs'), None]))
    assert tick.pick({})['result'] == 'idle'
    remote.assert_not_called()
print('empty patch state checks: green')
PY
uv run python - <<'PY'
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lokay import config, graph, main_guard, measure, store, tick
from lokay.types import Pick, RepoSnapshot, Snapshot

name = "mikolaj92/Temida"
with TemporaryDirectory() as directory, ExitStack() as stack:
    root = Path(directory)
    for key, value in (("HOME", root), ("RUNS", root / "runs"), ("LOCKS", root / "locks")):
        stack.enter_context(patch.object(store, key, value))
    baseline = {"sha": "B", "argv": [], "guard_version": main_guard.GUARD_VERSION,
                "ci": {"result": "red", "tested": True, "log": "red"},
                "lockfile": {"status": "pass", "findings": [], "reason": "ok"}}
    status = {"status": "red", "issue": 7423, "baseline": baseline, "since": 1}
    stack.enter_context(patch.object(main_guard, "git", side_effect=lambda path, *args, **kw: "B" if args[0] == "rev-parse" else ""))
    stack.enter_context(patch.object(main_guard, "guard_issue", return_value=7423))
    updates = stack.enter_context(patch.object(store, "state_update", wraps=store.state_update))
    for terminal in ("merged", "closed", "failed", "empty_patch"):
        for sha, recovery, reset in (("A", None, True), ("B", None, False), ("A", "B", False)):
            store.save_main_status(name, status)
            store.write_json(store.run_dir(name, 7423) / "state.json", {"repo": name, "issue": 7423, "result": terminal, "node": "plan",
                                    "sha": sha, "recovery_sha": recovery, "children": [1],
                                    "split_tasks": ["old"], "recovery_exhausted": True,
                                    "h2_context": "old", "difficulty": "hard"})
            updates.reset_mock()
            main_guard.check_main(name, root, base="main", config={})
            saved = store.state_read(name, 7423)
            assert (saved["result"] == "check") == reset, saved
            if reset:
                assert saved["node"] == "plan" and saved["children"] == [] and not saved["recovery_exhausted"]
                assert all(saved[key] is None for key in ("split_tasks", "recovery_sha", "h2_context", "difficulty"))
                assert saved["issue_body"].startswith("Main red.")
                snapshot = Snapshot((RepoSnapshot(name, status=store.main_status()[name], states={7423: saved}),), 10000)
                assert graph.pick(snapshot) == Pick(name, 7423, "red_main")
            main_guard.check_main(name, root, base="main", config={})
            events = [call.kwargs.get("_event", {}).get("action") for call in updates.call_args_list]
            assert events == (["reopened"] if reset else []), events

    name = "mikolaj92/Fala"
    store.state_update(name, 307, awaiting="children", children=[309, 310], result="pending", split_generation=4,
                       _event={"action": "enter_node", "outcome": {"node": "build"}})
    store.state_update(name, 309, _event={"action": "closed"})
    store.state_update(name, 310, result="failed")
    status = {"status": "red", "issue": 307, "checked_at": tick.time.time(), "since": tick.time.time()}
    store.save_main_status(name, status)
    def snapshot():
        return Snapshot((RepoSnapshot(name, status=status, states={issue: store.state_read(name, issue)
                                                                 for issue in (307, 309, 310)}),), tick.time.time())
    assert graph.pick(snapshot()) == Pick(name, 307, "red_main")
    store.state_update(name, 310, result="running")
    assert graph.pick(snapshot()) == Pick(name, 310, "red_main")
    store.state_update(name, 310, result="failed")
    stack.enter_context(patch.object(tick.maintenance, "sweep"))
    stack.enter_context(patch.object(tick, "probes", return_value={"host": "ok"}))
    stack.enter_context(patch.object(tick, "load_repos", return_value=[{"name": name, "clone_path": str(root / "absent"), "merge": "on"}]))
    stack.enter_context(patch.object(tick, "gh_json", return_value={"data": {"repository": {}}}))
    stack.enter_context(patch.object(tick, "open_pr_for", return_value=None))
    picked = tick.pick({"LOKAY2_REPO": name})
    assert picked["result"] == "picked" and picked["issue"] == 307 and picked["node"] == "plan", picked
    tick.release_lock(picked["held"])
    saved = store.state_read(name, 307)
    assert saved["node"] == "plan" and saved["split_generation"] == 5 and saved["children"] == []
    assert saved["awaiting"] is None and saved["waiting_on"] != "children"

    stack.enter_context(patch.object(config, "HOME", root))
    stack.enter_context(patch.object(measure, "escapes", return_value=[]))
    since = datetime.now(timezone.utc) - timedelta(hours=3)
    store.save_main_status("mikolaj92/Temida", {"status": "green"})
    store.save_main_status(name, {"status": "red", "since": since.timestamp()})
    stack.enter_context(patch.object(measure, "ledger", return_value=[]))
    for rows, expected in (([], 1), ([{"kind": "pick", "reason": "issue", "repo": name, "ts": since.isoformat()}], 1),
                           ([{"kind": "pick", "reason": "red_main", "repo": name,
                              "ts": (since - timedelta(seconds=1)).isoformat()}], 1),
                           ([{"kind": "pick", "reason": "red_main", "repo": name, "ts": since.isoformat()}], 0)):
        with patch.object(measure, "ledger", return_value=rows), redirect_stdout(io.StringIO()) as output:
            assert measure.main(["--json"]) == expected
        data = json.loads(output.getvalue())
        assert data["red_main_errors"] == ([name] if expected else [])
        assert data["red_main"][name]["hours"] >= 3 and data["red_main"][name]["picks"] == (0 if expected else 1)
print("red main exit checks: green")
PY
uv run lokay replay fixtures/replay/
uv run lokay replay fixtures/ticks/

#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
previous=''
for repetition in 1 2; do
output=$(uv run --offline python - <<'PY'
import hashlib
import json
import os
import select
import subprocess
import sys
import tempfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

# Exercise the real CLI, persistence, locks, CI and HTTP adapter. Only external
# tools are fake; no Git commands or requests to GitHub/real models are made.
FAKE = r'''
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

root = Path(os.environ["DARKFACTORY_ROOT"])
store = root / "external.json"
data = json.loads(store.read_text())
args = sys.argv[1:]
tool = Path(sys.argv[0]).name
cwd = Path.cwd()

def save():
    store.write_text(json.dumps(data))

def emit(value):
    print(json.dumps(value))

def head():
    return data["heads"][str(cwd)]

def branch():
    return (cwd / ".branch").read_text()

with (root / "calls.jsonl").open("a") as log:
    log.write(json.dumps([tool, args]) + "\n")

if tool == "pi":
    assert args[0] == "-p"
    prompt = args[-1]
    match = re.search(r"Write the plan only to (.+)\.\n$", prompt)
    if match:
        Path(match[1]).write_text("## Cel\nReturn 42.\n## Pliki\napp.py\n"
                                 "## Testy\npython verify.py\n## Poza zakresem\nNo other files.\n")
    else:
        # Build is deliberately wrong; Fix must change the code, not the check.
        value = 42 if "\n\nUwagi:\n" in prompt else 0
        (cwd / "app.py").write_text(f"value = {value}\n")
elif tool == "git":
    if args == ["fetch", "origin", "main"]:
        pass
    elif args[:3] == ["worktree", "add", "-b"]:
        target = Path(args[4])
        target.mkdir()
        (target / ".branch").write_text(args[3])
        (target / "verify.py").write_text("from app import value\nassert value == 42, value\n")
        data["heads"][str(target)] = "base"
        data["contents"][str(target)] = ""
        save()
    elif args[:3] == ["worktree", "remove", "--force"]:
        shutil.rmtree(args[3])
    elif args == ["status", "--porcelain"]:
        if (cwd / "app.py").read_text() != data["contents"][str(cwd)]:
            print(" M app.py")
    elif args in (["add", "-A"], ["reset", "-q", "--", "__pycache__"]):
        pass
    elif args[:2] == ["commit", "-m"]:
        content = (cwd / "app.py").read_text()
        data["heads"][str(cwd)] = hashlib.sha1((branch() + content).encode()).hexdigest()
        data["contents"][str(cwd)] = content
        save()
    elif args == ["rev-parse", "--abbrev-ref", "HEAD"]:
        print(branch())
    elif args == ["rev-parse", "HEAD"]:
        print(head())
    elif args == ["log", "--oneline", "origin/main..HEAD"]:
        print(head() + " scenario commit")
    elif args[:2] == ["ls-remote", "origin"]:
        remote = data["remote"].get(args[2].removeprefix("refs/heads/"))
        if remote:
            print(remote + "\t" + args[2])
    elif args[:3] == ["push", "-u", "origin"]:
        assert args[3] == branch()
        data["remote"][branch()] = head()
        save()
    elif args == ["diff", "--name-only", "--diff-filter=U"]:
        pass
    elif args == ["merge", "--no-edit", "--no-ff", "origin/main"]:
        pass
    elif args == ["diff", "origin/main...HEAD"]:
        print("diff --git a/app.py b/app.py\n+++ b/app.py\n@@ -0,0 +1 @@\n+"
              + (cwd / "app.py").read_text().strip())
    else:
        raise SystemExit(f"unexpected fake git: {args}")
elif tool == "gh":
    def option(name):
        return args[args.index(name) + 1]

    if args == ["auth", "status"]:
        pass
    elif args[:2] == ["issue", "list"]:
        # Reverse order proves the factory, not the fixture, selects oldest.
        emit([{"number": n, "createdAt": f"2026-10-12T00:00:0{n}Z", "title": f"Return 42 ({n})"}
              for n in (2, 1) if n not in data["merged"]])
    elif args[:2] == ["issue", "view"]:
        emit({"title": f"Return 42 ({args[2]})", "body": "Add app.py with value = 42."})
    elif args[:2] == ["pr", "list"]:
        emit([{"number": n, "headRefName": b, "headRefOid": data["remote"][b]}
              for b, n in data["prs"].items() if n not in data["merged"]
              and ("--head" not in args or b == option("--head"))])
    elif args[:2] == ["pr", "create"]:
        b = option("--head")
        n = int(b.split("/")[1])
        assert f"Closes #{n}" in option("--body")
        data["prs"][b] = n
        save()
        print(f"https://example.invalid/pull/{n}")
    elif args[:2] == ["pr", "view"]:
        emit({"headRefOid": data["remote"][f"lokay/{args[2]}"], "statusCheckRollup": []})
    elif args[:2] == ["pr", "comment"]:
        data["comments"].append([int(args[2]), option("--body")])
        save()
    elif args[:2] == ["pr", "merge"]:
        n = int(args[2])
        assert option("--match-head-commit") == data["remote"][f"lokay/{n}"]
        assert n not in data["merged"]
        checks = [body for issue, body in data['comments'] if issue == n]
        assert len(checks) == 2 and '**fix** · CI: **red**' in checks[0]
        assert '**merge** · CI: **green**' in checks[1], 'merge without green check'
        assert data['contents'][str(root / f'clone-wt-{n}')] == 'value = 42\n'
        data["merged"].append(n)
        save()
    else:
        raise SystemExit(f"unexpected fake gh: {args}")
else:
    raise SystemExit(f"unexpected tool: {tool}")
'''

requests = []

def verify_rounds(rounds, sha):
    assert len(rounds) == 5, rounds
    assert 'Plan 1: ok' in rounds[0], rounds
    assert 'Check 1:' in rounds[1] and 'result=fix' in rounds[1] and 'ci=red' in rounds[1], rounds
    assert 'Fix: sha=' in rounds[2], rounds
    assert 'Check 2:' in rounds[3] and 'result=merge' in rounds[3] and 'ci=green' in rounds[3], rounds
    assert f'Merge: sha={sha}' in rounds[4], rounds

def verify_runs(runs):
    assert sorted(path.name for path in runs.iterdir()) == ['1', '2'], 'missing second tick'
    for issue in (1, 2):
        state = json.loads((runs / str(issue) / 'state.json').read_text())
        assert state['result'] == 'merged' and state['pr'] == issue, state

def rejects(check, *args):
    try:
        check(*args)
    except AssertionError:
        return
    raise AssertionError('mutation escaped the evidence gate')

class DecisionAPI(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, payload):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_GET(self):
        assert self.path == "/health"
        self.reply({"ready": True})

    def do_POST(self):
        assert self.path == "/v1/decisions"
        wire = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert wire["model"] == "scenario"
        requests.append(wire)
        answers = {}
        for question in wire["questions"]:
            options = [row["name"] for row in question["options"]]
            choice = "ok" if question["id"] == "next" else (
                "true" if "kind" not in wire["input"] else "false")
            assert choice in options
            answers[question["id"]] = {"choice": choice,
                "probabilities": {name: float(name == choice) for name in options}}
        self.reply({"model": "scenario", "usage": {"completion_tokens": 0}, "answers": answers})

with tempfile.TemporaryDirectory(prefix="lokay-darkfactory-") as temporary:
    root = Path(temporary).resolve()
    (root / "bin").mkdir()
    (root / "clone").mkdir()
    # Guard the real runner and its children, not just the fake tool arguments.
    (root / 'sitecustomize.py').write_text('''
import socket
import sys

def offline(event, args):
    if event == 'socket.connect':
        address = args[1]
        if not isinstance(address, tuple) or address[0] != '127.0.0.1':
            raise RuntimeError(f'non-loopback network blocked: {address}')
    if event == 'subprocess.Popen':
        command = args[1]
        if command and command[0] == '/usr/bin/curl':
            if not command[-1].startswith('http://127.0.0.1:'):
                raise RuntimeError(f'non-loopback curl blocked: {command}')
sys.addaudithook(offline)
''')
    (root / "external.json").write_text(json.dumps({
        "heads": {}, "contents": {}, "remote": {}, "prs": {}, "merged": [], "comments": []}))
    for name in ("pi", "gh", "git"):
        executable = root / "bin" / name
        executable.write_text(f"#!{sys.executable}\n" + FAKE)
        executable.chmod(0o755)
    (root / "repos.yaml").write_text(
        f"repos:\n  - name: example/darkfactory\n    clone_path: {root / 'clone'}\n"
        f"    test: [{json.dumps(sys.executable)}, verify.py]\n    merge: on\n")
    server = ThreadingHTTPServer(("127.0.0.1", 0), DecisionAPI)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = {key: os.environ[key] for key in os.environ
           if not key.startswith(("LOKAY", "PI_")) and key not in ("GH_TOKEN", "GITHUB_TOKEN")}
    env.update(PYTHONPATH=str(root) + os.pathsep + str(Path('src').resolve()),
               HOME=str(root / "home"), PATH=str(root / "bin") + os.pathsep + os.environ["PATH"],
               DARKFACTORY_ROOT=str(root), LOKAY2_REPOS_FILE=str(root / "repos.yaml"),
               LOKAY2_PROVIDER="fake", LOKAY2_MODEL="scenario", LOKAY2_DECISION_API="tensorfold",
               LOKAY2_DECISION_MODEL="scenario", LOKAY2_DECISION_BASE_URL=f"http://127.0.0.1:{server.server_port}",
               LOKAY_VERSION="darkfactory-scenario", LOKAY_TICK_SECONDS="0.05")
    # Keep the CLI imported in one process across both ticks and the idle tick.
    worker = subprocess.Popen([sys.executable, '-u', '-c', '''
import contextlib
import io
import json
import sys
from lokay.cli import main
for line in sys.stdin:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(['start'])
    print(json.dumps([code, out.getvalue(), err.getvalue()]), flush=True)
'''], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    def run_tick(timeout=30):
        worker.stdin.write('tick\n')
        worker.stdin.flush()
        if not select.select([worker.stdout], [], [], timeout)[0]:
            raise subprocess.TimeoutExpired('persistent CLI tick', timeout)
        line = worker.stdout.readline()
        assert line, worker.stderr.read()
        code, out, err = json.loads(line)
        return subprocess.CompletedProcess(['lokay', 'start'], code, out, err)
    previous_time = None
    try:
        for issue in (1, 2):
            try:
                tick = run_tick()
            except subprocess.TimeoutExpired:
                for path in (root / "home/.lokay").rglob("state.json"):
                    print(path.read_text(), file=sys.stderr)
                print((root / "calls.jsonl").read_text(), file=sys.stderr)
                raise
            assert tick.returncode == 0, (tick.stdout, tick.stderr)
            picked, result = [json.loads(line) for line in tick.stdout.splitlines()]
            assert (picked["issue"], picked["node"], result["result"]) == (issue, "plan", "merged"), tick.stdout
            runs = root / "home/.lokay/runs/example__darkfactory"
            state = json.loads((runs / str(issue) / "state.json").read_text())
            assert state["node"] == "merge" and state["result"] == "merged", state
            assert state['pr'] == issue and state['branch'] == f'lokay/{issue}', state
            assert state["plan_rounds"] == 1 and state["check_rounds"] == 2, state
            assert state["failures"] == 0 and state["retry_at"] == 0, state
            assert state["local_ci"]["result"] == "green", state
            assert state["sha"] == state["verdict"]["sha"] == result["merge_sha"], state
            external = json.loads((root / 'external.json').read_text())
            assert external['prs'][state['branch']] == state['pr']
            assert external['remote'][state['branch']] == state['sha']
            assert state['sha'] == hashlib.sha1((state['branch'] + 'value = 42\n').encode()).hexdigest()
            rounds = (runs / str(issue) / "rounds.md").read_text().splitlines()
            verify_rounds(rounds, state['sha'])
            rejects(verify_rounds, rounds[:2] + rounds[3:], state['sha'])  # omitted Fix
            red_merge = list(rounds)
            red_merge[3] = red_merge[3].replace('ci=green', 'ci=red')
            rejects(verify_rounds, red_merge, state['sha'])
            beat = json.loads((root / "home/.lokay/heartbeat.json").read_text())
            assert (beat["repo"], beat["issue"], beat["result"]) == ("example/darkfactory", issue, "merged"), beat
            assert beat["node"] is None and beat["node_since"] is None, beat
            assert beat["version"] == "darkfactory-scenario", beat
            stamp = datetime.fromisoformat(beat["time"])
            assert stamp.utcoffset().total_seconds() == 0
            assert previous_time is None or stamp > previous_time
            previous_time = stamp
            external = json.loads((root / "external.json").read_text())
            assert external["merged"] == list(range(1, issue + 1)), external
            assert not (root / f"clone-wt-{issue}").exists()
            if issue == 1:
                assert not (runs / "2").exists(), "second issue started before the second tick"
                rejects(verify_runs, runs)  # no second tick is not a complete proof
                first_state = (runs / "1/state.json").read_bytes()
                first_rounds = (runs / "1/rounds.md").read_bytes()
            else:
                assert (runs / "1/state.json").read_bytes() == first_state
                assert (runs / "1/rounds.md").read_bytes() == first_rounds
        verify_runs(runs)
        second_state = (runs / '2/state.json').read_bytes()
        second_rounds = (runs / '2/rounds.md').read_bytes()
        # A further autonomous tick is idle: no duplicate pick or merge.
        idle = run_tick(timeout=10)
        assert idle.returncode == 0 and not idle.stdout and 'idle no_work' in idle.stderr
        assert json.loads((root / 'external.json').read_text()) == external
        assert (runs / '1/state.json').read_bytes() == first_state
        assert (runs / '1/rounds.md').read_bytes() == first_rounds
        assert (runs / '2/state.json').read_bytes() == second_state
        assert (runs / '2/rounds.md').read_bytes() == second_rounds
        assert len(requests) == 6, requests  # Plan + one combined call per Check, twice.
        for issue in (1, 2):
            comments = [body for n, body in external["comments"] if n == issue]
            assert len(comments) == 2, comments
            assert "**fix** · CI: **red**" in comments[0], comments
            assert "**merge** · CI: **green**" in comments[1], comments
        calls = [json.loads(line) for line in (root / "calls.jsonl").read_text().splitlines()]
        assert sum(tool == "pi" for tool, _ in calls) == 6, calls
        for issue in (1, 2):
            state = json.loads((runs / str(issue) / 'state.json').read_text())
            merges = [args for tool, args in calls
                      if tool == 'gh' and args[:3] == ['pr', 'merge', str(state['pr'])]]
            assert len(merges) == 1, merges
            assert merges[0][merges[0].index('--match-head-commit') + 1] == state['sha']
        # Compare every external operation, including order, across fresh homes.
        normalized = json.dumps(calls, sort_keys=True).replace(str(root), '<root>')
        print('operations:', len(calls), hashlib.sha256(normalized.encode()).hexdigest())
        print("darkfactory: two autonomous ticks, red → fix → green → merge, state/rounds/heartbeat OK; mutations rejected=3")
    finally:
        worker.stdin.close()
        try:
            worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait()
        server.shutdown()
        server.server_close()
        thread.join()
PY
)
printf '%s\n' "$output"
[ -z "$previous" ] || [ "$output" = "$previous" ] || { echo 'non-deterministic operations' >&2; exit 1; }
previous=$output
done

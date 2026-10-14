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

# Host guard snapshots use sets internally; their read order is not a graph operation.
if not (tool == 'git' and args and args[0] in ('-C', '--literal-pathspecs')):
    with (root / "calls.jsonl").open("a") as log:
        log.write(json.dumps([tool, args]) + "\n")

if tool == "pi":
    assert args[0] == "-p"
    prompt = args[-1]
    match = re.search(r"Write the plan only to (.+)\.\n$", prompt)
    synthesis = re.search(r"Write JSON only to (.+)\. Do not write plan\.md\.\n$", prompt)
    if synthesis:
        sources = re.findall(r"Accepted branch: (\w+)", prompt)
        assert sources == ['minimal', 'risk', 'gates'], sources
        Path(synthesis[1]).write_text(json.dumps({
            'cel': 'Return 42.',
            'kryteria': [{'tresc': 'value == 42', 'zrodla': ['gates']}],
            'kroki': [{'tresc': 'Set value to 42.', 'zrodla': ['minimal']}],
            'pliki': [{'sciezka': 'app.py', 'zmiana': 'Return 42.', 'zrodla': ['minimal']}],
            'testy': [{'tresc': 'python verify.py', 'zrodla': ['gates']}],
            'poza_zakresem': [{'tresc': 'No other files.', 'zrodla': ['risk']}],
            'odrzucone': [],
        }))
    elif match:
        Path(match[1]).write_text("## Cel\nReturn 42.\n## Pliki\n- app.py\n"
                                 "## Testy\npython verify.py\n## Poza zakresem\nNo other files.\n")
    else:
        # Build is deliberately wrong; Fix must change the code, not the check.
        value = 42 if "\n\nUwagi:\n" in prompt else 0
        (cwd / "app.py").write_text(f"value = {value}\n")
elif tool == "git":
    if args and args[0] == '--literal-pathspecs':
        args = args[1:]
    if args and args[0] == '-C':
        if Path(args[1]) == root / 'clone':
            if args[2:] == ['rev-parse', 'HEAD']:
                print('base')
            raise SystemExit(0)
        os.execv('/usr/bin/git', ['git', *args])
    if args and args[0] == '--literal-pathspecs':
        args = args[1:]
    if args[:3] == ['diff', '--name-status', '--diff-filter=A'] or args[:4] == ['diff', '--cached', '--name-status', '--diff-filter=A'] or args == ['ls-files', '--others', '--exclude-standard']:
        pass
    elif args == ['ls-files', '-m', '-d', '--others', '--exclude-standard', '-z']:
        if (cwd / 'app.py').exists() and (cwd / 'app.py').read_text() != data['contents'][str(cwd)]:
            print('app.py\0', end='')
    elif args == ['diff', '--cached', '--binary', '--', 'app.py']:
        pass
    elif args in (['ls-files', '-z'], ['diff', '--name-only', '-z', 'origin/main...HEAD'],
                  ['diff', '--name-only', '-z', 'HEAD'],
                  ['diff', '--name-only', '-z', 'origin/main..HEAD'],
                  ['diff', '--cached', '--name-only', '-z'],
                  ['ls-tree', '-r', '--name-only', '-z', 'HEAD']):
        print('app.py\0', end='')
    elif args in (['ls-files', '--others', '--exclude-standard', '-z'],
                  ['ls-files', '--others', '--ignored', '--exclude-standard', '-z']):
        pass
    elif args == ['diff', '--name-status', '-z', 'origin/main...HEAD']:
        print('A\0app.py\0', end='')
    elif args == ['diff', '--stat', 'origin/main...HEAD']:
        print(' app.py | 1 +')
    elif args == ['log', '--format=%s', 'origin/main..HEAD']:
        print('scenario commit')
    elif args == ['diff', '--name-only', 'origin/main...HEAD']:
        print('app.py')
    elif args == ["fetch", "origin", "main"]:
        os.execv('/usr/bin/git', ['git', *args])
    elif args == ['rev-parse', 'origin/main'] or args[:3] == ['worktree', 'add', '--detach']:
        os.execv('/usr/bin/git', ['git', *args])
    elif args[:3] == ['show', '--format=fuller', '--first-parent']:
        os.execv('/usr/bin/git', ['git', *args[:3], 'HEAD'])
    elif args[:3] == ["worktree", "add", "-b"]:
        target = Path(args[4])
        target.mkdir()
        (target / ".branch").write_text(args[3])
        (target / "verify.py").write_text("from app import value\nassert value == 42, value\nprint('1 passed')\n")
        data["heads"][str(target)] = "base"
        data["contents"][str(target)] = ""
        save()
    elif args[:3] == ["worktree", "remove", "--force"]:
        if Path(args[3]).parent.name.startswith('lokay-main-'):
            os.execv('/usr/bin/git', ['git', *args])
        shutil.rmtree(args[3])
    elif args[:2] == ["status", "--porcelain"]:
        if (cwd / "app.py").exists() and (cwd / "app.py").read_text() != data["contents"][str(cwd)]:
            print(" M app.py")
    elif args[:2] == ["add", "-A"] or args == ["reset", "-q", "--", "__pycache__"]:
        pass
    elif args[:2] in (["commit", "-m"], ["commit", "--only"]):
        content = (cwd / "app.py").read_text()
        data["heads"][str(cwd)] = hashlib.sha1((branch() + content).encode()).hexdigest()
        data["contents"][str(cwd)] = content
        save()
    elif args == ["rev-parse", "--abbrev-ref", "HEAD"]:
        print(branch())
    elif args == ["rev-parse", "HEAD"]:
        print(head())
    elif args[:2] == ["rev-parse", "--git-path"]:
        print(".git/" + args[2])
    elif args[:2] == ["log", "--oneline"] and args[2].endswith('..HEAD'):
        if args[2].removesuffix('..HEAD') != head():
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
    elif args == ["merge", "--no-edit", "origin/main"]:
        pass
    elif args == ['diff', '--stat', 'origin/main...HEAD']:
        print(' app.py | 1 +\n 1 file changed, 1 insertion(+)')
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
    elif args[:2] == ["pr", "edit"]:
        assert f"Closes #{args[2]}" in option("--body")
    elif args[:2] == ["pr", "view"]:
        sha = data["remote"][f"lokay/{args[2]}"]
        emit({"headRefOid": sha, "mergeCommit": {"oid": sha},
              "statusCheckRollup": [{"name": "fixture", "status": "COMPLETED", "conclusion": "SUCCESS"}]})
    elif args[:2] == ["pr", "edit"]:
        assert f"Closes #{args[2]}" in option("--body")
        assert int(args[2]) in data["prs"].values()
    elif args[:2] == ["pr", "comment"]:
        data["comments"].append([int(args[2]), option("--body")])
        save()
    elif args[:2] == ["pr", "merge"]:
        n = int(args[2])
        assert option("--match-head-commit") == data["remote"][f"lokay/{n}"]
        assert n not in data["merged"]
        checks = [body for issue, body in data['comments'] if issue == n]
        assert len(checks) == 2 and '**fix** · CI: **green** · tests: **red**' in checks[0]
        assert '**merge** · CI: **green** · tests: **green** · tested=true' in checks[1], 'merge without green check'
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
    progress = [line for line in rounds if 'Fix progress:' in line]
    assert len(progress) == 1 and 'counts=[2]' in progress[0], rounds
    lenses = [line for line in rounds if 'Check lens ' in line]
    assert len(lenses) == 14, rounds
    rounds = [line for line in rounds if 'Fix progress:' not in line and 'Check lens ' not in line]
    assert len(rounds) == 12, rounds
    assert [line.split(' ', 2)[2] for line in rounds[:8]] == [
        f'Plan {perspective} 1: {phase}'
        for perspective in ('minimal', 'risk', 'gates')
        for phase in ('write', 'Decision ok')
    ] + ['Synteza 1: write', 'Synteza 1: Decision ok'], rounds
    assert 'Check 1:' in rounds[8] and 'result=fix' in rounds[8] and 'ci=red' in rounds[8], rounds
    assert 'Fix: sha=' in rounds[9], rounds
    assert 'Check 2:' in rounds[10] and 'result=merge' in rounds[10] and 'ci=green' in rounds[10], rounds
    assert f'Merge: sha={sha}' in rounds[11], rounds

def verify_runs(runs):
    assert sorted(path.name for path in runs.iterdir() if path.is_dir()) == ['1', '2'], 'missing second tick'
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
    def real_git(*args):
        subprocess.run(['/usr/bin/git', *args], cwd=root / 'clone', check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       env={**os.environ, 'GIT_AUTHOR_DATE': '2026-01-01T00:00:00Z',
                            'GIT_COMMITTER_DATE': '2026-01-01T00:00:00Z'})
    real_git('init', '-b', 'main')
    real_git('config', 'user.name', 'mikolaj92')
    real_git('config', 'user.email', 'fixture@example.invalid')
    (root / 'clone/app.py').write_text('value = 42\n')
    (root / 'clone/verify.py').write_text("from app import value\nassert value == 42, value\nprint('1 passed')\n")
    real_git('add', '.')
    real_git('commit', '-m', 'Main fixture')
    real_git('remote', 'add', 'origin', str(root / 'clone'))
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
            assert state["plan_rounds"] == 4 and state["check_rounds"] == 2, state
            assert set(state['plan_branches']) == {'minimal', 'risk', 'gates'}, state
            assert all(branch['phase'] == 'accepted' and branch['rounds'] == 1
                       for branch in state['plan_branches'].values()), state
            assert state['plan_synthesis']['phase'] == 'accepted', state
            assert state['plan_synthesis']['rounds'] == 1, state
            plan_dir = runs / str(issue)
            assert all((plan_dir / 'plans' / f'{name}.md').is_file()
                       for name in ('minimal', 'risk', 'gates'))
            assert (plan_dir / 'synthesis.json').is_file()
            assert '[źródła: gates]' in (plan_dir / 'plan.md').read_text()
            assert state["failures"] == 0 and state["retry_at"] == 0, state
            assert state["local_ci"]["result"] == "green", state
            assert state["sha"] == state["verdict"]["sha"] == result["merge_sha"], state
            external = json.loads((root / 'external.json').read_text())
            assert external['prs'][state['branch']] == state['pr']
            assert external['remote'][state['branch']] == state['sha']
            assert state['sha'] == hashlib.sha1((state['branch'] + 'value = 42\n').encode()).hexdigest()
            rounds = (runs / str(issue) / "rounds.md").read_text().splitlines()
            verify_rounds(rounds, state['sha'])
            rejects(verify_rounds, [line for line in rounds if 'Fix: sha=' not in line], state['sha'])
            red_merge = list(rounds)
            red_merge = [line.replace('ci=green', 'ci=red') for line in red_merge]
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
        assert len(requests) == 36, requests  # Three branches + synthesis + seven lenses per Check, twice.
        for issue in (1, 2):
            comments = [body for n, body in external["comments"] if n == issue]
            assert len(comments) == 2, comments
            assert "**fix** · CI: **green** · tests: **red**" in comments[0], comments
            assert "**merge** · CI: **green** · tests: **green** · tested=true" in comments[1], comments
        calls = [json.loads(line) for line in (root / "calls.jsonl").read_text().splitlines()]
        pi_prompts = [args[-1] for tool, args in calls if tool == 'pi']
        assert len(pi_prompts) == 12, calls
        assert sum('Write the plan only to ' in prompt for prompt in pi_prompts) == 6, pi_prompts
        assert sum('Write JSON only to ' in prompt for prompt in pi_prompts) == 2, pi_prompts
        for issue in (1, 2):
            state = json.loads((runs / str(issue) / 'state.json').read_text())
            merges = [args for tool, args in calls
                      if tool == 'gh' and args[:3] == ['pr', 'merge', str(state['pr'])]]
            assert len(merges) == 1, merges
            assert merges[0][merges[0].index('--match-head-commit') + 1] == state['sha']
        # Compare every external operation, including order, across fresh homes.
        import re
        normalized = json.dumps(calls, sort_keys=True).replace(str(root), '<root>')
        normalized = re.sub(r'/[^" ]*/lokay-main-[^/" ]+', '<main>', normalized)
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

"""Native authored handoff: test attestation -> compare-and-merge -> close gate."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

from lokay.graph_run import _materialize_package


@pytest.mark.parametrize("head_changed", [False, True])
def test_native_review_test_merge_handoff(tmp_path, head_changed):
    pytest.importorskip("fala")
    root = Path(__file__).resolve().parents[1]
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    for args in (("init", "-q"), ("config", "user.name", "Test"),
                 ("config", "user.email", "test@example.test"),
                 ("commit", "--allow-empty", "-qm", "reviewed")):
        subprocess.run(["git", "-C", str(checkout), *args], check=True, capture_output=True)
    head = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    merged = tmp_path / "merged"
    closed = tmp_path / "closed"
    effector = tmp_path / "effector.py"
    effector.write_text(f'''
from pathlib import Path
from fala.sdk import load_manifest, output, write_result
from lokay import fala_organ
from lokay.atom_runtime import run_atom_main
from lokay.code import github
from lokay.config import Config
import lokay.config
from lokay.organ.lanes import handle_lanes
from lokay.proc import pr_merge
from lokay.proc.select_pr_triage_outcome import select
from lokay.proc.summarize_pr_triage import summarize
from lokay.runner import CommandResult
import lokay.proc.test_local_execution_subflow
m = load_manifest()
a = str(dict(m.config).get('atom') or m.job)
up = fala_organ._conduction_values(m)
head = {head!r}
review = {{'ok': True, 'merge_ok': True, 'head_sha': head,
          'decision': {{'verdict': 'approve', 'reviewed_head_sha': head}}}}
v = {{'ok': True, 'atom': a}}
if a == 'pr_checks': v.update(status='passed', green=True, head_sha=head)
if a == 'classify_pr_triage_checks': v.update(route='review', head_sha=head)
if a == 'resolve_sha_review': v['route'] = 'agent'
if a == 'select_pr_review_scope': v['route'] = 'ready'
if a == 'validate_pr_review': v.update(route='valid', decision=review['decision'])
if a in ('select_pr_review', 'select_evidence_review', 'finalize_pr_review'):
    v.update(route='publish', decision=review['decision'])
if a == 'review_evidence_catalog': v['route'] = 'not_applicable'
if a == 'publish_pr_review': v = review
if a == 'review_repair_gate': v['route'] = 'not_applicable'
if a == 'worktree_add': v.update(route='ready', worktree={str(checkout)!r})
if a == 'test_local':
    # Replace only the declared verifier; production organ owns SHA attestation.
    lokay.proc.test_local_execution_subflow.run = lambda **kw: {{'ok': True, 'tested': True}}
    v = fala_organ._handle(a, {{'repo': 'owner/repo', 'pr': 7}}, up)
if a == 'select_pr_triage_outcome':
    v = select(up['classify_pr_triage_checks'], up['review_repair_gate'], up['test_local'])
if a == 'pr_merge':
    cfg = Config(merge_enabled=True)
    lokay.config.load_config = lambda *_: cfg
    pr_merge.load_cfg = lambda *_: cfg
    pr_merge.mutations_allowed = lambda **_: True
    github.view_pr = lambda *args, **kw: {{}}
    class Remote:
        def run_checked(self, spec, *, live):
            assert spec.argv[-2:] == ('--match-head-commit', head), spec.argv
            if {head_changed!r}:
                raise RuntimeError('Head commit of pull request changed')
            Path({str(merged)!r}).write_text(head)
            return CommandResult(spec=spec, executed=True, returncode=0)
    pr_merge.runner = Remote
    v = handle_lanes(a, {{}}, up, {{'cfg': [], 'live': ['--live'], 'repo': 'owner/repo',
        'pr_number': 7, 'issue_number': None, 'branch': '', 'run_atom_main': run_atom_main}})
if a == 'close_issue':
    def close(main, argv):
        Path({str(closed)!r}).write_text('closed')
        return {{'ok': True, 'issue': 7}}
    v = handle_lanes(a, {{}}, up, {{'cfg': [], 'live': ['--live'], 'repo': 'owner/repo',
        'pr_number': 7, 'issue_number': 7, 'branch': '', 'run_atom_main': close}})
if a == 'summarize_pr_triage':
    v = summarize(review=up['publish_pr_review'], repair=up.get('pr_repair_verdict', {{}}),
        repair_manual=up.get('review_repair_manual', {{}}), manual=up.get('review_manual', {{}}),
        merge=up['pr_merge'], close=up['close_issue'], outcome=up['select_pr_triage_outcome'])
write_result(output(m, v))
''')
    package = tmp_path / "lokay.fala-package.toml"
    _materialize_package(root / "fala/lokay.fala-package.toml", package, project=root, path_id="pr_triage")
    path = tomllib.loads(package.read_text())["correlation_paths"][0]
    commands = {item["id"]: [sys.executable, str(effector)] for item in path["effectors"]}
    script = (
        "import fala,json,sys; print(json.dumps(fala.host_run_package("
        "db_path=sys.argv[1],package_path=sys.argv[2],path_id='pr_triage',"
        "run_id='merge-sha',command_overrides=json.loads(sys.argv[3]),max_ticks=40)))"
    )
    env = os.environ.copy()
    for node in path["effectors"]:
        for key in node["adapter"].get("inherit_env", []):
            env.setdefault(key, "")
    run = subprocess.run([sys.executable, "-c", script, str(tmp_path / "state.sqlite"),
                          str(package), json.dumps(commands)], cwd=root, env=env,
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout.strip().splitlines()[-1])
    statuses = {key: value["status"] for key, value in result["effector_results"].items()}
    assert statuses["test_local"] == "succeeded", result
    assert statuses["pr_merge"] == "succeeded", result
    assert statuses["summarize_pr_triage"] == "succeeded", result
    assert merged.exists() is not head_changed
    assert closed.exists() is not head_changed

"""Native Fala proofs for every visible ready-survey slot route."""

import json, os, subprocess, sys, tomllib
from pathlib import Path
import pytest


def run_ready_graph(tmp_path, body, run_id):
    pytest.importorskip("fala")
    root = Path(__file__).resolve().parents[1]
    effector = tmp_path / "effector.py"
    effector.write_text(body)
    package = tmp_path / "pkg.toml"
    package.write_text(
        (root / "fala/lokay.fala-package.toml")
        .read_text()
        .replace("PLACEHOLDER_PROJECT", str(root))
    )
    path = next(
        x
        for x in tomllib.loads(package.read_text())["correlation_paths"]
        if x["id"] == "survey_ready"
    )
    commands = {x["id"]: [sys.executable, str(effector)] for x in path["effectors"]}
    script = "import fala,json,sys;print(json.dumps(fala.host_run_package(db_path=sys.argv[1],package_path=sys.argv[2],path_id='survey_ready',run_id=sys.argv[4],command_overrides=json.loads(sys.argv[3]),max_ticks=512)))"
    env = os.environ.copy()
    for key in (
        "LOKAY_ROOT",
        "LOKAY_PROCESS_HEAD",
        "LOKAY_HOST_FF_FETCHED",
        "LOKAY_HEALTH_LEASE",
        "LOKAY_HEALTH_LEASE_PATH",
        "LOKAY_DISABLE_HEALTH_LEASE_ISSUE",
        "PYTHONPATH",
    ):
        env.setdefault(key, "")
    run = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(tmp_path / "db.sqlite"),
            str(package),
            json.dumps(commands),
            run_id,
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout.strip().splitlines()[-1])


def effector(extra):
    return (
        "import json,os\nfrom pathlib import Path\nm=json.loads(Path(os.environ['FALA_EFFECTOR_MANIFEST']).read_text());a=(m.get('config') or {}).get('atom') or m.get('process_id');v={'ok':True,'atom':a}\n"
        + extra
        + "\n(Path(os.environ['FALA_EFFECTOR_OUTPUT_DIR'])/'result.json').write_text(json.dumps({'values':v}))\n"
    )


def test_first_slot_lists_classifies_parks_and_records(tmp_path):
    listed, parked = tmp_path / "listed", tmp_path / "parked"
    body = effector(
        """if a=='prepare_ready_survey':v.update(route='survey',repos=['a/one'],active_repos=['a/one'])
if a.startswith('select_ready_repo_'):v.update(route='survey' if a.endswith('_1') else 'empty',repo='a/one' if a.endswith('_1') else '')
if a=='list_work_ready_1':v.update(route='listed');Path(%r).write_text('listed')
if a.startswith('classify_ready_repo_'):v.update(route='blocked' if a.endswith('_1') else 'empty',repo='a/one' if a.endswith('_1') else '',blocked=[{'number':7}] if a.endswith('_1') else [])
if a=='park_blocked_ready_1':v.update(applied=True);Path(%r).write_text('parked')
if a.startswith('record_ready_repo_'):v.update(route='record')
if a=='finalize_ready_survey':v.update(remaining_ready=0,survey_errors=0)
if a=='update_ready_survey_stamp':v['result']={'remaining_ready':0}"""
        % (str(listed), str(parked))
    )
    result = run_ready_graph(tmp_path, body, "ready-slot")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert listed.exists() and parked.exists()
    assert status["list_work_ready_1"] == status["park_blocked_ready_1"] == "succeeded"
    assert status["list_work_ready_2"] == status["park_blocked_ready_2"] == "skipped"
    assert status["update_ready_survey_stamp"] == "succeeded"


def test_recent_empty_skips_all_network_and_mutation_nodes(tmp_path):
    touched = tmp_path / "wrong"
    body = effector(
        """if a=='prepare_ready_survey':v.update(route='skip',repos=[],active_repos=[])
if a.startswith('select_ready_repo_'):v.update(route='empty',repo='')
if a.startswith('classify_ready_repo_'):v.update(route='empty',repo='')
if a.startswith('list_work_ready_') or a.startswith('park_blocked_ready_'):Path(%r).write_text(a)
if a.startswith('record_ready_repo_'):v.update(route='empty')
if a=='finalize_ready_survey':v.update(skipped=True,remaining_ready=0,survey_errors=0)
if a=='update_ready_survey_stamp':v['result']={'skipped':True}""" % str(touched)
    )
    result = run_ready_graph(tmp_path, body, "ready-skip")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert not touched.exists()
    assert all(status[f"list_work_ready_{i}"] == "skipped" for i in range(1, 31))
    assert status["update_ready_survey_stamp"] == "succeeded"

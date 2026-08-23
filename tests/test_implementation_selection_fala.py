"""Native Fala proofs for explicit implementation-repository slots."""

import json, os, subprocess, sys, tomllib
from pathlib import Path
import pytest
from test_issue_triage_fala import base_effector


def run_graph(tmp_path, body, run_id, path_id="select_implement"):
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
        if x["id"] == path_id
    )
    commands = {x["id"]: [sys.executable, str(effector)] for x in path["effectors"]}
    script = "import fala,json,sys;print(json.dumps(fala.host_run_package(db_path=sys.argv[1],package_path=sys.argv[2],path_id=sys.argv[5],run_id=sys.argv[4],command_overrides=json.loads(sys.argv[3]),max_ticks=512)))"
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
            path_id,
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout.strip().splitlines()[-1])


def test_first_repo_eligible_is_selected(tmp_path):
    body = base_effector(
        """if a=='prepare_implementation_selection':v.update(route='select',repos=['a/one'])
if a.startswith('select_implementation_repo_'):v.update(route='repo' if a.endswith('_1') else 'empty',repo='a/one' if a.endswith('_1') else '')
if a.startswith('inspect_implementation_eligibility_'):v.update(route='eligible',repo='a/one')
if a.startswith('select_implementation_eligibility_gate_'):v.update(route='eligible' if a.endswith('_1') else 'empty',repo='a/one' if a.endswith('_1') else '')
if a.startswith('record_eligible_implementation_repo_'):v.update(route='eligible',repo='a/one')
if a.startswith('record_ineligible_implementation_repo_'):v.update(route='empty')
if a.startswith('select_implementation_slot_outcome_'):v.update(route='eligible' if a.endswith('_1') else 'empty',repo='a/one' if a.endswith('_1') else '')
if a=='reduce_implementation_selection':v.update(route='selected',clean_repos=['a/one'])
if a=='persist_implementation_selection':v.update(selected=1)
if a=='summarize_implementation_selection':v['result']={'selected':1}"""
    )
    result = run_graph(tmp_path, body, "select-one", path_id="select_implement")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["inspect_implementation_eligibility_1"] == "succeeded"
        and status["inspect_implementation_eligibility_2"] == "skipped"
        and status["summarize_implementation_selection"] == "succeeded"
    )


def test_no_budget_skips_all_inspections(tmp_path):
    wrong = tmp_path / "wrong"
    body = base_effector(
        """if a=='prepare_implementation_selection':v.update(route='no_budget',repos=[])
if a.startswith('select_implementation_repo_'):v['route']='empty'
if a.startswith('inspect_implementation_eligibility_'):Path(%r).write_text(a)
if a.startswith('select_implementation_eligibility_gate_'):v['route']='empty'
if a.startswith('record_ineligible_implementation_repo_') or a.startswith('select_implementation_slot_outcome_'):v['route']='empty'
if a=='reduce_implementation_selection':v.update(route='no_budget',clean_repos=[])
if a=='persist_implementation_selection':v.update(selected=0)
if a=='summarize_implementation_selection':v['result']={'selected':0}""" % str(wrong)
    )
    result = run_graph(tmp_path, body, "select-none", path_id="select_implement")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        all(
            status[f"inspect_implementation_eligibility_{i}"] == "skipped"
            for i in range(1, 31)
        )
        and not wrong.exists()
    )

"""Native Fala proofs for one implementation-selection catalog atom."""

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


def test_select_implement_is_one_catalog_atom(tmp_path):
    body = base_effector(
        """if a=='prepare_implementation_selection':v.update(route='select',repos=['a/one'])
if a=='implementation_selection_catalog':v.update(route='selected',clean_repos=['a/one'])
if a=='persist_implementation_selection':v.update(selected=1)
if a=='summarize_implementation_selection':v['result']={'selected':1}"""
    )
    result = run_graph(tmp_path, body, "select-catalog", path_id="select_implement")
    order = [
        "prepare_implementation_selection",
        "implementation_selection_catalog",
        "persist_implementation_selection",
        "summarize_implementation_selection",
    ]
    statuses = result["effector_results"]
    assert all(statuses[name]["status"] == "succeeded" for name in order)
    assert set(statuses) == set(order)
    assert not any(
        name.startswith("select_implementation_repo_")
        or name.startswith("inspect_implementation_eligibility_")
        or name.startswith("select_implementation_eligibility_gate_")
        or name.startswith("record_eligible_implementation_repo_")
        or name.startswith("record_ineligible_implementation_repo_")
        or name.startswith("select_implementation_slot_outcome_")
        or name.startswith("reduce_implementation_selection")
        for name in statuses
    )
    assert result.get("ticks_used", 16) <= 16


def test_select_implement_no_budget_finishes_without_184_effectors(tmp_path):
    body = base_effector(
        """if a=='prepare_implementation_selection':v.update(route='no_budget',repos=[])
if a=='implementation_selection_catalog':v.update(route='no_budget',clean_repos=[])
if a=='persist_implementation_selection':v.update(selected=0)
if a=='summarize_implementation_selection':v['result']={'selected':0}"""
    )
    result = run_graph(tmp_path, body, "select-none", path_id="select_implement")
    statuses = result["effector_results"]
    assert len(statuses) == 4
    assert statuses["implementation_selection_catalog"]["status"] == "succeeded"
    assert statuses["summarize_implementation_selection"]["status"] == "succeeded"
    assert result.get("ticks_used", 16) < 64

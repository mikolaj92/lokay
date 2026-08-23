"""Native Fala proof that a nonmatching PR outcome adapter never runs."""

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


def test_request_changes_runs_repair_branch_not_merge(tmp_path):
    pytest.importorskip("fala")
    root = Path(__file__).resolve().parents[1]
    sentinel = tmp_path / "merge-ran"
    effector = tmp_path / "effector.py"
    effector.write_text(
        "import json,os\nfrom pathlib import Path\n"
        "m=json.loads(Path(os.environ['FALA_EFFECTOR_MANIFEST']).read_text())\n"
        "a=(m.get('config') or {}).get('atom') or m.get('process_id')\n"
        "v={'ok':True,'atom':a}\n"
        "if a=='resolve_sha_review': v['route']='agent'\n"
        "if a=='verify_review_evidence_sha': v['route']='not_applicable'\n"
        "if a in {'validate_pr_review','validate_pr_review_retry'}: v.update(route='valid',decision={'verdict':'request_changes'})\n"
        "if a=='select_pr_review': v.update(route='publish',evidence_kind='none',decision={'verdict':'request_changes'})\n"
        "if a=='finalize_pr_review': v.update(route='publish',evidence_kind='none',decision={'verdict':'request_changes'})\n"
        "if a=='publish_pr_review': v['decision']={'verdict':'request_changes'}\n"
        "if a=='review_repair_gate': v['route']='repair'\n"
        "if a=='pr_merge': Path(" + repr(str(sentinel)) + ").write_text('ran')\n"
        "(Path(os.environ['FALA_EFFECTOR_OUTPUT_DIR'])/'result.json').write_text(json.dumps({'values':v}))\n",
        encoding="utf-8",
    )
    package = tmp_path / "lokay.fala-package.toml"
    package.write_text(
        (root / "fala/lokay.fala-package.toml").read_text().replace("PLACEHOLDER_PROJECT", str(root)),
        encoding="utf-8",
    )
    data = tomllib.loads(package.read_text())
    path = next(item for item in data["correlation_paths"] if item["id"] == "pr_triage")
    commands = {item["id"]: [sys.executable, str(effector)] for item in path["effectors"]}
    script = (
        "import fala,json,sys; print(json.dumps(fala.host_run_package("
        "db_path=sys.argv[1],package_path=sys.argv[2],path_id='pr_triage',"
        "run_id='request-changes',command_overrides=json.loads(sys.argv[3]),max_ticks=32)))"
    )
    env = os.environ.copy()
    for key in (
        "LOKAY_ROOT", "LOKAY_PROCESS_HEAD", "LOKAY_HOST_FF_FETCHED",
        "LOKAY_HEALTH_LEASE", "LOKAY_HEALTH_LEASE_PATH",
        "LOKAY_DISABLE_HEALTH_LEASE_ISSUE",
    ):
        env.setdefault(key, "")
    run = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "state.sqlite"), str(package), json.dumps(commands)],
        cwd=root, env=env, capture_output=True, text=True, check=True,
    )
    result = json.loads(run.stdout.strip().splitlines()[-1])
    statuses = {key: value["status"] for key, value in result["effector_results"].items()}
    assert statuses["pr_repair_subflow"] == "succeeded"
    assert statuses["pr_merge"] == "skipped"
    assert statuses["worktree_add"] == "skipped"
    assert not sentinel.exists()


def test_invalid_review_runs_one_retry_then_approve_branch(tmp_path):
    pytest.importorskip("fala")
    root = Path(__file__).resolve().parents[1]
    retry_sentinel = tmp_path / "retry-ran"
    merge_sentinel = tmp_path / "merge-ran"
    effector = tmp_path / "effector.py"
    effector.write_text(
        "import json,os\nfrom pathlib import Path\n"
        "m=json.loads(Path(os.environ['FALA_EFFECTOR_MANIFEST']).read_text())\n"
        "a=(m.get('config') or {}).get('atom') or m.get('process_id')\n"
        "v={'ok':True,'atom':a}\n"
        "if a=='resolve_sha_review': v['route']='agent'\n"
        "if a=='verify_review_evidence_sha': v['route']='not_applicable'\n"
        "if a=='validate_pr_review': v.update(route='retry',validation_error='bad json')\n"
        "if a=='pr_review_retry_agent': Path(" + repr(str(retry_sentinel)) + ").write_text('ran')\n"
        "if a=='validate_pr_review_retry': v.update(route='valid',decision={'verdict':'approve'})\n"
        "if a=='select_pr_review': v.update(route='publish',evidence_kind='none',decision={'verdict':'approve'})\n"
        "if a=='finalize_pr_review': v.update(route='publish',evidence_kind='none',decision={'verdict':'approve'})\n"
        "if a=='publish_pr_review': v['decision']={'verdict':'approve'}\n"
        "if a=='review_repair_gate': v['route']='not_applicable'\n"
        "if a=='pr_merge': v['merged']=True; Path(" + repr(str(merge_sentinel)) + ").write_text('ran')\n"
        "(Path(os.environ['FALA_EFFECTOR_OUTPUT_DIR'])/'result.json').write_text(json.dumps({'values':v}))\n",
        encoding="utf-8",
    )
    package = tmp_path / "lokay.fala-package.toml"
    package.write_text((root / "fala/lokay.fala-package.toml").read_text().replace("PLACEHOLDER_PROJECT", str(root)), encoding="utf-8")
    path = next(item for item in tomllib.loads(package.read_text())["correlation_paths"] if item["id"] == "pr_triage")
    commands = {item["id"]: [sys.executable, str(effector)] for item in path["effectors"]}
    script = (
        "import fala,json,sys; print(json.dumps(fala.host_run_package("
        "db_path=sys.argv[1],package_path=sys.argv[2],path_id='pr_triage',"
        "run_id='invalid-retry',command_overrides=json.loads(sys.argv[3]),max_ticks=32)))"
    )
    env = os.environ.copy()
    for key in ("LOKAY_ROOT", "LOKAY_PROCESS_HEAD", "LOKAY_HOST_FF_FETCHED", "LOKAY_HEALTH_LEASE", "LOKAY_HEALTH_LEASE_PATH", "LOKAY_DISABLE_HEALTH_LEASE_ISSUE"):
        env.setdefault(key, "")
    run = subprocess.run([sys.executable, "-c", script, str(tmp_path / "state.sqlite"), str(package), json.dumps(commands)], cwd=root, env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    result=json.loads(run.stdout.strip().splitlines()[-1]); statuses={k:v["status"] for k,v in result["effector_results"].items()}
    assert statuses["pr_review_retry_agent"] == "succeeded"
    assert statuses["pr_repair_subflow"] == "skipped"
    assert statuses["pr_merge"] == "succeeded"
    assert retry_sentinel.exists() and merge_sentinel.exists()


def test_cached_sha_verdict_skips_both_review_agents(tmp_path):
    pytest.importorskip("fala")
    root=Path(__file__).resolve().parents[1]; agent_sentinel=tmp_path/"agent-ran"; repair_sentinel=tmp_path/"repair-ran"
    effector=tmp_path/"effector.py"
    effector.write_text(
        "import json,os\nfrom pathlib import Path\n"
        "m=json.loads(Path(os.environ['FALA_EFFECTOR_MANIFEST']).read_text()); a=(m.get('config') or {}).get('atom') or m.get('process_id'); v={'ok':True,'atom':a}\n"
        "if a=='resolve_sha_review': v.update(route='cached',evidence_kind='none',decision={'verdict':'request_changes'},merge_ok=False)\n"
        "if a=='validate_pr_review': v['route']='not_applicable'\n"
        "if a=='verify_review_evidence_sha': v['route']='not_applicable'\n"
        "if a in {'pr_review_agent','pr_review_retry_agent'}: Path("+repr(str(agent_sentinel))+").write_text('ran')\n"
        "if a=='select_pr_review': v.update(route='cached',evidence_kind='none',decision={'verdict':'request_changes'},merge_ok=False)\n"
        "if a=='finalize_pr_review': v.update(route='cached',evidence_kind='none',decision={'verdict':'request_changes'},merge_ok=False)\n"
        "if a=='publish_pr_review': v['decision']={'verdict':'request_changes'}\n"
        "if a=='review_repair_gate': v['route']='repair'\n"
        "if a=='pr_repair_subflow': Path("+repr(str(repair_sentinel))+").write_text('ran')\n"
        "(Path(os.environ['FALA_EFFECTOR_OUTPUT_DIR'])/'result.json').write_text(json.dumps({'values':v}))\n",encoding='utf-8')
    package=tmp_path/'pkg.toml'; package.write_text((root/'fala/lokay.fala-package.toml').read_text().replace('PLACEHOLDER_PROJECT',str(root)))
    path=next(x for x in tomllib.loads(package.read_text())['correlation_paths'] if x['id']=='pr_triage'); commands={x['id']:[sys.executable,str(effector)] for x in path['effectors']}
    script="import fala,json,sys; print(json.dumps(fala.host_run_package(db_path=sys.argv[1],package_path=sys.argv[2],path_id='pr_triage',run_id='cached',command_overrides=json.loads(sys.argv[3]),max_ticks=32)))"
    env=os.environ.copy()
    for key in ("LOKAY_ROOT","LOKAY_PROCESS_HEAD","LOKAY_HOST_FF_FETCHED","LOKAY_HEALTH_LEASE","LOKAY_HEALTH_LEASE_PATH","LOKAY_DISABLE_HEALTH_LEASE_ISSUE"): env.setdefault(key,'')
    run=subprocess.run([sys.executable,'-c',script,str(tmp_path/'db.sqlite'),str(package),json.dumps(commands)],cwd=root,env=env,capture_output=True,text=True); assert run.returncode==0,run.stderr
    result=json.loads(run.stdout.strip().splitlines()[-1]); statuses={k:v['status'] for k,v in result['effector_results'].items()}
    assert statuses['pr_review_agent']=='skipped' and statuses['pr_review_retry_agent']=='skipped'
    assert statuses['pr_repair_subflow']=='succeeded'; assert repair_sentinel.exists() and not agent_sentinel.exists()


def test_needs_evidence_runs_only_selected_collector_then_one_agent(tmp_path):
    pytest.importorskip("fala")
    root=Path(__file__).resolve().parents[1]
    selected_sentinel=tmp_path/"selected-collector"
    wrong_sentinel=tmp_path/"wrong-collector"
    evidence_agent_sentinel=tmp_path/"evidence-agent"
    merge_sentinel=tmp_path/"merge"
    effector=tmp_path/"effector.py"
    effector.write_text(
        "import json,os\nfrom pathlib import Path\n"
        "m=json.loads(Path(os.environ['FALA_EFFECTOR_MANIFEST']).read_text()); a=(m.get('config') or {}).get('atom') or m.get('process_id'); v={'ok':True,'atom':a}\n"
        "if a=='resolve_sha_review': v['route']='agent'\n"
        "if a=='verify_review_evidence_sha': v['route']='not_applicable'\n"
        "if a=='validate_pr_review': v.update(route='valid',decision={'verdict':'needs_evidence','evidence_kind':'diff_tail'})\n"
        "if a=='select_pr_review': v.update(route='evidence',evidence_kind='diff_tail',decision={'verdict':'needs_evidence','evidence_kind':'diff_tail'})\n"
        "if a=='collect_review_diff_tail': Path("+repr(str(selected_sentinel))+").write_text('ran')\n"
        "if a in {'collect_review_pr_metadata','collect_review_changed_files','collect_review_commit_summary'}: Path("+repr(str(wrong_sentinel))+").write_text(a)\n"
        "if a=='verify_review_evidence_sha': v['route']='agent'\n"
        "if a=='evidence_review_agent': Path("+repr(str(evidence_agent_sentinel))+").write_text('ran')\n"
        "if a=='validate_evidence_review': v.update(route='valid',decision={'verdict':'approve'})\n"
        "if a=='select_evidence_review': v.update(route='publish',decision={'verdict':'approve'})\n"
        "if a=='finalize_pr_review': v.update(route='publish',decision={'verdict':'approve'})\n"
        "if a=='publish_pr_review': v['decision']={'verdict':'approve'}\n"
        "if a=='review_repair_gate': v['route']='not_applicable'\n"
        "if a=='pr_merge': Path("+repr(str(merge_sentinel))+").write_text('ran')\n"
        "(Path(os.environ['FALA_EFFECTOR_OUTPUT_DIR'])/'result.json').write_text(json.dumps({'values':v}))\n",encoding='utf-8')
    package=tmp_path/'pkg.toml'; package.write_text((root/'fala/lokay.fala-package.toml').read_text().replace('PLACEHOLDER_PROJECT',str(root)))
    path=next(x for x in tomllib.loads(package.read_text())['correlation_paths'] if x['id']=='pr_triage'); commands={x['id']:[sys.executable,str(effector)] for x in path['effectors']}
    script="import fala,json,sys; print(json.dumps(fala.host_run_package(db_path=sys.argv[1],package_path=sys.argv[2],path_id='pr_triage',run_id='evidence',command_overrides=json.loads(sys.argv[3]),max_ticks=64)))"
    env=os.environ.copy()
    for key in ("LOKAY_ROOT","LOKAY_PROCESS_HEAD","LOKAY_HOST_FF_FETCHED","LOKAY_HEALTH_LEASE","LOKAY_HEALTH_LEASE_PATH","LOKAY_DISABLE_HEALTH_LEASE_ISSUE","PYTHONPATH"): env.setdefault(key,'')
    run=subprocess.run([sys.executable,'-c',script,str(tmp_path/'db.sqlite'),str(package),json.dumps(commands)],cwd=root,env=env,capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    result=json.loads(run.stdout.strip().splitlines()[-1]); statuses={k:v['status'] for k,v in result['effector_results'].items()}
    assert statuses['collect_review_diff_tail']=='succeeded'
    assert statuses['collect_review_pr_metadata']=='skipped'
    assert statuses['collect_review_changed_files']=='skipped'
    assert statuses['collect_review_commit_summary']=='skipped'
    assert selected_sentinel.exists() and evidence_agent_sentinel.exists() and merge_sentinel.exists()
    assert not wrong_sentinel.exists()

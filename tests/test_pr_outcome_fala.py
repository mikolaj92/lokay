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
        "if a=='pr_review': v['decision']={'verdict':'request_changes'}\n"
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

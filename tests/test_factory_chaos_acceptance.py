"""Canonical hermetic chaos acceptance over authored Fala path identities."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run(tmp_path, body: str, run_id: str, path_id: str) -> dict:
    """Drive one authored path through native Fala with a stub effector."""
    pytest.importorskip("fala")
    effector = tmp_path / "effector.py"
    effector.write_text(body)
    from lokay.graph_run import _materialize_package

    package = _materialize_package(
        ROOT / "fala/lokay.fala-package.toml", tmp_path / "pkg.toml",
        project=ROOT, path_id=path_id,
    )
    path = next(
        item for item in tomllib.loads(package.read_text())["correlation_paths"]
        if item["id"] == path_id
    )
    commands = {item["id"]: [sys.executable, str(effector)] for item in path["effectors"]}
    script = (
        "import fala,json,sys;print(json.dumps(fala.host_run_package("
        "db_path=sys.argv[1],package_path=sys.argv[2],path_id=sys.argv[5],"
        "run_id=sys.argv[4],command_overrides=json.loads(sys.argv[3]),max_ticks=64)))"
    )
    env = os.environ.copy()
    env.pop("DYLD_LIBRARY_PATH", None)
    env.pop("DYLD_FALLBACK_LIBRARY_PATH", None)
    for key in (
        "LOKAY_ROOT", "LOKAY_PROCESS_HEAD", "LOKAY_HOST_FF_FETCHED",
        "LOKAY_HEALTH_LEASE", "LOKAY_HEALTH_LEASE_PATH",
        "LOKAY_DISABLE_HEALTH_LEASE_ISSUE", "PYTHONPATH", "OCR_LLM_API_KEY",
    ):
        env.setdefault(key, "")
    run = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "db.sqlite"), str(package),
         json.dumps(commands), run_id, path_id],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout.strip().splitlines()[-1])


def _effector(route: str) -> str:
    return (
        "import json\n"
        "from fala.sdk import load_manifest, output, write_result\n"
        "m=load_manifest(); a=str(dict(m.config).get('atom') or m.job)\n"
        "v={'ok':True,'atom':a}\n"
        f"if a=='resolve_existing_delivery': v['route']={route!r}\n"
        "write_result(output(m, v))\n"
    )


def _fired(result: dict) -> set[str]:
    """Nodes Fala actually dispatched and that succeeded. Not a hand counter."""
    return {
        name
        for name, row in result["effector_results"].items()
        if row.get("status") == "succeeded"
    }


def test_issue_to_pr_deliver_fires_the_subflow_not_the_closeout(tmp_path):
    fired = _fired(_run(tmp_path, _effector("deliver"), "chaos-deliver", "issue_to_pr"))
    assert "issue_to_pr_subflow" in fired
    assert "close_existing_delivery" not in fired
    assert "issue_to_pr_no_effect" not in fired


def test_issue_to_pr_closeout_fires_only_the_closeout(tmp_path):
    fired = _fired(_run(tmp_path, _effector("closeout"), "chaos-closeout", "issue_to_pr"))
    assert "close_existing_delivery" in fired
    assert "issue_to_pr_subflow" not in fired


def test_issue_to_pr_no_effect_fires_nothing(tmp_path):
    fired = _fired(_run(tmp_path, _effector("no_effect"), "chaos-none", "issue_to_pr"))
    assert "issue_to_pr_no_effect" in fired
    assert "issue_to_pr_subflow" not in fired
    assert "close_existing_delivery" not in fired

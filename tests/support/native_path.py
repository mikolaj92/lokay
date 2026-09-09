"""Drive one authored path through Fala with a FEP/1 fixture organ."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


_INHERIT = (
    "LOKAY_ROOT",
    "LOKAY_PROCESS_HEAD",
    "LOKAY_HOST_FF_FETCHED",
    "LOKAY_HEALTH_LEASE",
    "LOKAY_HEALTH_LEASE_PATH",
    "LOKAY_DISABLE_HEALTH_LEASE_ISSUE",
    "PYTHONPATH",
)


def effector_source(values_path: Path, ran_path: Path) -> str:
    """Return a FEP/1 organ that publishes JSON values and logs ran ids."""
    return (
        "import hashlib, json\n"
        "from pathlib import Path\n"
        "from fala.fep import build_result\n"
        "from fala.sdk import load_manifest, write_result\n"
        f"VALUES = json.loads(Path({json.dumps(str(values_path))}).read_text())\n"
        f"RAN = {json.dumps(str(ran_path))}\n"
        "m = load_manifest()\n"
        "pid = str(m.get('process_id') or '')\n"
        "short = pid.split(':')[-1]\n"
        "atom = str((m.get('config') or {}).get('atom') or short)\n"
        "v = {'ok': True, 'atom': atom, 'route': 'fixture', 'effect': None}\n"
        "for key in (pid, short, atom):\n"
        "    extra = VALUES.get(key)\n"
        "    if extra: v.update(extra)\n"
        "Path(RAN).open('a').write(short + chr(10))\n"
        "req = {'protocol': 'fala-effector/1', 'message_kind': 'effector.request', "
        "'run_id': str(m.get('run_id') or 'run'), 'process_id': m['process_id'], "
        "'execution_id': m['execution_id'], 'attempt': m['attempt'], "
        "'impulse_id': m.get('impulse_id', ''), 'process_fingerprint': 'process:test', "
        "'path_digest': 'path:test', 'capability': 'lokay_atom', "
        "'input': m.get('input') or {}, 'config': m.get('config') or {}, "
        "'output_contract_ref': 'schema:test'}\n"
        "body = json.dumps(req, ensure_ascii=False, separators=(',', ':'), sort_keys=True)\n"
        "req['message_id'] = 'msg:sha256:' + hashlib.sha256(body.encode()).hexdigest()\n"
        "write_result(build_result(req, values=v))\n"
    )


def _rewrite_placeholders(obj: Any, project: Path) -> Any:
    project_text = str(project)
    if isinstance(obj, str):
        if obj == "PLACEHOLDER_PROJECT" or obj.endswith("PLACEHOLDER_PROJECT"):
            return project_text
        return obj.replace("PLACEHOLDER_PROJECT", project_text)
    if isinstance(obj, list):
        return [_rewrite_placeholders(item, project) for item in obj]
    if isinstance(obj, dict):
        return {key: _rewrite_placeholders(value, project) for key, value in obj.items()}
    return obj


def expanded_path_package(root: Path, path_id: str, dest: Path) -> Path:
    """Write one expanded correlation path as a JSON package Fala can host."""
    expanded = json.loads((root / "fala/lokay.expanded.golden.json").read_text(encoding="utf-8"))
    path = next(item for item in expanded["correlation_paths"] if item["id"] == path_id)
    package = {
        "version": expanded.get("version", "2"),
        "id": expanded.get("id", "lokay"),
        "title": expanded.get("title", "Lokay"),
        "capabilities": expanded.get("capabilities") or [{"id": "lokay_atom"}],
        "correlation_paths": [_rewrite_placeholders(path, root)],
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


def run_overridden_path(
    tmp_path: Path,
    path_id: str,
    values: Mapping[str, Mapping[str, Any]],
    *,
    run_id: str,
    max_ticks: int = 256,
) -> dict[str, Any]:
    """Drive one expanded path with command_overrides and a FEP/1 fixture organ."""
    import pytest

    pytest.importorskip("fala")
    root = Path(__file__).resolve().parents[2]
    work = Path(tmp_path) / run_id
    work.mkdir(parents=True, exist_ok=True)
    ran = work / "ran.log"
    ran.write_text("", encoding="utf-8")
    values_path = work / "values.json"
    values_path.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
    effector = work / "effector.py"
    effector.write_text(effector_source(values_path, ran), encoding="utf-8")
    package = expanded_path_package(root, path_id, work / "pkg.json")
    data = json.loads(package.read_text(encoding="utf-8"))
    path = next(item for item in data["correlation_paths"] if item["id"] == path_id)
    commands = {item["id"]: [sys.executable, str(effector)] for item in path.get("effectors", [])}
    script = (
        "import fala, json, sys\n"
        "print(json.dumps(fala.host_run_package("
        "db_path=sys.argv[1], package_path=sys.argv[2], path_id=sys.argv[5], "
        "run_id=sys.argv[4], command_overrides=json.loads(sys.argv[3]), "
        f"max_ticks={int(max_ticks)})))\n"
    )
    env = os.environ.copy()
    env.pop("DYLD_LIBRARY_PATH", None)
    env.pop("DYLD_FALLBACK_LIBRARY_PATH", None)
    for key in _INHERIT:
        env.setdefault(key, "")
    run = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(work / "state.sqlite"),
            str(package),
            json.dumps(commands),
            run_id,
            path_id,
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout.strip().splitlines()[-1])
    result["_ran"] = [line for line in ran.read_text(encoding="utf-8").splitlines() if line]
    return result

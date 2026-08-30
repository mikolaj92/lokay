"""Native Fala proofs for composed one-job factory-begin atoms."""

import tomllib
from pathlib import Path

from test_factory_pass_fala import _require_fala_host
from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


NODES = (
    "probe_factory_host",
    "load_factory_config",
    "select_factory_scope",
    "read_factory_stuck",
    "create_factory_pass_dir",
    "build_factory_begin_state",
    "build_factory_working_state",
    "seed_factory_occupancy",
    "attach_factory_stuck",
    "persist_factory_begin_state",
    "persist_factory_working_state",
    "persist_factory_tick",
    "classify_leftover_remaining",
    "merge_leftover_remaining",
)

CEREMONY = (
    "inspect_factory_lease",
    "restore_factory_lease",
    "run_factory_preflight",
    "classify_factory_mode",
    "harvest_factory_children",
    "select_factory_survey_repos",
    "classify_factory_begin_terminal",
    "build_factory_begin_terminal_preflight_failed",
    "build_factory_begin_terminal_mode_not_live",
    "build_factory_begin_terminal_offline",
    "build_factory_begin_terminal_ready",
    "select_factory_begin_terminal",
)


def _factory_begin_path() -> dict:
    root = Path(__file__).resolve().parents[1]
    pkg = tomllib.loads(
        (root / "fala" / "lokay.fala-package.toml").read_text(encoding="utf-8")
    )
    return next(p for p in pkg["correlation_paths"] if p["id"] == "factory_begin")


def test_factory_begin_leaves_have_no_idle_skip():
    path = _factory_begin_path()
    ids = [node["id"] for node in path["effectors"]]
    assert ids == list(NODES)
    assert not set(CEREMONY).intersection(ids)
    when = {node["id"]: node.get("when") for node in path["effectors"]}
    assert all(not when[name] for name in NODES)
    assert "harvest_factory_children" not in ids
    for node in path["effectors"]:
        assert (node.get("adapter") or {}).get("kind") == "subprocess"
        assert (node.get("config") or {}).get("atom") == node["id"]
    conduction = {node["id"]: list(node.get("conduction") or []) for node in path["effectors"]}
    assert conduction["persist_factory_begin_state"] == [
        "create_factory_pass_dir",
        "attach_factory_stuck",
    ]
    assert "persist_factory_begin_state" in conduction["persist_factory_working_state"]
    assert "persist_factory_working_state" in conduction["persist_factory_tick"]
    assert "build_factory_begin_state" in conduction["attach_factory_stuck"]
    assert "seed_factory_occupancy" in conduction["attach_factory_stuck"]


def test_workspace_persists_without_lease_or_terminals(tmp_path):
    _require_fala_host()
    body = base_effector(
        """if a=='probe_factory_host':v.update(route='up',offline=False)
if a=='load_factory_config':v.update(mode='dry-run',live=False,state_path='/s')
if a=='select_factory_scope':v['repos']=['a/b']
if a=='read_factory_stuck':v.update(stuck_path='/s',issue_count=0)
if a=='create_factory_pass_dir':v['pass_dir']='/pass'
if a=='build_factory_begin_state':v['begin']={'planned':[],'pass_dir':'/pass'}
if a=='build_factory_working_state':v['working']={}
if a=='seed_factory_occupancy':v['working']={}
if a=='attach_factory_stuck':v.update(begin={},working={})
if a=='persist_factory_begin_state':v['pass_dir']='/pass'
if a=='persist_factory_working_state':v['pass_dir']='/pass'
if a=='persist_factory_tick':v.update(ok=True,pass_dir='/pass',idle=False)
if a=='classify_leftover_remaining':v.update(route='keep')
if a=='merge_leftover_remaining':v.update(written=False,route='keep')"""
    )
    result = run_graph(tmp_path, body, "factory-begin-ready", path_id="factory_begin")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert set(status) == set(NODES)
    assert all(status[name] == "succeeded" for name in NODES)
    for name in CEREMONY:
        assert name not in status


def test_empty_survey_does_not_skip_workspace(tmp_path):
    _require_fala_host()
    body = base_effector(
        """if a=='probe_factory_host':v.update(route='up')
if a=='load_factory_config':v.update(mode='dry-run',live=False,state_path='/s',repos=[])
if a=='select_factory_scope':v['repos']=[]
if a=='read_factory_stuck':v.update(stuck_path='/s',issue_count=0)
if a=='create_factory_pass_dir':v['pass_dir']='/pass'
if a=='build_factory_begin_state':v['begin']={'planned':[]}
if a=='build_factory_working_state':v['working']={}
if a=='seed_factory_occupancy':v['working']={}
if a=='attach_factory_stuck':v.update(begin={},working={})
if a=='persist_factory_begin_state':v['pass_dir']='/pass'
if a=='persist_factory_working_state':v['pass_dir']='/pass'
if a=='persist_factory_tick':v.update(ok=True,pass_dir='/pass',idle=False,planned=[])
if a=='classify_leftover_remaining':v.update(route='keep')
if a=='merge_leftover_remaining':v.update(written=False,route='keep')"""
    )
    result = run_graph(tmp_path, body, "factory-begin-empty", path_id="factory_begin")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert status["create_factory_pass_dir"] == "succeeded"
    assert status["persist_factory_begin_state"] == "succeeded"
    assert status["persist_factory_tick"] == "succeeded"

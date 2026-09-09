"""Native Fala proofs for explicit issue-triage branches."""
import json,os,subprocess,sys,tomllib
from pathlib import Path
import pytest

def run_graph(tmp_path, body: str, run_id: str, path_id: str = "issue_triage"):
    pytest.importorskip("fala"); root=Path(__file__).resolve().parents[1]; effector=tmp_path/"effector.py"; effector.write_text(body)
    from lokay.graph_run import _materialize_package
    package = _materialize_package(root / "fala/lokay.fala-package.toml", tmp_path / "pkg.toml", project=root, path_id=path_id)
    path=next(x for x in tomllib.loads(package.read_text())["correlation_paths"] if x["id"]==path_id); commands={x["id"]:[sys.executable,str(effector)] for x in path["effectors"]}
    script="import fala,json,sys;print(json.dumps(fala.host_run_package(db_path=sys.argv[1],package_path=sys.argv[2],path_id=sys.argv[5],run_id=sys.argv[4],command_overrides=json.loads(sys.argv[3]),max_ticks=64)))"
    env=os.environ.copy()
    env.pop("DYLD_LIBRARY_PATH", None); env.pop("DYLD_FALLBACK_LIBRARY_PATH", None)
    for key in ("LOKAY_ROOT","LOKAY_PROCESS_HEAD","LOKAY_HOST_FF_FETCHED","LOKAY_HEALTH_LEASE","LOKAY_HEALTH_LEASE_PATH","LOKAY_DISABLE_HEALTH_LEASE_ISSUE","PYTHONPATH"):env.setdefault(key,"")
    run=subprocess.run([sys.executable,"-c",script,str(tmp_path/"db.sqlite"),str(package),json.dumps(commands),run_id,path_id],cwd=root,env=env,capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    return json.loads(run.stdout.strip().splitlines()[-1])

def base_effector(extra: str) -> str:
    """Build a FEP/1 subprocess effector from Fala's adapter manifest."""
    return (
        "import hashlib,json,os\nfrom pathlib import Path\n"
        "from fala.fep import build_result\n"
        "from fala.sdk import load_manifest, write_result\n"
        "m=load_manifest(); a=(m.get('config') or {}).get('atom') or m.get('process_id'); v={'ok':True,'atom':a}\n"
        "req={'protocol':'fala-effector/1','message_kind':'effector.request','run_id':os.environ.get('RUN_ID','run'),'process_id':m['process_id'],'execution_id':m['execution_id'],'attempt':m['attempt'],'impulse_id':m.get('impulse_id',''),'process_fingerprint':'process:test','path_digest':'path:test','capability':'lokay_atom','input':m.get('input') or {},'config':m.get('config') or {},'output_contract_ref':'schema:test'}\n"
        "body=json.dumps(req,ensure_ascii=False,separators=(',',':'),sort_keys=True); req['message_id']='msg:sha256:'+hashlib.sha256(body.encode()).hexdigest()\n"
        "if a=='plan_issue_split':v.update(route='not_applicable',child_1='absent',child_2='absent',child_3='absent',child_4='absent',child_5='absent')\n"
        + extra
        + "\nwrite_result(build_result(req, values=v))\n"
    )

"""Native Fala proofs for explicit issue-triage branches."""
import json,os,subprocess,sys,tomllib
from pathlib import Path
import pytest

def run_graph(tmp_path, body: str, run_id: str, path_id: str = "issue_triage"):
    pytest.importorskip("fala"); root=Path(__file__).resolve().parents[1]; effector=tmp_path/"effector.py"; effector.write_text(body)
    package=tmp_path/"pkg.toml"; package.write_text((root/"fala/lokay.fala-package.toml").read_text().replace("PLACEHOLDER_PROJECT",str(root)))
    path=next(x for x in tomllib.loads(package.read_text())["correlation_paths"] if x["id"]==path_id); commands={x["id"]:[sys.executable,str(effector)] for x in path["effectors"]}
    script="import fala,json,sys;print(json.dumps(fala.host_run_package(db_path=sys.argv[1],package_path=sys.argv[2],path_id=sys.argv[5],run_id=sys.argv[4],command_overrides=json.loads(sys.argv[3]),max_ticks=64)))"
    env=os.environ.copy()
    for key in ("LOKAY_ROOT","LOKAY_PROCESS_HEAD","LOKAY_HOST_FF_FETCHED","LOKAY_HEALTH_LEASE","LOKAY_HEALTH_LEASE_PATH","LOKAY_DISABLE_HEALTH_LEASE_ISSUE","PYTHONPATH"):env.setdefault(key,"")
    run=subprocess.run([sys.executable,"-c",script,str(tmp_path/"db.sqlite"),str(package),json.dumps(commands),run_id,path_id],cwd=root,env=env,capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    return json.loads(run.stdout.strip().splitlines()[-1])

def base_effector(extra: str) -> str:
    return "import json,os\nfrom pathlib import Path\nm=json.loads(Path(os.environ['FALA_EFFECTOR_MANIFEST']).read_text());a=(m.get('config') or {}).get('atom') or m.get('process_id');v={'ok':True,'atom':a}\nif a=='plan_issue_split':v.update(route='not_applicable',child_1='absent',child_2='absent',child_3='absent',child_4='absent',child_5='absent')\n"+extra+"\n(Path(os.environ['FALA_EFFECTOR_OUTPUT_DIR'])/'result.json').write_text(json.dumps({'values':v}))\n"

def test_ready_runs_only_ready_effect(tmp_path):
    wrong=tmp_path/"wrong"; ready=tmp_path/"ready"
    body=base_effector("""if a=='resolve_issue_candidate':v['route']='evaluate'
if a in {'collect_issue_linked_prs','collect_issue_covering_prs'}:v['collected']=True
if a=='resolve_issue_hard_facts':v['route']='agent'
if a=='validate_issue_triage':v.update(route='valid',decision={'verdict':'ready'})
if a=='select_issue_triage':v.update(route='publish',evidence_kind='none',decision={'verdict':'ready'})
if a=='verify_issue_evidence':v['route']='not_applicable'
if a=='select_issue_evidence':v['route']='not_applicable'
if a=='finalize_issue_triage':v['decision']={'verdict':'ready'}
if a=='apply_issue_ready':Path(%r).write_text('ran')
if a in {'apply_issue_close','apply_issue_blocked','apply_issue_manual'}:Path(%r).write_text(a)"""%(str(ready),str(wrong)))
    result=run_graph(tmp_path,body,"ready"); statuses={k:v['status'] for k,v in result['effector_results'].items()}
    assert statuses['apply_issue_ready']=='succeeded' and statuses['apply_issue_close']=='skipped' and statuses['apply_issue_blocked']=='skipped' and statuses['issue_split_subflow']=='skipped'
    assert ready.exists() and not wrong.exists()

def test_invalid_json_runs_exactly_one_retry_then_close(tmp_path):
    retry=tmp_path/"retry"; close=tmp_path/"close"
    body=base_effector("""if a=='resolve_issue_candidate':v['route']='evaluate'
if a in {'collect_issue_linked_prs','collect_issue_covering_prs'}:v['collected']=True
if a=='resolve_issue_hard_facts':v['route']='agent'
if a=='validate_issue_triage':v.update(route='retry',validation_error='bad')
if a=='issue_triage_retry_agent':Path(%r).write_text('ran')
if a=='validate_issue_triage_retry':v.update(route='valid',decision={'verdict':'close'})
if a=='select_issue_triage':v.update(route='publish',evidence_kind='none',decision={'verdict':'close'})
if a=='verify_issue_evidence':v['route']='not_applicable'
if a=='select_issue_evidence':v['route']='not_applicable'
if a=='finalize_issue_triage':v['decision']={'verdict':'close'}
if a=='apply_issue_close':Path(%r).write_text('ran')"""%(str(retry),str(close)))
    result=run_graph(tmp_path,body,"retry"); statuses={k:v['status'] for k,v in result['effector_results'].items()}
    assert statuses['issue_triage_retry_agent']=='succeeded' and statuses['apply_issue_close']=='succeeded'
    assert retry.exists() and close.exists()

def test_evidence_runs_only_selected_collector_once(tmp_path):
    chosen=tmp_path/"chosen"; wrong=tmp_path/"wrong"; agent=tmp_path/"agent"
    body=base_effector("""if a=='resolve_issue_candidate':v['route']='evaluate'
if a in {'collect_issue_linked_prs','collect_issue_covering_prs'}:v.update(collected=True,additional_evidence={})
if a=='resolve_issue_hard_facts':v['route']='agent'
if a=='validate_issue_triage':v.update(route='valid',decision={'verdict':'needs_evidence','evidence_kind':'named_paths'})
if a=='select_issue_triage':v.update(route='evidence',evidence_kind='named_paths',decision={'verdict':'needs_evidence','evidence_kind':'named_paths'})
if a=='collect_issue_named_paths':Path(%r).write_text('ran');v.update(collected=True,additional_evidence={})
if a=='collect_issue_repo_shape':Path(%r).write_text('ran')
if a=='verify_issue_evidence':v.update(route='agent',additional_evidence={})
if a=='issue_evidence_agent':Path(%r).write_text('ran')
if a=='validate_issue_evidence':v.update(route='valid',decision={'verdict':'ready'})
if a=='select_issue_evidence':v.update(route='publish',decision={'verdict':'ready'})
if a=='finalize_issue_triage':v['decision']={'verdict':'ready'}"""%(str(chosen),str(wrong),str(agent)))
    result=run_graph(tmp_path,body,"evidence"); statuses={k:v['status'] for k,v in result['effector_results'].items()}
    assert statuses['collect_issue_named_paths']=='succeeded' and statuses['collect_issue_repo_shape']=='skipped'
    assert chosen.exists() and agent.exists() and not wrong.exists()


def test_split_runs_bounded_child_effect_chain(tmp_path):
    child1=tmp_path/"child1"; child2=tmp_path/"child2"; wrong=tmp_path/"wrong"; closed=tmp_path/"closed"
    body=base_effector("""if a=='resolve_issue_candidate':v['route']='evaluate'
if a in {'collect_issue_linked_prs','collect_issue_covering_prs'}:v['collected']=True
if a=='resolve_issue_hard_facts':v['route']='agent'
if a=='validate_issue_triage':v.update(route='valid',decision={'verdict':'split','reason':'multi_epic_blob'})
if a=='select_issue_triage':v.update(route='publish',evidence_kind='none',decision={'verdict':'split','reason':'multi_epic_blob'})
if a=='verify_issue_evidence':v['route']='not_applicable'
if a=='select_issue_evidence':v['route']='not_applicable'
if a=='finalize_issue_triage':v['decision']={'verdict':'split','reason':'multi_epic_blob'}
if a=='plan_issue_split':v.update(route='children',child_1='present',child_2='present',child_3='absent',child_4='absent',child_5='absent',plan={})
if a=='create_issue_split_child_1':Path(%r).write_text('ran');v['child']={'number':10}
if a=='create_issue_split_child_2':Path(%r).write_text('ran');v['child']={'number':11}
if a in {'create_issue_split_child_3','create_issue_split_child_4','create_issue_split_child_5'}:Path(%r).write_text(a)
if a=='close_issue_tracker':Path(%r).write_text('ran')"""%(str(child1),str(child2),str(wrong),str(closed)))
    result=run_graph(tmp_path,body,"split",path_id="issue_split"); statuses={k:v['status'] for k,v in result['effector_results'].items()}
    assert statuses['create_issue_split_child_1']=='succeeded' and statuses['create_issue_split_child_2']=='succeeded'
    assert statuses['create_issue_split_child_3']=='skipped' and statuses['close_issue_tracker']=='succeeded'
    assert child1.exists() and child2.exists() and closed.exists() and not wrong.exists()


def test_hard_blocked_routes_only_blocked_effect(tmp_path):
    blocked=tmp_path/"blocked"; wrong=tmp_path/"wrong"
    body=base_effector("""if a=='resolve_issue_candidate':v['route']='evaluate'
if a in {'collect_issue_linked_prs','collect_issue_covering_prs'}:v['collected']=True
if a=='resolve_issue_hard_facts':v.update(route='terminal',decision={'verdict':'blocked','reason':'preflight_incident'})
if a=='validate_issue_triage':v['route']='not_applicable'
if a=='select_issue_triage':v.update(route='publish',evidence_kind='none',decision={'verdict':'blocked','reason':'preflight_incident'})
if a=='verify_issue_evidence':v['route']='not_applicable'
if a=='select_issue_evidence':v['route']='not_applicable'
if a=='finalize_issue_triage':v['decision']={'verdict':'blocked','reason':'preflight_incident'}
if a=='apply_issue_blocked':Path(%r).write_text('ran')
if a in {'apply_issue_ready','apply_issue_close','apply_issue_manual','issue_split_subflow'}:Path(%r).write_text(a)"""%(str(blocked),str(wrong)))
    result=run_graph(tmp_path,body,"blocked"); statuses={k:v['status'] for k,v in result['effector_results'].items()}
    assert statuses['apply_issue_blocked']=='succeeded' and statuses['apply_issue_ready']=='skipped'
    assert blocked.exists() and not wrong.exists()

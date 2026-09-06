from pathlib import Path
import tomllib

ROOT=Path(__file__).resolve().parents[1]

def test_acceptance_is_authored_before_builder_and_verified_before_push():
    package=tomllib.loads((ROOT/'fala/lokay.fala-package.toml').read_text())
    path=next(p for p in package['correlation_paths'] if p['id']=='issue_to_pr_delivery')
    ids=[e['id'] for e in path['effectors']]
    prepare=next(e for e in path['effectors'] if e['id']=='prepare_acceptance')
    builder=next(e for e in path['effectors'] if e['id']=='coding_execution')
    verify=next(e for e in path['effectors'] if e['id']=='verify_acceptance')
    gate=next(e for e in path['effectors'] if e['id']=='select_publish_gate')
    push=next(e for e in path['effectors'] if e['id']=='push')
    assert ids.index('prepare_acceptance') < ids.index('coding_execution') < ids.index('verify_acceptance') < ids.index('select_publish_gate') < ids.index('push')
    assert 'prepare_acceptance' in builder['conduction']
    assert 'select_publish_gate' in push['conduction']
    assert verify['when']=={'upstream':'finalize_local_tests','path':'route','equals':'publish'}
    assert push['when']=={'upstream':'select_publish_gate','path':'route','equals':'publish'}
    assert gate['when']=={'upstream':'assert_stamps_committed','path':'route','equals':'publish'}
    assert 'verify_acceptance' in gate['conduction'] and 'assert_stamps_committed' in gate['conduction']
    assert prepare['capability']=='acceptance_write' and builder['capability']!='acceptance_write'

def test_local_verification_terminal_is_unglued_from_publish():
    package=tomllib.loads((ROOT/'fala/lokay.fala-package.toml').read_text())
    path=next(p for p in package['correlation_paths'] if p['id']=='issue_to_pr_delivery')
    ids=[e['id'] for e in path['effectors']]
    assert ids.index('finalize_local_tests') < ids.index('local_verification_terminal') < ids.index('verify_acceptance')
    term=next(e for e in path['effectors'] if e['id']=='local_verification_terminal')
    assert term['conduction']==['finalize_local_tests']


def test_acceptance_repair_nodes_wired():
    package=tomllib.loads((ROOT/'fala/lokay.fala-package.toml').read_text())
    path=next(p for p in package['correlation_paths'] if p['id']=='issue_to_pr_delivery')
    by_id={e['id']: e for e in path['effectors']}
    assert by_id["acceptance_repair_execution"]["when"] == {
        "upstream": "verify_acceptance",
        "path": "route",
        "equals": "repair",
    }
    assert by_id["list_dirty_stamp_paths"]["when"] == {
        "upstream": "finalize_acceptance",
        "path": "route",
        "equals": "publish",
    }
    assert "finalize_acceptance" in by_id
    assert "verify_acceptance_recheck" in by_id
    assert "Merge is separate (Alfred)" not in path.get("description", "")
    assert "lokaj merges itself" in path.get("description", "")

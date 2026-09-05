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
    push=next(e for e in path['effectors'] if e['id']=='push')
    assert ids.index('prepare_acceptance') < ids.index('coding_execution') < ids.index('verify_acceptance') < ids.index('push')
    assert 'prepare_acceptance' in builder['conduction']
    assert 'verify_acceptance' in push['conduction']
    assert verify['when']=={'upstream':'finalize_local_tests','path':'route','equals':'publish'}
    assert prepare['capability']=='acceptance_write' and builder['capability']!='acceptance_write'

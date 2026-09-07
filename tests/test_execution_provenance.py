"""Execution identity must describe loaded code, not a later checkout."""
import importlib.util


def test_loaded_code_digest_survives_source_replacement(tmp_path):
    from lokay.execution_provenance import implementation_identity

    path = tmp_path / 'executor.py'
    path.write_text('def execute():\n    return 1\n')
    spec = importlib.util.spec_from_file_location('local_executor', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    before = implementation_identity(module.execute)
    path.write_text('def execute():\n    return 2\n')
    assert implementation_identity(module.execute) == before
    assert before['symbol'] == 'local_executor:execute'
    assert len(before['code_sha256']) == 64


def test_real_dispatch_reports_selected_handler_without_payloads():
    from lokay.fala_organ import _handle

    evidence = {}
    result = _handle('map_repo', {'worktree': '/nonexistent', 'body': 'private'}, {}, provenance=evidence)
    assert result is not None
    assert evidence['symbol'] == 'lokay.organ.map_repo:handle_map_repo'
    assert evidence['scope'] == 'loaded_callable_only'
    assert 'private' not in str(evidence)


def test_identity_changes_with_implementation():
    from lokay.execution_provenance import implementation_identity

    def first():
        return 1

    def second():
        return 2

    assert implementation_identity(first)['code_sha256'] != implementation_identity(second)['code_sha256']

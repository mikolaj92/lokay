"""Review-directed PR repairs must never be silently restored away."""

from lokay.organ.relocalize_boundary import handle_relocalize


def test_pr_repair_preserves_protected_paths_for_scope_gate():
    result = handle_relocalize(
        "classify_relocalization_residue", {"repair_mode": True},
        {"read_relocalization_changed_paths": {"changed": ["fala/lokay.fala-package.toml"]},
         "read_relocalization_issue_paths": {"paths": []}}, {},
    )
    assert result is not None
    assert result["route"] == "continue"
    assert result["restore_paths"] == []

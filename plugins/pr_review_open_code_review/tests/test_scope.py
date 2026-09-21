"""Vendor selection is evidence, never permission to omit required code."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lokay_review_open_code_review import cli


def test_scope_request_invokes_only_preview_and_preserves_exact_inventory(monkeypatch):
    # Load fixtures by path: host and plugin both have a test_cli module.
    import runpy
    fixtures = Path(__file__).parent
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as root:
        files = runpy.run_path(str(fixtures / "test_cli.py"))["_request"](Path(root))
        contract_request = runpy.run_path(str(fixtures / "test_contract.py"))["_request"]
        request = {**contract_request(), "repo_path": files["repo_path"], "engine": files["engine"]}
        calls = []
        monkeypatch.setattr(cli, "verify_checkout", lambda request: {"identity": "unchanged"})
        preview = {"files": [{"path": "src/demo.py", "status": "modified", "will_review": True}],
                   "total_files": 1, "reviewable_count": 1, "excluded_count": 0}
        def invoke(request, *, preview):
            calls.append(preview)
            return copy.deepcopy(output)
        output = preview
        monkeypatch.setattr(cli, "invoke_ocr", invoke)
        result = cli.scope_request(request)
        assert calls == [True]
        assert result["ok"] is True
        assert result["schema"] == "lokay.review-scope/1"
        assert result["head_sha"] == request["head_sha"]
        assert result["diff_sha256"] == request["diff_sha256"]
        assert result["preview"] == preview


@pytest.mark.parametrize("git_status", ["added", "modified", "renamed", "deleted"])
def test_binary_is_content_kind_not_git_status_and_remains_unreviewed(git_status):
    from lokay_review_open_code_review.scope import validate_scope
    request = {"diff_paths": [{"path": "cache.dat", "old_path": "", "status": git_status}]}
    preview = {"files": [{"path": "cache.dat", "status": "binary", "will_review": False,
                           "exclude_reason": "binary"}],
               "total_files": 1, "reviewable_count": 0, "excluded_count": 1}
    with pytest.raises(ValueError, match="^preview contains unreviewed binary paths$"):
        validate_scope(request, preview)


def test_scope_refuses_vendor_excluded_python_test():
    from lokay_review_open_code_review.scope import validate_scope
    request = {"diff_paths": [{"path": "tests/test_x.py", "old_path": "", "status": "added"}]}
    preview = {"files": [{"path": "tests/test_x.py", "status": "added", "will_review": False,
                          "exclude_reason": "default_path"}],
               "total_files": 1, "reviewable_count": 0, "excluded_count": 1}
    with pytest.raises(ValueError, match="required diff path"):
        validate_scope(request, preview)

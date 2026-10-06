import json
import subprocess
from types import SimpleNamespace

import pytest

from lokay.proc import semantic_relocalization


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


@pytest.mark.parametrize("drift", ["none", "tracked", "inventory"])
@pytest.mark.parametrize("choice,status,expected_reason", [
    ("uncertain", "abstained", "decision_uncertain"),
    ("unrelated", "completed", "off_goal_not_approved"),
    ("required", "completed", ""),
])
def test_extraction_decision_includes_original_source_changes(
    tmp_path, monkeypatch, choice, status, expected_reason, drift
):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    source = tmp_path / "src"
    source.mkdir()
    original = "def calculate_total(values):\n    return sum(values)\n"
    (source / "large.py").write_text(original)
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "baseline")
    (source / "large.py").write_text("from .extracted import calculate_total\n")
    (source / "extracted.py").write_text(original)
    (source / "support.py").write_text("SUPPORT_CONSTANT = 7\n")
    captured = {}

    def decide(config, **kwargs):
        captured.update(kwargs["evidence"])
        if drift == "tracked":
            (source / "large.py").write_text("def changed_during_decision():\n    return False\n")
        elif drift == "inventory":
            (source / "support.py").unlink()
        return {"status": status, "choice": choice,
                "reason": "decision_uncertain" if status == "abstained" else "decision_completed"}

    monkeypatch.setattr(semantic_relocalization, "decide", decide)
    cfg = SimpleNamespace(
        live=True,
        decision_routes={"relocalization": "test"},
        decision_endpoints={"test": {"max_input_chars": 120000}},
    )
    result = semantic_relocalization.run(
        {"worktree": str(tmp_path), "base": "HEAD", "localized": ["src/large.py", "src/support.py"],
         "issue_raw": {"number": 1, "body": "Split large.py without changing behavior."}},
        {"off_goal_paths": ["src/extracted.py"]}, config=cfg,
    )
    assert "Untracked file src/extracted.py:" in captured["diff"]
    assert "-def calculate_total(values):" in captured["localized_tracked_diff"]
    assert "+from .extracted import calculate_total" in captured["localized_tracked_diff"]
    assert captured["omitted_localized_untracked_paths"] == ["src/support.py"]
    assert "SUPPORT_CONSTANT" not in captured["localized_tracked_diff"]
    if choice == "required" and drift != "none":
        assert result["route"] == "terminal"
        assert result["reason"] == "decision_scope_drift"
    elif choice == "required":
        assert result["route"] == "validate"
        assert json.loads(result["text"])["paths"] == ["src/extracted.py"]
    else:
        assert result["route"] == "terminal"
        assert result["reason"] == expected_reason


@pytest.mark.parametrize("path", ["", " ", ".", "./", "./.", "../source.py", "/source.py"])
def test_invalid_context_paths_never_read_repository(tmp_path, monkeypatch, path):
    def decide(*args, **kwargs):
        pytest.fail("invalid supporting scope must not reach the model")

    monkeypatch.setattr(semantic_relocalization, "decide", decide)
    result = semantic_relocalization.run(
        {"worktree": str(tmp_path), "localized": [path]},
        {"off_goal_paths": ["src/new.py"]}, config=SimpleNamespace(live=True),
    )
    assert result["reason"] == "decision_scope_invalid"

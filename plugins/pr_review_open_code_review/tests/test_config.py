from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(PACKAGE_SRC))

from lokay_review_open_code_review.tools import validate_tools  # noqa: E402


def test_checked_in_tool_registry_has_only_bounded_context_and_comment_tools():
    payload = validate_tools(Path(__file__).parents[1] / "src" / "lokay_review_open_code_review" / "tools.json")
    assert set(payload) == {"task_done", "code_comment", "file_read", "file_read_diff", "file_find", "code_search"}
    assert payload["task_done"]["plan_task"] is False
    assert payload["task_done"]["main_task"] is True
    assert payload["code_comment"]["main_task"] is True
    assert payload["code_comment"]["plan_task"] is False
    assert payload["file_read_diff"]["plan_task"] is True
    assert payload["code_search"]["main_task"] is True


def test_tool_registry_rejects_extra_or_write_capability(tmp_path: Path):
    path = tmp_path / "tools.json"
    path.write_text('[{"name":"shell","plan_task":true,"main_task":true,"definition":{}}]')
    try:
        validate_tools(path)
    except ValueError as exc:
        assert "tool" in str(exc)
    else:
        raise AssertionError("unapproved tool accepted")

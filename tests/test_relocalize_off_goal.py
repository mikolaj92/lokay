"""Contracts for minimal off-goal relocalization atoms."""


def test_protected_residue_not_named_by_issue_is_restored():
    from lokay.proc.classify_relocalization_residue import classify

    out = classify(
        {"changed": ["src/a.py", "src/lokay/proc/factory_begin.py"]},
        {"paths": ["src/a.py"]},
    )
    assert out["route"] == "restore" and out["restore_paths"] == [
        "src/lokay/proc/factory_begin.py"
    ]


def test_issue_explicit_path_is_not_restored():
    from lokay.proc.classify_relocalization_residue import classify

    path = "src/lokay/organ/agent.py"
    assert classify({"changed": [path]}, {"paths": [path]})["restore_paths"] == []


def test_off_goal_is_purely_classified_after_restore():
    from lokay.proc.classify_relocalization_off_goal import classify

    out = classify(
        {"localized": ["src/a.py"]},
        {"changed": ["src/a.py", "src/b.py"]},
        {"restored_paths": []},
    )
    assert out["route"] == "agent" and out["off_goal_paths"] == ["src/b.py"]


def test_agent_approval_is_limited_to_current_off_goal_set():
    from lokay.proc.validate_relocalization_approval import validate

    out = validate(
        {"route": "valid", "paths": ["src/b.py", "src/foreign.py"]},
        {"off_goal_paths": ["src/b.py"]},
    )
    assert out["approved"] == ["src/b.py"] and out["route"] == "write"


def test_empty_agent_approval_does_not_expand_scope():
    from lokay.proc.validate_relocalization_approval import validate

    assert (
        validate(
            {"route": "valid", "paths": ["src/foreign.py"]},
            {"off_goal_paths": ["src/b.py"]},
        )["route"]
        == "terminal"
    )

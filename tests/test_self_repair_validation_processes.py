"""Contracts for minimal self-repair validation processes."""


def test_zero_diff_is_rejected():
    from lokay.proc.classify_self_repair_candidate_diff import classify

    assert "zero diff" in classify({"changed": "", "committed": "empty"})["error"]


def test_committed_plan_evidence_is_rejected():
    from lokay.proc.classify_self_repair_candidate_diff import classify

    assert (
        "committed plan evidence"
        in classify({"changed": "", "committed": "plan_only"})["error"]
    )


def test_untracked_overflow_is_fail_closed(monkeypatch):
    from lokay.proc.list_self_repair_untracked_paths import list_paths

    class Run:
        def run(self, *a, **k):
            return type(
                "R",
                (),
                {
                    "returncode": 0,
                    "stdout": "\0".join(str(i) for i in range(31)) + "\0",
                },
            )()

    monkeypatch.setattr("lokay.proc.list_self_repair_untracked_paths.runner", Run)
    out = list_paths({"worktree": "/tmp/w"}, slot_count=30)
    assert out["ok"] is False and "exceed authored slots" in out["error"]


def test_invalid_untracked_check_reduces_fail_closed():
    from lokay.proc.reduce_self_repair_untracked_checks import reduce_state

    out = reduce_state([{"route": "invalid", "error": "bad"}], {"worktree": "/tmp/w"})
    assert out["ok"] is False


def test_no_base_skips_committed_identity():
    from lokay.proc.validate_self_repair_identity_request import validate as verify

    out = verify(
        {"base_sha": "", "changed": ""}, expected_subject="", expected_commit=""
    )
    assert out["route"] == "tests"

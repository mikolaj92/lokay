from lokay.proc.select_issue_executor import select


def _do() -> dict:
    return {"route": "do", "repo": "o/r", "issue": 2, "leftover": 1, "leftover_issues": []}


def test_disabled_executor_does_not_launch() -> None:
    out = select(_do(), enabled=False)
    assert out["route"] == "skip"
    assert out["reason"] == "executor_disabled"
    assert out["repo"] == "o/r" and out["issue"] == 2


def test_enabled_executor_launches_after_sito_do() -> None:
    out = select(_do(), enabled=True)
    assert out["route"] == "do"
    assert out["issue"] == 2


def test_enabled_executor_does_not_replace_sito_skip() -> None:
    out = select({"route": "skip", "reason": "sito_nie_robic"}, enabled=True)
    assert out["route"] == "skip"
    assert out["reason"] == "sito_nie_robic"

"""P0 intake law: labeled start, one list, no unlabeled catalog implement fuel."""

from pathlib import Path

import tomllib

from lokay.proc.catalog_work import remaining_ready_count, work_by_repo
from lokay.proc.select_next_issue import select
from lokay.sieve_decision import listed_of


ROOT = Path(__file__).resolve().parents[1]


def test_unlabeled_open_issues_are_none_ready():
    out = select(
        {
            "issues": [
                {"repo": "o/r", "issue": 1, "labels": []},
                {"repo": "o/r", "issue": 2, "labels": ["bug"]},
            ],
            "count": 2,
            "overflow": False,
        }
    )
    assert out["route"] == "none"
    assert out["reason"] == "none_ready"


def test_ai_ready_is_start_fuel():
    out = select(
        {
            "issues": [{"repo": "o/r", "issue": 9, "number": 9, "labels": ["ai:ready"]}],
            "count": 1,
            "overflow": False,
        }
    )
    assert out["route"] == "ready"
    assert out["issue"] == 9


def test_ready_for_agent_is_start_fuel():
    out = select(
        {
            "issues": [
                {"repo": "o/r", "issue": 1, "number": 1, "labels": []},
                {"repo": "o/r", "issue": 2, "number": 2, "labels": ["ready-for-agent"]},
            ],
            "count": 2,
            "overflow": False,
        }
    )
    assert out["route"] == "ready"
    assert out["issue"] == 2


def test_inbox_only_unlabeled_is_zero_implement_fuel():
    work = work_by_repo(
        {
            "ready_by_repo": {},
            "inbox_issues_by_repo": {
                "mikolaj92/Temida": [{"number": 4968, "labels": []}]
            },
        }
    )
    assert remaining_ready_count(work) == 0


def test_leftover_labeled_remainder_walks_after_skip():
    listed = {
        "issues": [
            {"repo": "o/r", "issue": 1, "labels": ["ai:ready"]},
            {"repo": "o/r", "issue": 2, "labels": ["ai:ready"]},
            {"repo": "o/r", "issue": 3, "labels": []},
        ],
        "count": 3,
        "overflow": False,
    }
    first = select(listed)
    assert first["issue"] == 1
    from lokay.proc.select_issue_sieve import select as select_sieve

    skipped = select_sieve(
        first,
        {"route": "completed", "triage": {"decision": {"verdict": "park"}}},
        listed,
    )
    assert skipped["route"] == "skip"
    assert skipped["reason"] == "park"
    assert skipped["leftover_issues"][0]["issue"] == 2
    second = select(listed, last=skipped)
    assert second["route"] == "ready"
    assert second["issue"] == 2
    third = select(listed, last={**second, "leftover_issues": second.get("leftover_issues") or []})
    assert third["route"] == "none"
    assert third["reason"] == "none_ready"


def test_leftover_dual_ready_is_still_implement_fuel():
    work = work_by_repo(
        {
            "ready_by_repo": {},
            "inbox_issues_by_repo": {},
            "leftover_issues": [
                {
                    "repo": "mikolaj92/Temida",
                    "issue": 5714,
                    "number": 5714,
                    "labels": ["ai:ready", "work:ready"],
                }
            ],
        }
    )
    assert remaining_ready_count(work) == 1
    assert work["mikolaj92/Temida"][0]["number"] == 5714


def test_package_has_one_intake_list_open_issues():
    package = tomllib.loads(
        (ROOT / "fala/lokay.fala-package.toml").read_text(encoding="utf-8")
    )
    authored = []
    for path in package["correlation_paths"]:
        if path["id"] in {"issue_triage_department", "executor_department"}:
            for node in path.get("effectors") or []:
                if node.get("id") == "list_open_issues" or node.get("config", {}).get(
                    "atom"
                ) == "list_open_issues":
                    authored.append(path["id"])
    assert authored == ["issue_triage_department"]


def test_executor_listed_of_reuses_triage_snapshot():
    listed = {
        "ok": True,
        "issues": [{"repo": "o/r", "issue": 2, "labels": ["ai:ready"]}],
        "count": 1,
    }
    out = listed_of({"result": {"listed": listed, "leftover": 0}})
    assert out["issues"][0]["issue"] == 2


def test_docs_do_not_teach_oil_only_as_empty_scope_default():
    forbidden = (
        "default `mikolaj92/lokay`",
        "factory_scope`, default `mikolaj92/lokay`",
    )
    for rel in ("docs/WORKING.md", "docs/AUTONOMY.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        for phrase in forbidden:
            assert phrase not in text, f"{rel} still says {phrase!r}"
    scope = (ROOT / "src/lokay/factory_scope.py").read_text(encoding="utf-8")
    assert "Empty means full configured catalog" in scope
    assert "oil-only" in scope

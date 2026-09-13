"""#1041: host-ops must not enter coding as a monolith."""

from __future__ import annotations

from lokay.host_ops import (
    HOST_OPS_UNPARK_CRITERION,
    host_ops_unpark_ready,
    issue_is_host_ops_monolith,
    issue_requests_host_ops,
    line_is_host_ops_only,
)
from lokay.issue_triage_boundary import resolve_hard_facts
from lokay.models import Issue
from lokay.proc.select_issue_sieve import classify_sieve
from lokay.split import plan_split


def _issue(**kwargs) -> Issue:
    base = dict(
        repo="a/b",
        number=41,
        title="Feature",
        body="Implement something useful with clear acceptance.",
        labels=[],
        assignees=[],
        url="https://example.com/41",
        state="OPEN",
    )
    base.update(kwargs)
    return Issue(**base)


def _data(**kwargs) -> dict:
    return _issue(**kwargs).to_dict()


def test_detector_true_for_live_host_ops():
    assert issue_requests_host_ops(
        _issue(title="Hermes restore on host 0", body="Need live evidence.")
    )
    assert issue_requests_host_ops(
        _issue(title="LaunchAgent stuck", body="Restart on mini-m4-0")
    )
    assert issue_requests_host_ops(
        _issue(title="Ops", body="Potrzebny żywy host + fleet host evidence")
    )
    assert issue_requests_host_ops(
        _issue(title="Grok Bot computer update", body="SSH host check")
    )


def test_detector_false_for_ordinary_code_and_host_ff_docs():
    assert not issue_requests_host_ops(
        _issue(
            title="Tighten host_ff docs",
            body="Update docs about host_ff atom in src/lokay/proc/host_ff.py",
        )
    )
    assert not issue_requests_host_ops(
        _issue(title="Implement sieve", body="## Done means\n- [ ] add tests")
    )


def test_monolith_vs_pure_host_ops():
    mono = _issue(
        title="Hermes restore + fix coding path",
        body=(
            "## Goal\nRestore Hermes on host 0 and fix the detector.\n\n"
            "## Done means\n"
            "- [ ] Hermes restore on live host\n"
            "- [ ] Implement src/lokay/host_ops.py + tests\n"
        ),
    )
    assert issue_requests_host_ops(mono)
    assert issue_is_host_ops_monolith(mono)

    pure = _issue(
        title="Hermes restore on host 0",
        body="Restore Hermes. LaunchAgent must be healthy. Fleet host evidence only.",
    )
    assert issue_requests_host_ops(pure)
    assert not issue_is_host_ops_monolith(pure)


def test_hard_facts_monolith_parks_host_ops_issue_split():
    data = _data(
        title="Hermes restore + implement detector",
        body=(
            "Need Hermes restore on mini-m4 and code in src/lokay/intake.py.\n"
            "- [ ] implement tests\n"
            "- [ ] Hermes restore\n"
        ),
    )
    out = resolve_hard_facts(
        data, {"route": "evaluate"}, {"merged_prs": []}, {"covering_prs": []}
    )
    assert out["route"] == "terminal"
    assert out["decision"]["verdict"] == "park"
    assert "host_ops_issue_split" in out["decision"]["reason"]
    assert "issue_split" in out["decision"]["reason"]


def test_sieve_routes_host_ops_issue_split_to_split():
    out = classify_sieve(
        {
            "triage": {
                "decision": {
                    "verdict": "park",
                    "reason": "host_ops_issue_split",
                }
            }
        },
        {},
    )
    assert out["route"] == "split"


def test_hard_facts_pure_host_ops_parks_not_do():
    data = _data(
        title="LaunchAgent on mini-m4",
        body="Restart LaunchAgent. Need host evidence only — no code change.",
    )
    out = resolve_hard_facts(
        data, {"route": "evaluate"}, {"merged_prs": []}, {"covering_prs": []}
    )
    assert out["route"] == "terminal"
    assert out["decision"]["verdict"] == "skip"
    assert out["decision"]["reason"] == "host_ops"
    assert HOST_OPS_UNPARK_CRITERION in (out["decision"].get("summary") or "")
    sieve = classify_sieve(
        {"triage": {"decision": out["decision"]}}, {"route": "issue"}
    )
    assert sieve["route"] == "skip"
    assert sieve["route"] != "do"


def test_coding_ready_issue_unchanged():
    data = _data(
        title="Implement useful feature",
        body="A sufficiently detailed body with clear acceptance criteria.",
    )
    out = resolve_hard_facts(
        data, {"route": "evaluate"}, {"merged_prs": []}, {"covering_prs": []}
    )
    assert out["route"] == "agent"


def test_plan_split_host_ops_prefers_code_plus_ops_child():
    body = (
        "## Goal\nmixed\n\n"
        "- [ ] Implement src/lokay/host_ops.py detector\n"
        "- [ ] Hermes restore on host 0\n"
        "- [ ] Add focused pytest for sieve\n"
    )
    plan = plan_split(
        _issue(title="Host ops monolith", body=body),
        reason="host_ops_issue_split",
    )
    assert plan is not None
    titles = [c.title.lower() for c in plan.children]
    assert any("host/ops" in t or "not coding" in t for t in titles)
    assert any("host_ops" == c.source for c in plan.children)
    code_titles = [c.title for c in plan.children if c.source != "host_ops"]
    assert code_titles
    assert all("hermes restore" not in t.lower() for t in code_titles)
    assert "NOT a coding slot" in plan.children[-1].body


def test_plan_split_host_ops_fail_closed_without_code_slice():
    plan = plan_split(
        _issue(
            title="Hermes restore only",
            body="- [ ] Hermes restore on host 0\n- [ ] LaunchAgent healthy\n",
        ),
        reason="host_ops_issue_split",
    )
    assert plan is None


def test_host_ops_unpark_ready_pure():
    issue = _issue(title="Hermes restore", body="<!-- lokay-host-ops:x -->")
    assert not host_ops_unpark_ready(issue, evidence={})
    assert host_ops_unpark_ready(
        issue, evidence={"hermes_restored": True}
    )
    assert host_ops_unpark_ready(
        issue, evidence={"host_evidence_receipt": {"ok": True}}
    )
    assert not host_ops_unpark_ready(
        _issue(title="Normal code", body="implement tests"),
        evidence={"hermes_restored": True},
    )


def test_machine_name_mention_is_not_itself_a_host_ops_request():
    # Issue #31 documents that a fleet machine receives an incorrect identity.
    # A machine mention in the evidence does not request live host work.
    issue = _issue(
        title=(
            "[docs-audit] fleet Hermes USER.md/MEMORY.md traktują Mirosława "
            "jako bieżącego użytkownika"
        ),
        body="Agent na mini-m4-0 i na stacji dostaje cudzą sesję jako default.",
    )
    assert not issue_requests_host_ops(issue)
    assert not issue_is_host_ops_monolith(issue)
    assert not line_is_host_ops_only("- [ ] Fix Hermes identity for mini-m4-0")


def test_machine_identity_report_reaches_semantic_triage():
    data = _data(
        title=(
            "[docs-audit] fleet Hermes USER.md/MEMORY.md traktują Mirosława "
            "jako bieżącego użytkownika"
        ),
        body="Agent na mini-m4-0 i na stacji dostaje cudzą sesję jako default.",
    )
    out = resolve_hard_facts(
        data, {"route": "evaluate"}, {"merged_prs": []}, {"covering_prs": []}
    )
    assert out["route"] == "agent"


def test_generated_host_ops_child_is_not_split_again():
    issue = _issue(
        number=42,
        title="Host/ops evidence (not coding)",
        body=(
            "## Goal\nDeterministic host/fleet ops evidence for the parent. "
            "This is NOT a coding slot — do not route to issue_to_pr / ai/fix.\n\n"
            "## Done means\n"
            "- [ ] auto-unpark when host evidence receipt exists / Hermes restored\n"
            "- [ ] Keep parent skipped (no limbo label) until evidence exists "
            "(factory skip; zero needs_human)\n\n"
            "## Parent\nSplit from mikolaj92/dotfiles#40: Host/ops evidence "
            "(not coding)\n\n"
            "<!-- lokay-host-ops:auto-unpark when host evidence receipt "
            "exists / Hermes restored -->\n"
            "<!-- lokay-split:mikolaj92/dotfiles#40:child:2 -->\n"
        ),
    )
    assert issue_requests_host_ops(issue)
    assert not issue_is_host_ops_monolith(issue)
    out = resolve_hard_facts(
        issue.to_dict(), {"route": "evaluate"}, {"merged_prs": []}, {"covering_prs": []}
    )
    assert out["route"] == "terminal"
    assert out["decision"]["verdict"] == "skip"
    assert out["decision"]["reason"] == "host_ops"

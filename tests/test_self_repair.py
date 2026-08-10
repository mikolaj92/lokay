from pathlib import Path
from types import SimpleNamespace

from lokay import self_repair


def cfg(tmp_path, **kw):
    base = dict(state_path=tmp_path / "state.jsonl", max_repairs_per_tick=2, max_self_repair_attempts=2, whole_run_deadline_seconds=3600,
                executor_enabled=True, require_checks=False, merge_enabled=True, branch_prefix="ai/fix",
                active_repos=lambda: [])
    base.update(kw); return SimpleNamespace(**base)


def unhealthy(url="https://github.com/mikolaj92/lokay/issues/44"):
    return {"ok": False, "fingerprint": "abc", "incident_url": url,
            "findings": [{"name": "fala_smoke", "ok": False}]}


def setup_lane(monkeypatch, tmp_path, **cfg_kw):
    monkeypatch.setattr(self_repair, "load_config", lambda p: cfg(tmp_path, **cfg_kw))
    monkeypatch.setattr(self_repair, "revoke_health_lease", lambda: None)
    monkeypatch.setattr(self_repair, "RepairBroker", lambda **k: SimpleNamespace(env=lambda: {}, close=lambda: None, bind_pr=lambda **k: None))
    monkeypatch.setattr(self_repair, "_gh_json", lambda a: {"headRefName": "ai/fix/44-health", "headRefOid": "head", "headRepository": {"nameWithOwner": "mikolaj92/lokay"}, "baseRefName": "main", "body": "<!-- lokay-preflight:abc -->", "mergeCommit": {"oid": "merge"}})


def test_missing_deduplicated_incident_never_runs_executor(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path)
    monkeypatch.setattr(self_repair, "compose_issue_to_pr", lambda **k: (_ for _ in ()).throw(AssertionError()))
    result = self_repair.run_self_repair("x", unhealthy(url=None))
    assert not result["ok"] and result["reason"] == "deduplicated_incident_unavailable"


def test_bootstrap_dependency_failure_avoids_recursion(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path)
    value = unhealthy(); value["findings"] = [{"name": "executor_availability", "ok": False}]
    monkeypatch.setattr(self_repair, "_repair_pr", lambda n, **kw: (_ for _ in ()).throw(AssertionError()))
    result = self_repair.run_self_repair("x", value)
    assert result["reason"] == "bootstrap_dependency_unavailable" and result["attempts"] == []


def test_services_only_incident_without_product_intake(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path, max_self_repair_attempts=1)
    calls = []
    monkeypatch.setattr(self_repair, "_repair_pr", lambda n, **kw: calls.append(("discover", n)))
    monkeypatch.setattr(self_repair, "compose_issue_to_pr", lambda **k: calls.append(("issue", k["repo"], k["issue_number"])) or {"ok": False})
    result = self_repair.run_self_repair("x", unhealthy())
    assert calls == [("discover", 44), ("issue", "mikolaj92/lokay", 44)]
    assert len(result["attempts"]) == 1


def test_zero_diff_does_not_claim_repair(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path, max_self_repair_attempts=1)
    monkeypatch.setattr(self_repair, "_repair_pr", lambda n, **kw: None)
    monkeypatch.setattr(self_repair, "compose_issue_to_pr", lambda **k: {"ok": True, "branch": ""})
    result = self_repair.run_self_repair("x", unhealthy())
    assert not result["ok"]
    assert result["attempts"][0]["reason"] == "zero_diff_or_no_pr"


def test_failed_checks_use_bounded_existing_pr_repair(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path, max_self_repair_attempts=2)
    monkeypatch.setattr(self_repair, "_repair_pr", lambda n, **kw: {"number": 7, "headRefName": "ai/fix/44-health"})
    monkeypatch.setattr(self_repair, "_checks", lambda *a, **k: "failed")
    calls = []
    monkeypatch.setattr(self_repair, "compose_pr_repair", lambda **k: calls.append(k) or {"ok": True})
    result = self_repair.run_self_repair("x", unhealthy())
    assert len(calls) == 2 and len(result["attempts"]) == 2 and not result["ok"]


def test_normal_policy_merge_activation_and_preflight_release(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path, max_self_repair_attempts=1)
    monkeypatch.setattr(self_repair, "_repair_pr", lambda n, **kw: {"number": 7, "headRefName": "ai/fix/44-health"})
    monkeypatch.setattr(self_repair, "_checks", lambda *a, **k: "passed")
    monkeypatch.setattr(self_repair, "compose_pr_triage", lambda **k: {"ok": True, "merged": True})
    monkeypatch.setattr(self_repair, "_activate", lambda c, **kw: {"ok": True, "activated": True, "path": str(tmp_path)})
    monkeypatch.setattr(self_repair, "_gh_json", lambda a: {"mergeCommit": {"oid": "abc"}, "headRefName": "ai/fix/44-health", "headRefOid": "head", "headRepository": {"nameWithOwner": "mikolaj92/lokay"}, "baseRefName": "main", "body": "<!-- lokay-preflight:abc -->"})
    monkeypatch.setattr(self_repair.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout='{"ok": true, "health": "healthy"}\n', stderr=""))
    result = self_repair.run_self_repair("x", unhealthy())
    assert result["ok"] and result["validated"] and not result["gate_released"] and result["repaired_pr"] == 7


def test_merge_policy_disabled_fails_closed(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path, max_self_repair_attempts=1, merge_enabled=False)
    monkeypatch.setattr(self_repair, "_repair_pr", lambda n, **kw: {"number": 7, "headRefName": "ai/fix/44-health"})
    monkeypatch.setattr(self_repair, "_checks", lambda *a, **k: "passed")
    monkeypatch.setattr(self_repair, "compose_pr_triage", lambda **k: (_ for _ in ()).throw(AssertionError()))
    result = self_repair.run_self_repair("x", unhealthy())
    assert result["attempts"][0]["reason"] == "merge_policy_disabled"


def test_multiple_repair_prs_fail_closed(monkeypatch):
    monkeypatch.setattr(self_repair, "_gh_json", lambda a: [
        {"number": 1, "headRefName": "ai/fix/44-a", "baseRefName": "main", "headRepository": {"nameWithOwner": "mikolaj92/lokay"}, "body": "<!-- lokay-preflight: -->"},
        {"number": 2, "headRefName": "ai/fix/44-b", "baseRefName": "main", "headRepository": {"nameWithOwner": "mikolaj92/lokay"}, "body": "<!-- lokay-preflight: -->"},
    ])
    import pytest
    with pytest.raises(RuntimeError, match="ambiguous"):
        self_repair._repair_pr(44)


def test_wrong_issue_branch_is_not_selected(monkeypatch):
    monkeypatch.setattr(self_repair, "_gh_json", lambda a: [
        {"number": 1, "headRefName": "ai/fix/144-not-this-issue"},
    ])
    assert self_repair._repair_pr(44) is None

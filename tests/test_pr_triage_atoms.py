"""Atomic pr_triage engine selection."""

from lokay.compose._atoms import use_fala


def test_use_fala_default_off(monkeypatch):
    monkeypatch.delenv("LOKAY_USE_FALA", raising=False)
    assert use_fala() is False


def test_use_fala_on(monkeypatch):
    monkeypatch.setenv("LOKAY_USE_FALA", "1")
    assert use_fala() is True


from pathlib import Path

from lokay.compose import pr_triage


def _live_config(tmp_path: Path) -> str:
    path = tmp_path / "config.yaml"
    path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: true
  command: omp
  args: ["-p", "{{prompt}}"]
merge:
  enabled: true
  require_checks: false
  require_llm_review: true
state:
  path: {tmp_path / 'state.jsonl'}
""",
        encoding="utf-8",
    )
    return str(path)


def test_request_changes_returns_repairable_decision(tmp_path, monkeypatch):
    cfg = _live_config(tmp_path)
    calls = []

    def fake_atom(fn, argv):
        calls.append(fn.__module__)
        if fn is pr_triage.p_checks.main:
            return {"ok": True, "status": "none", "text": "no checks"}
        if fn is pr_triage.p_review.main:
            return {
                "ok": True,
                "merge_ok": False,
                "decision": {
                    "verdict": "request_changes",
                    "secrets": False,
                    "blocking": ["add regression test"],
                },
            }
        raise AssertionError("merge must not run")

    monkeypatch.setattr(pr_triage, "run_atom", fake_atom)
    result = pr_triage._atomic_pr_triage(
        config_path=cfg, repo="a/b", pr_number=7, branch="ai/fix/7-x", live=True
    )
    assert result["reason"] == "llm_review_requested_changes"
    assert result["repairable"] is True
    assert result["review"]["blocking"] == ["add regression test"]
    assert not any(name.endswith("pr_merge") for name in calls)


def test_needs_human_is_not_repairable(tmp_path, monkeypatch):
    cfg = _live_config(tmp_path)

    def fake_atom(fn, argv):
        if fn is pr_triage.p_checks.main:
            return {"ok": True, "status": "none", "text": "no checks"}
        if fn is pr_triage.p_review.main:
            return {
                "ok": True,
                "merge_ok": False,
                "decision": {"verdict": "needs_human", "secrets": False},
            }
        raise AssertionError("merge must not run")

    monkeypatch.setattr(pr_triage, "run_atom", fake_atom)
    result = pr_triage._atomic_pr_triage(
        config_path=cfg, repo="a/b", pr_number=8, branch="ai/fix/8-x", live=True
    )
    assert result["reason"] == "llm_review_not_approved"
    assert result["repairable"] is False


def test_fala_opt_in_uses_atoms_when_structured_review_required(tmp_path, monkeypatch):
    cfg = _live_config(tmp_path)
    monkeypatch.setenv("LOKAY_USE_FALA", "1")
    called = []

    def fake_atomic(**kwargs):
        called.append(kwargs)
        return {"ok": True, "skipped": True, "repairable": True}

    monkeypatch.setattr(pr_triage, "_atomic_pr_triage", fake_atomic)
    result = pr_triage.compose_pr_triage(
        config_path=cfg, repo="a/b", pr_number=9, branch="ai/fix/9-x", live=True
    )
    assert called
    assert result["kind"] in {"pr_repair", "pr_triage"}
    assert result["repairable"] is True

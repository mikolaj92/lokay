from pathlib import Path

from lokay import fala_organ


def _config(tmp_path: Path, *, required: bool, executor: bool) -> str:
    path = tmp_path / "config.yaml"
    path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: {str(executor).lower()}
merge:
  enabled: true
  require_checks: false
  require_llm_review: {str(required).lower()}
state:
  path: {tmp_path / 'state.jsonl'}
""",
        encoding="utf-8",
    )
    return str(path)


def test_review_not_required_bypasses_disabled_executor_and_allows_merge(tmp_path, monkeypatch):
    cfg = _config(tmp_path, required=False, executor=False)
    review = fala_organ._handle(
        "pr_review",
        {"config_path": cfg, "repo": "a/b", "pr": 7, "live": True},
        {"pr_checks": {"ok": True, "status": "none"}},
    )
    assert review == {
        "ok": True,
        "skipped": True,
        "reason": "llm_review_not_required",
        "merge_ok": True,
        "repo": "a/b",
        "pr": 7,
    }

    called = []
    def fake_run(main, argv):
        called.append((main, argv))
        return {"ok": True, "merged": True}
    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    merged = fala_organ._handle(
        "pr_merge",
        {"config_path": cfg, "repo": "a/b", "pr": 7, "live": True},
        {"pr_checks": {"ok": True, "status": "none", "merge_ok": True}, "pr_review": review},
    )
    assert merged["merged"] is True
    assert called, "pr_merge atom must execute"


def test_required_review_with_disabled_executor_stays_blocked(tmp_path, monkeypatch):
    cfg = _config(tmp_path, required=True, executor=False)

    def fake_run(main, argv):
        return {"ok": True, "skipped": True, "reason": "executor_disabled", "merge_ok": False}
    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    review = fala_organ._handle(
        "pr_review",
        {"config_path": cfg, "repo": "a/b", "pr": 8, "live": True},
        {"pr_checks": {"ok": True, "status": "none"}},
    )
    merged = fala_organ._handle(
        "pr_merge",
        {"config_path": cfg, "repo": "a/b", "pr": 8, "live": True},
        {"pr_checks": {"ok": True, "status": "none", "merge_ok": True}, "pr_review": review},
    )
    assert merged["skipped"] is True
    assert merged["reason"] == "executor_disabled"


def test_bundled_fala_manifest_is_ascii_safe():
    """Native TOML parsing must never land on a UTF-8 continuation byte."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    authored = (root / "fala" / "lokay.fala-package.toml").read_bytes()
    bundled = (root / "src" / "lokay" / "data" / "lokay.fala-package.toml").read_bytes()
    assert authored == bundled
    authored.decode("ascii")

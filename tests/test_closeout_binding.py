"""A surviving single-PR path must retain its real organ binding."""

from lokay.fala_organ import _handle


def test_inspect_closeout_pr_has_real_binding(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    out = _handle("inspect_closeout_pr", {"selected": {"repo": "o/r", "pr": {"number": 7, "mergeable": "CONFLICTING"}}}, {})
    assert out["route"] == "conflict"

"""Atomic pr_triage engine selection."""

from lokay.compose._atoms import use_fala


def test_use_fala_default_off(monkeypatch):
    monkeypatch.delenv("LOKAY_USE_FALA", raising=False)
    assert use_fala() is False


def test_use_fala_on(monkeypatch):
    monkeypatch.setenv("LOKAY_USE_FALA", "1")
    assert use_fala() is True

"""Preflight incident cooldown: no duplicate creates for same fingerprint."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from lokay import preflight


def _cfg(tmp_path: Path, **kw):
    base = dict(
        state_path=tmp_path / "state.jsonl",
        incident_repo="mikolaj92/lokay",
        incident_cooldown_hours=12.0,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _source_fail(fp="deadbeefcafebabe"):
    return {
        "fingerprint": fp,
        "findings": [
            preflight._finding("github_authentication", True, "ok"),
            preflight._finding("fala_smoke", False, "unavailable"),
        ],
    }


def test_open_match_reuses_without_create(monkeypatch, tmp_path):
    cfg = _cfg(tmp_path)
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        argv = list(argv)

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        if argv[:3] == ["gh", "api", "--method"]:
            R.stdout = json.dumps(
                [
                    [
                        {
                            "number": 7,
                            "body": "<!-- lokay-preflight:deadbeefcafebabe -->\nfail",
                        }
                    ]
                ]
            )
            return R()
        if argv[:3] == ["gh", "issue", "comment"]:
            return R()
        if argv[:3] == ["gh", "issue", "create"]:
            raise AssertionError("create must not run when open match exists")
        return R()

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    url = preflight._github_incident(_source_fail(), cfg=cfg)
    assert url == "https://github.com/mikolaj92/lokay/issues/7"
    assert any(c[:3] == ["gh", "issue", "comment"] for c in calls)
    assert not any(c[:3] == ["gh", "issue", "create"] for c in calls)


def test_cooldown_skips_duplicate_create(monkeypatch, tmp_path):
    cfg = _cfg(tmp_path)
    ledger = {
        "deadbeefcafebabe": {
            "fingerprint": "deadbeefcafebabe",
            "incident_url": "https://github.com/mikolaj92/lokay/issues/9",
            "number": 9,
            "created_at": 1_700_000_000.0,
            "last_incident_at": 1_700_000_000.0,
        }
    }
    path = tmp_path / "preflight-incidents.json"
    path.write_text(json.dumps(ledger), encoding="utf-8")
    creates: list[list[str]] = []

    def fake_run(argv, **kwargs):
        argv = list(argv)

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        if argv[:3] == ["gh", "api", "--method"]:
            R.stdout = "[]"
            return R()
        if argv[:3] == ["gh", "issue", "create"]:
            creates.append(argv)
            raise AssertionError("create skipped during cooldown")
        if argv[:3] in (["gh", "issue", "reopen"], ["gh", "issue", "comment"]):
            raise AssertionError("cooldown must not mutate GitHub")
        return R()

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    monkeypatch.setattr(preflight.time, "time", lambda: 1_700_000_000.0 + 3600)
    url = preflight._github_incident(_source_fail(), cfg=cfg)
    assert url == "https://github.com/mikolaj92/lokay/issues/9"
    assert creates == []


def test_cooldown_expired_creates_once(monkeypatch, tmp_path):
    cfg = _cfg(tmp_path, incident_cooldown_hours=1.0)
    ledger = {
        "deadbeefcafebabe": {
            "fingerprint": "deadbeefcafebabe",
            "incident_url": "https://github.com/mikolaj92/lokay/issues/9",
            "number": 9,
            "created_at": 1_700_000_000.0,
            "last_incident_at": 1_700_000_000.0,
        }
    }
    (tmp_path / "preflight-incidents.json").write_text(
        json.dumps(ledger), encoding="utf-8"
    )

    def fake_run(argv, **kwargs):
        argv = list(argv)

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        if argv[:3] == ["gh", "api", "--method"]:
            R.stdout = "[]"
            return R()
        if argv[:3] == ["gh", "issue", "reopen"]:
            R.returncode = 1
            return R()
        if argv[:3] == ["gh", "issue", "view"]:
            R.stdout = json.dumps({"state": "CLOSED"})
            return R()
        if argv[:3] == ["gh", "issue", "create"]:
            R.stdout = "https://github.com/mikolaj92/lokay/issues/22\n"
            return R()
        return R()

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    monkeypatch.setattr(preflight.time, "time", lambda: 1_700_000_000.0 + 7200)
    url = preflight._github_incident(_source_fail(), cfg=cfg)
    assert url == "https://github.com/mikolaj92/lokay/issues/22"
    saved = json.loads((tmp_path / "preflight-incidents.json").read_text())
    assert saved["deadbeefcafebabe"]["number"] == 22


def test_incident_repo_is_configurable(monkeypatch, tmp_path):
    cfg = _cfg(tmp_path, incident_repo="acme/ops")
    seen: list[str] = []

    def fake_run(argv, **kwargs):
        argv = list(argv)
        seen.extend(argv)

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        if argv[:3] == ["gh", "api", "--method"]:
            R.stdout = "[]"
            return R()
        if argv[:3] == ["gh", "issue", "create"]:
            R.stdout = "https://github.com/acme/ops/issues/3\n"
            return R()
        return R()

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    url = preflight._github_incident(_source_fail(), cfg=cfg)
    assert url == "https://github.com/acme/ops/issues/3"
    assert "repos/acme/ops/issues" in " ".join(seen)
    assert "--repo" in seen and "acme/ops" in seen


def test_open_match_within_cooldown_skips_comment_spam(monkeypatch, tmp_path):
    cfg = _cfg(tmp_path)
    (tmp_path / "preflight-incidents.json").write_text(
        json.dumps(
            {
                "deadbeefcafebabe": {
                    "fingerprint": "deadbeefcafebabe",
                    "incident_url": "https://github.com/mikolaj92/lokay/issues/7",
                    "number": 7,
                    "last_incident_at": 1_700_000_000.0,
                }
            }
        ),
        encoding="utf-8",
    )
    comments = 0

    def fake_run(argv, **kwargs):
        nonlocal comments
        argv = list(argv)

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        if argv[:3] == ["gh", "api", "--method"]:
            R.stdout = json.dumps(
                [
                    [
                        {
                            "number": 7,
                            "body": "<!-- lokay-preflight:deadbeefcafebabe -->",
                        }
                    ]
                ]
            )
            return R()
        if argv[:3] == ["gh", "issue", "comment"]:
            comments += 1
            return R()
        return R()

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    monkeypatch.setattr(preflight.time, "time", lambda: 1_700_000_000.0 + 60)
    url = preflight._github_incident(_source_fail(), cfg=cfg)
    assert url.endswith("/issues/7")
    assert comments == 0

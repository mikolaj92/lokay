"""Contracts for one supplemental PR-review evidence catalog atom."""


def _collector(kind, seen):
    def collect(*, repo, pr, live):
        seen.append(kind)
        return {"ok": True, "collected": True, "additional_evidence": {"payload": kind}}

    return collect


def test_skips_when_route_not_evidence():
    from lokay.proc.review_evidence_catalog import run

    out = run(
        {"ok": True, "route": "publish", "evidence_kind": "none"},
        repo="a/b",
        pr=1,
        live=False,
        expected_sha="abc",
    )
    assert out["ok"] is True and out["route"] == "not_applicable"


def test_dispatches_each_evidence_kind(monkeypatch):
    from lokay.proc import review_evidence_catalog as cat

    seen = []
    for kind, modname in cat._COLLECTORS.items():
        monkeypatch.setattr(f"{modname}.collect", _collector(kind, seen))
    monkeypatch.setattr(
        "lokay.proc.verify_review_evidence_sha.verify",
        lambda **_k: {"ok": True, "route": "agent", "head_sha": "abc"},
    )
    for kind in ("pr_metadata", "changed_files", "diff_tail", "commit_summary"):
        seen.clear()
        out = cat.run(
            {"ok": True, "route": "evidence", "evidence_kind": kind},
            repo="a/b",
            pr=7,
            live=True,
            expected_sha="abc",
        )
        assert out["ok"] is True and out["route"] == "agent"
        assert out["additional_evidence"] == {
            "kind": kind,
            "value": {"payload": kind},
        }
        assert seen == [kind]


def test_fail_closed_on_bad_sha(monkeypatch):
    from lokay.proc import review_evidence_catalog as cat

    monkeypatch.setattr(
        "lokay.proc.collect_review_diff_tail.collect",
        lambda **_k: {
            "ok": True,
            "collected": True,
            "additional_evidence": {"diff_tail": "x"},
        },
    )
    monkeypatch.setattr(
        "lokay.proc.verify_review_evidence_sha.verify",
        lambda **_k: {
            "ok": True,
            "route": "fail_closed",
            "reason": "supplemental review evidence SHA changed",
            "expected_sha": "old",
            "actual_sha": "new",
        },
    )
    out = cat.run(
        {"ok": True, "route": "evidence", "evidence_kind": "diff_tail"},
        repo="a/b",
        pr=7,
        live=True,
        expected_sha="old",
    )
    assert out["ok"] is True and out["route"] == "fail_closed"
    assert out.get("additional_evidence") is None


def test_fail_closed_when_collect_missing(monkeypatch):
    from lokay.proc import review_evidence_catalog as cat

    monkeypatch.setattr(
        "lokay.proc.collect_review_changed_files.collect",
        lambda **_k: {"ok": True, "collected": False, "reason": "unavailable"},
    )
    out = cat.run(
        {"ok": True, "route": "evidence", "evidence_kind": "changed_files"},
        repo="a/b",
        pr=7,
        live=True,
        expected_sha="abc",
    )
    assert out == {
        "ok": True,
        "route": "fail_closed",
        "reason": "unavailable",
        "evidence_kind": "changed_files",
        "probe_failed": False,
    }


def test_unknown_kind_fail_closed():
    from lokay.proc.review_evidence_catalog import run

    out = run(
        {"ok": True, "route": "evidence", "evidence_kind": "arbitrary"},
        repo="a/b",
        pr=1,
        live=False,
        expected_sha="abc",
    )
    assert out["ok"] is True and out["route"] == "fail_closed"

"""Leftover overflow parks the first authored handful; it does not fail the pass."""

from lokay.proc.leftover_catalog import CANDIDATE_SLOTS, run
from lokay.proc.reduce_leftover_candidates import reduce_candidates


def test_too_many_repos_still_probes(monkeypatch):
    listed = []

    def fetch(selected, **_k):
        listed.append(selected["repo"])
        return {**selected, "ok": True, "route": "listed", "numbers": []}

    monkeypatch.setattr("lokay.proc.list_leftover_closed_ready.fetch", fetch)
    out = run(
        {
            "ok": True,
            "route": "probe",
            "repos": [f"o/r{i}" for i in range(40)],
            "labels": ["work:ready"],
            "mutations_allowed": True,
            "live": True,
        },
        config_path=None,
        live=True,
    )
    assert out["ok"] is True
    assert listed == [f"o/r{i}" for i in range(40)]
    assert out.get("leftover_skip") is not True
    assert out["leftover_closed"] == 0


def test_too_many_candidates_parks_first_handful():
    rows = [
        {
            "candidates": [
                {"repo": f"o/r{i}", "number": i} for i in range(40)
            ]
        }
    ]
    out = reduce_candidates(
        {"route": "probe", "mutations_allowed": True, "live": True},
        rows,
        slot_count=30,
    )
    assert out["ok"] is True
    assert out["leftover_skip"] is True
    assert out["leftover_overflow"] is True
    assert out["reason"] == "leftover_overflow"
    assert out["count"] == 40
    assert [c["number"] for c in out["candidates"]] == list(range(30))
    assert CANDIDATE_SLOTS == 30

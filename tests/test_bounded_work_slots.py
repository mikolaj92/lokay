"""Repeated work slots are authored once; Fala owns their expansion."""

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("path_id", ["executor_rows", "product_pass_budget"])
def test_work_slots_use_native_bounded_expansion(path_id):
    package = tomllib.loads((ROOT / "fala/lokay.fala-package.toml").read_text())
    path = next(p for p in package["correlation_paths"] if p["id"] == path_id)
    assert "effectors" not in path
    assert path["expansion"]["max_items"] == 8
    assert path["expansion"]["serial"] is True
    template = next(t for t in package["path_templates"] if t["id"] == path["expansion"]["template"])
    assert all("${index}" in e["id"] for e in template["effectors"])
    assert [item["index"] for item in path["expansion"]["items"]] == list(range(2, 9))
    # The first slot has no previous receipt; it remains an explicit prefix.
    assert path["prefix_effectors"][1]["id"].endswith("_1")

"""Public tick prose must describe the authored parent, not a second spine."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tick_prose_lists_authored_department_runs_in_order():
    package = tomllib.loads((ROOT / "fala/lokay.fala-package.toml").read_text())
    parent = next(p for p in package["correlation_paths"] if p["id"] == "factory_pass")
    expected = [e["id"] for e in parent["effectors"] if re.fullmatch(r"run_\w+_department", e["id"])]
    prose = (ROOT / "README.md").read_text().split("## What one tick does\n", 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^\d+\. `([^`]+)`", prose, re.MULTILINE) == expected
    assert "`host_ff`" in prose
    assert "`record_pass`" in prose
    assert "sibling" in prose
    assert "`select_implement` after `factory_begin`" not in prose


def test_docs_do_not_present_unwired_idle_classifier_as_a_live_node():
    package = tomllib.loads((ROOT / "fala/lokay.fala-package.toml").read_text())
    atoms = {e["id"] for p in package["correlation_paths"] for e in p.get("effectors", [])}
    for filename in ("GRAPH.md", "WORKING.md"):
        text = (ROOT / "docs" / filename).read_text()
        if "classify_factory_idle" not in atoms:
            assert "`classify_factory_idle`" not in text
    assert "second `factory_pass`" not in (ROOT / "docs/GRAPH.md").read_text()


def test_unix_map_classifies_every_program_without_implying_order():
    text = (ROOT / "docs/UNIX.md").read_text()
    assert "## Top-level vs nested vs CLI" in text
    rows = [line for line in text.splitlines() if line.startswith("| `lokay")]
    assert rows
    for row in rows:
        assert row.split("|")[2].strip() in {"top", "nested", "cli-wrapper", "legacy-unused"}

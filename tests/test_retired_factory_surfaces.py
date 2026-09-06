"""Retired orchestration must not return as a second Python process."""

from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_unwired_idle_atoms_and_old_parent_bindings_are_removed():
    import ast

    retired = {
        "classify_factory_idle", "record_factory_idle", "survey_prs",
        "survey_inbox", "survey_ready", "plan_pass", "resolve_conflicts",
        "closeout_prs", "reap_stale_implementing", "reap_over_budget",
        "refresh_occupancy",
    }
    tree = ast.parse((ROOT / "src/lokay/organ/factory.py").read_text())
    bindings = {
        value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
        and node.left.id == "atom"
        for comparator in node.comparators
        for value in ast.walk(comparator)
        if isinstance(value, ast.Constant) and isinstance(value.value, str)
    }
    assert not bindings.intersection(retired)
    assert not (ROOT / "src/lokay/proc/classify_factory_idle.py").exists()
    assert not (ROOT / "src/lokay/proc/record_factory_idle.py").exists()


def test_retired_fleet_paths_and_cli_wrappers_are_absent():
    retired = {
        "survey_prs", "survey_inbox", "survey_ready", "plan_pass",
        "closeout_prs", "refresh_occupancy", "reap_over_budget",
        "reap_stale_implementing", "resolve_conflicts",
    }
    package = tomllib.loads((ROOT / "fala/lokay.fala-package.toml").read_text())
    assert not retired.intersection(p["id"] for p in package["correlation_paths"])
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]
    assert not retired.intersection(v.split(":")[0].split(".")[-1] for v in scripts.values())
    for name in retired:
        assert not (ROOT / "src/lokay/proc" / (name + "_subflow.py")).exists()


def test_survey_bridge_is_removed_from_code_and_cli():
    assert not (ROOT / "src/lokay/proc/survey_repos.py").exists()
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]
    assert "lokay-survey-repos" not in scripts
    for name in ("factory", "recovery"):
        assert "survey_repos" not in (ROOT / f"src/lokay/organ/{name}.py").read_text()

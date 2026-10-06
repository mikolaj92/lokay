import json

import pytest

from lokay.approach_plan import repo_file_hints
from lokay.localize import build_localization, extract_seed_paths, walk_repo_tree
from lokay.localize_agent import LocalizeAgentError, parse_localize_output
from lokay.proc.validate_localization_paths import validate as validate_paths
from lokay.proc.validate_relocalization_approval import validate as approve


def test_ci_workflow_identity_survives_planner_and_localization(tmp_path):
    workflow = tmp_path / ".github/workflows/test.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: test\njobs: {}\n")
    control = tmp_path / ".git/objects"
    control.mkdir(parents=True)
    (control / "private").write_text("git metadata")
    seed = "Add pytest CI in `.github/workflows/test.yml`."
    tree = walk_repo_tree(tmp_path)
    assert ".github/workflows/test.yml" in tree
    assert not any(path == ".git" or path.startswith(".git/") for path in tree)
    hints = repo_file_hints(tmp_path, ["./.github/workflows/test.yml"])
    assert hints == (".github/workflows/test.yml",)
    localized = build_localization(worktree=tmp_path, seed_text=seed, extra_paths=hints)
    assert ".github/workflows/test.yml" in localized.paths
    assert "github/workflows/test.yml" not in localized.paths
    new_path = ".github/workflows/new-test.yml"
    parsed = parse_localize_output('{"paths":[".github/workflows/new-test.yml"]}')
    valid = validate_paths({}, {"tree": tree}, {"paths": parsed}, {})
    assert valid["paths"] == [new_path]
    assert approve({"route": "valid", "paths": parsed}, {"off_goal_paths": [new_path]})["approved"] == [new_path]
    assert extract_seed_paths('File "/tmp/repo/src/foo.py", line 1') == ("src/foo.py",)
    assert extract_seed_paths('File "../src/foo.py", line 1') == ()
    for unsafe in ["../README.md", "/README.md", "C:/README.md", "//host/README.md"]:
        with pytest.raises(LocalizeAgentError):
            parse_localize_output(json.dumps({"paths": [unsafe]}))

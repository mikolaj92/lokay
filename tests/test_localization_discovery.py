import json

from lokay.localize import load_existing_localize_paths, walk_repo_tree


def test_swiftpm_dependencies_do_not_consume_product_discovery_budget(tmp_path):
    dependency = tmp_path / "App/.build/checkouts/dependency/Sources"
    dependency.mkdir(parents=True)
    for number in range(20):
        (dependency / f"Dependency{number}.swift").write_text("struct Dependency {}\n")
    source = tmp_path / "App/Sources/PlnFlrCapture"
    source.mkdir(parents=True)
    (source / "WorkspaceView.swift").write_text("struct WorkspaceView {}\n")
    assert walk_repo_tree(tmp_path, max_entries=5) == (
        "App",
        "App/Sources",
        "App/Sources/PlnFlrCapture",
        "App/Sources/PlnFlrCapture/WorkspaceView.swift",
    )


def test_retained_swiftpm_scope_is_relocalized(tmp_path):
    product = tmp_path / "App/Sources/WorkspaceView.swift"
    product.parent.mkdir(parents=True)
    product.write_text("struct WorkspaceView {}\n")
    dependency = tmp_path / "App/.build/checkouts/dependency/Sources/Dependency.swift"
    dependency.parent.mkdir(parents=True)
    dependency.write_text("struct Dependency {}\n")
    evidence = tmp_path / ".lokay/localize.json"
    evidence.parent.mkdir()
    evidence.write_text(json.dumps({
        "issue": 37,
        "paths": ["App/Sources/WorkspaceView.swift", "App/.build/checkouts/dependency/Sources/Dependency.swift"],
    }))
    assert load_existing_localize_paths(tmp_path, issue=37) == []
    evidence.write_text(json.dumps({"issue": 37, "paths": ["App/Sources/WorkspaceView.swift"]}))
    assert load_existing_localize_paths(tmp_path, issue=37) == ["App/Sources/WorkspaceView.swift"]

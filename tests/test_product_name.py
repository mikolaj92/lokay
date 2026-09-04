from pathlib import Path


def test_legacy_product_name_is_absent() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden = "m" + "ill"
    excluded = {".git", ".venv", "__pycache__"}
    hits = []
    for path in root.rglob("*"):
        if not path.is_file() or excluded.intersection(path.parts):
            continue
        if forbidden in path.name.lower():
            hits.append(str(path.relative_to(root)))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if forbidden in text.lower():
            hits.append(str(path.relative_to(root)))
    assert hits == []

"""Compare OCR's deterministic selection with the host's exact diff."""
from typing import Any, Mapping

from .contract import ContractError


def validate_scope(request: Mapping[str, Any], preview: Mapping[str, Any]) -> None:
    rows = preview.get("files")
    inventory = request["diff_paths"]
    if not isinstance(rows, list) or len(rows) != len(inventory):
        raise ContractError("preview inventory mismatch")
    expected = {row["path"]: row for row in inventory}
    if len(expected) != len(inventory):
        raise ContractError("ambiguous preview inventory")
    seen = set()
    selected = 0
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("path"), str):
            raise ContractError("malformed preview path")
        path = row["path"]
        if path in seen or path not in expected:
            raise ContractError("preview inventory mismatch")
        seen.add(path)
        source = expected[path]
        # OCR uses `binary` as a content kind, while Git preserves A/M/R/D.
        # This is an uncovered path, not identity drift; never silently waive it.
        if row.get("status") == "binary" and row.get("exclude_reason") == "binary" and row.get("will_review") is False:
            raise ContractError("preview contains unreviewed binary paths")
        if row.get("status") != source["status"]:
            raise ContractError("preview path status mismatch")
        required = source["status"] != "deleted"
        if row.get("will_review") is not required:
            raise ContractError("preview omitted required diff path")
        if required and row.get("exclude_reason") not in (None, ""):
            raise ContractError("preview omitted required diff path")
        selected += int(required)
    if not selected:
        raise ContractError("preview is incomplete or empty")
    counts = {"total_files": len(rows), "reviewable_count": selected,
              "excluded_count": len(rows) - selected}
    if any(type(preview.get(key)) is not int or preview[key] != value for key, value in counts.items()):
        raise ContractError("preview counts mismatch")

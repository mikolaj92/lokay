"""Protected, pre-builder acceptance artifacts."""
from __future__ import annotations
import hashlib, json, os
from pathlib import Path
from typing import Any

KINDS = {"test", "cli_contract", "html_snapshot", "graph_diff", "external_fact"}

def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()

def prepare_acceptance(issue: dict[str, Any], *, root: Path, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    if any(row.get("kind") not in KINDS for row in evidence): raise ValueError("unknown acceptance evidence kind")
    identity = f"{issue['repo']}#{int(issue['number'])}"
    body = {"schema":"lokay.acceptance/1","identity":identity,"issue":{"repo":issue["repo"],"number":int(issue["number"]),"title":issue.get("title","")},"expected_observable_outcomes":[line[1:].strip() for line in str(issue.get("body","")).splitlines() if line.strip().startswith("-")],"evidence":evidence,"protected_paths":[".lokay/acceptance.json"]}
    digest = _digest(body); directory = root / identity.replace("/","__").replace("#","__"); directory.mkdir(parents=True,exist_ok=True)
    path = directory / "acceptance.json"
    text = _canonical(body) + "\n"
    if path.exists():
        if path.read_text() != text: raise ValueError("acceptance identity already exists with different digest")
    else:
        path.write_text(text); os.chmod(path,0o444)
    return {**body,"digest":digest,"path":str(path)}

def verify_acceptance(path: str|Path, observed: list[dict[str,Any]], expected_digest: str) -> dict[str,Any]:
    body = json.loads(Path(path).read_text())
    actual = _digest(body)
    if actual != expected_digest: raise ValueError("acceptance digest mismatch")
    required = {row["kind"] for row in body["evidence"]}; by_kind = {row.get("kind"):row for row in observed}
    failures = sorted(kind for kind in required if by_kind.get(kind,{}).get("ok") is not True)
    accepted = not failures
    return {"schema":"lokay.acceptance-verdict/1","acceptance_digest":actual,"accepted":accepted,"route":"publish" if accepted else "repair","failed_evidence":failures,"evidence_refs":[row.get("ref") for row in observed if row.get("ref")]}

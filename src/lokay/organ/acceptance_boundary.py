"""Protected acceptance preparation and independent verification atoms."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from lokay.acceptance import prepare_acceptance, verify_acceptance


def handle_acceptance(atom: str, inputs: dict[str,Any], up: dict[str,dict[str,Any]], ctx: dict[str,Any]) -> dict[str,Any]|None:
    if atom == "prepare_acceptance":
        issue = dict(up.get("get_issue",{}).get("issue") or {})
        root = Path.home()/".lokay"/"acceptance"
        evidence = list(inputs.get("evidence") or [{"kind":"test","expect":"declared repository tests pass"}])
        return {"ok":True, **prepare_acceptance(issue,root=root,evidence=evidence)}
    if atom == "verify_acceptance":
        artifact = up.get("prepare_acceptance") or {}
        tested = up.get("local_repair_execution") or up.get("test_local_execution") or {}
        observation = {"kind":"test","ok": bool(tested.get("ok") or tested.get("passed")),"ref":str(tested.get("tests") or "local-test")}
        try:
            verdict=verify_acceptance(str(artifact.get("path") or ""),[observation],str(artifact.get("digest") or ""))
            return {"ok":verdict["accepted"],**verdict}
        except Exception as exc:
            return {"ok":False,"accepted":False,"route":"repair","reason":"acceptance_invalid","error":str(exc)}
    return None

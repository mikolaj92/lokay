"""Vendor-neutral executor continuity derived from durable work identity."""
from __future__ import annotations
import hashlib,json
from typing import Any

def _identity(**values: Any) -> str:
    body=json.dumps(values,sort_keys=True,separators=(",",":"))
    return hashlib.sha256(body.encode()).hexdigest()

def resolve_session(*,policy:str,repo:str,role:str,issue:int|None=None,pr:int|None=None,branch:str="",head_sha:str="",base_sha:str="",prior:dict[str,Any]|None=None)->dict[str,Any]:
    if policy not in {"fresh","resume","inherit"}: raise ValueError("unknown session policy")
    identity=_identity(repo=repo,role=role,issue=issue,pr=pr,branch=branch,head_sha=head_sha,base_sha=base_sha)
    continuity=_identity(repo=repo,issue=issue,branch=branch,head_sha=head_sha,base_sha=base_sha)
    valid_prior=bool(prior and prior.get("continuity_digest")==continuity)
    resolved=policy; reason="authored"
    if policy=="resume" and not valid_prior: resolved="fresh"; reason="identity_changed" if prior else "first_run"
    if policy=="inherit" and not valid_prior: raise ValueError("inherit source identity changed")
    session_id=(prior or {}).get("session_id") if resolved in {"resume","inherit"} else "lokay-session-"+identity[:20]
    out={"schema":"lokay.session/1","policy":policy,"resolved_policy":resolved,"session_id":session_id,"work_identity_digest":identity,"continuity_digest":continuity,"reason":reason,"role":role}
    if policy=="inherit": out["source_session_id"]=(prior or {})["session_id"]
    return out

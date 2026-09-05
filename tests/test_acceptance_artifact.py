from pathlib import Path
import pytest
from lokay.acceptance import prepare_acceptance, verify_acceptance


def issue():
    return {"repo":"mikolaj92/app","number":7,"title":"Add CLI output","body":"Acceptance:\n- CLI exits zero\n- output is JSON"}


def test_prepare_is_canonical_immutable_and_supports_explicit_evidence(tmp_path: Path):
    artifact = prepare_acceptance(issue(), root=tmp_path, evidence=[
        {"kind":"test","expect":"tests pass"}, {"kind":"cli_contract","expect":"exit 0"},
        {"kind":"html_snapshot","expect":"matches"}, {"kind":"graph_diff","expect":"compatible"},
        {"kind":"external_fact","expect":"issue closed"},
    ])
    assert artifact["identity"] == "mikolaj92/app#7"
    assert len(artifact["digest"]) == 71
    path = Path(artifact["path"])
    assert path.exists() and not (path.stat().st_mode & 0o222)
    again = prepare_acceptance(issue(), root=tmp_path, evidence=artifact["evidence"])
    assert again["digest"] == artifact["digest"]


def test_verify_fails_closed_on_tamper_or_failed_evidence(tmp_path: Path):
    artifact = prepare_acceptance(issue(), root=tmp_path, evidence=[{"kind":"test","expect":"green"}])
    verdict = verify_acceptance(artifact["path"], [{"kind":"test","ok":False,"ref":"test:1"}], artifact["digest"])
    assert verdict["route"] == "repair" and verdict["accepted"] is False
    Path(artifact["path"]).chmod(0o600); Path(artifact["path"]).write_text("{}")
    with pytest.raises(ValueError, match="digest"):
        verify_acceptance(artifact["path"], [], artifact["digest"])

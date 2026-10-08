from lokay.claim import claim
from lokay.events import Log


def test_stale_token_is_a_contract_failure(tmp_path):
    log = Log(tmp_path / "lokay.db")
    token = log.acquire("repo:o/r", "tick", ttl_s=300)
    log.release("repo:o/r", token)
    out = claim(log, resource="repo:o/r", token=token, mode="build")
    assert out["terminal"] == "contract_failed"


def test_live_token_claims_a_build(tmp_path):
    log = Log(tmp_path / "lokay.db")
    token = log.acquire("repo:o/r", "tick", ttl_s=300)
    out = claim(log, resource="repo:o/r", token=token, mode="build")
    assert out == {"ok": True, "mode": "build", "review_round": 0, "fix_budget": 1}

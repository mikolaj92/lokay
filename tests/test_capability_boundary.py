"""Graph effect authority is separate from the harness runtime."""
from lokay.capabilities import authorize_effect


def test_dedicated_effect_gets_only_authored_authority_and_denial_is_traceable():
    assert authorize_effect("merge_effect", "pr.merge")["allowed"]
    assert authorize_effect("builder", "code.write")["allowed"]
    assert not authorize_effect("builder", "pr.merge")["allowed"]
    assert not authorize_effect("builder", "acceptance.write")["allowed"]
    assert not authorize_effect("reviewer", "git.push")["allowed"]
    assert authorize_effect("reviewer", "pr.merge") == {
        "allowed": False,
        "route": "fail_closed",
        "reason": "capability_denied",
        "role": "reviewer",
        "capability": "pr.merge",
        "trace": True,
    }

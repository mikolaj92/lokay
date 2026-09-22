import pytest
from lokay.delivery_receipt import marker, parse_marker, verify_receipt, finalize_receipt


def base():
    from test_delivery_provenance import completed_lineage
    return {**completed_lineage(), 'repo':'a/b', 'issue':7, 'work_id':'a/b#7',
            'acceptance_identity':'a/b#7'}

def test_one_canonical_marker_roundtrips_without_prompts_or_secrets():
    text=marker(base()); parsed=parse_marker('body\n'+text+'\n')
    assert parsed['head_sha']=='b'*40 and text.count('lokay-autonomous-delivery:')==1
    assert 'prompt' not in text and 'token' not in text

def test_manual_or_tampered_pr_is_not_autonomous():
    assert parse_marker('manual') is None
    with pytest.raises(ValueError,match='digest|head'):
        verify_receipt({**base(),'head_sha':'x'},observed_head='h')

def test_final_receipt_requires_main_merge_and_closed_issue():
    complete=finalize_receipt(base(),merge_sha='m',merged_at='t',issue_closed=True,main_contains_head=True)
    assert verify_receipt(complete,observed_head='b'*40,require_delivered=True)['autonomous']
    with pytest.raises(ValueError,match='delivery'):
        finalize_receipt(base(),merge_sha='m',merged_at='t',issue_closed=False,main_contains_head=True)


def test_publish_delivery_receipt_replaces_provisional_marker_after_observation():
    from lokay.proc.publish_delivery_receipt import publish

    provisional = marker(base())
    out = publish(
        repo="a/b",
        pr=9,
        issue=7,
        merge={"merged": True},
        close={"issue": 7},
        live=True,
        read_pr=lambda *_: {
            "body": f"summary\n{provisional}\n",
            "headRefOid": "b" * 40,
            "mergeCommit": {"oid": "m"},
            "mergedAt": "t",
        },
        read_issue=lambda *_: {"state": "CLOSED"},
        main_contains=lambda *_: True,
        edit_pr=lambda _repo, _pr, body: body,
    )

    assert out["confirmed"] is True
    receipt = parse_marker(out["body"])
    assert receipt is not None
    assert receipt["merge_sha"] == "m"
    assert receipt["issue_closed"] is True
    assert verify_receipt(receipt, observed_head="b" * 40, require_delivered=True)["autonomous"]


def test_receipt_organ_uses_closed_issue_and_configured_runner(monkeypatch):
    from lokay.organ.lanes import handle_lanes
    from lokay import gh_prs
    from lokay.proc import _common
    from lokay import config

    configured = object()
    carrier = object()
    monkeypatch.setattr(config, "load_config", lambda path: configured if path == "chosen.yaml" else pytest.fail("wrong config"))
    monkeypatch.setattr(_common, "runner", lambda cfg: carrier if cfg is configured else pytest.fail("unconfigured runner"))
    monkeypatch.setattr(_common, "mutations_allowed", lambda **kw: kw['cfg'] is configured)
    calls = []

    def read(runner, args, *, live):
        assert runner is carrier and live
        calls.append(args)
        if args[:2] == ["pr", "view"]:
            return {"body": marker(base()), "headRefOid": "b" * 40, "mergeCommit": {"oid": "m"}, "mergedAt": "t"}
        assert args[:3] == ["issue", "view", "7"]
        return {"state": "CLOSED"}

    def text(runner, args, *, live, require_success):
        assert runner is carrier and live and require_success
        calls.append(args)
        return "ahead" if args[0] == "api" else ""

    monkeypatch.setattr(gh_prs, "gh_json", read)
    monkeypatch.setattr(gh_prs, "gh_text", text)
    out = handle_lanes("publish_delivery_receipt", {"live": True, "config_path": "chosen.yaml"},
                       {"pr_merge": {"merged": True}, "close_issue": {"ok": True, "closed": True, "repo": "a/b", "issue": 7}},
                       {"cfg": [], "live": ["--live"], "repo": "a/b", "pr_number": 9, "issue_number": None, "branch": "ai/fix/7-title"})
    assert out["route"] == "confirmed"
    assert out["issue"] == 7
    assert len(calls) == 4


@pytest.mark.parametrize("change", [{"repo": "other/repo"}, {"issue": 8}, {"head_sha": "old"}])
def test_receipt_never_rebinds_provenance_to_other_delivery(change):
    from lokay.proc.publish_delivery_receipt import publish
    out = publish(repo="a/b", pr=9, issue=7, merge={"merged": True}, close={}, live=True,
                  read_pr=lambda *_: {"body": marker({**base(), **change}), "headRefOid": "b" * 40, "mergeCommit": {"oid": "m"}, "mergedAt": "t"},
                  read_issue=lambda *_: {"state": "CLOSED"}, main_contains=lambda *_: True,
                  edit_pr=lambda *_: pytest.fail("must not rewrite provenance"))
    assert out["route"] == "pending"
    assert out["reason"] == "receipt_identity_mismatch"


def test_receipt_repeat_is_confirmed_without_second_write():
    from lokay.proc.publish_delivery_receipt import publish
    complete = finalize_receipt(base(), merge_sha="m", merged_at="t", issue_closed=True, main_contains_head=True)
    out = publish(repo="a/b", pr=9, issue=7, merge={"merged": True}, close={}, live=True,
                  read_pr=lambda *_: {"body": marker(complete), "headRefOid": "b" * 40, "mergeCommit": {"oid": "m"}, "mergedAt": "t"},
                  read_issue=lambda *_: {"state": "CLOSED"}, main_contains=lambda *_: True,
                  edit_pr=lambda *_: pytest.fail("receipt already published"))
    assert out["confirmed"] is True


def test_publish_delivery_receipt_fails_closed_without_authoritative_confirmation():
    from lokay.proc.publish_delivery_receipt import publish

    out = publish(
        repo="a/b",
        pr=9,
        issue=7,
        merge={"merged": True},
        close={"issue": 7},
        live=True,
        read_pr=lambda *_: {
            "body": marker(base()),
            "headRefOid": "b" * 40,
            "mergeCommit": {"oid": "m"},
            "mergedAt": "t",
        },
        read_issue=lambda *_: {"state": "OPEN"},
        main_contains=lambda *_: True,
        edit_pr=lambda *_: pytest.fail("must not publish an unconfirmed receipt"),
    )

    assert out["ok"] is True
    assert out["confirmed"] is False
    assert out["route"] == "pending"

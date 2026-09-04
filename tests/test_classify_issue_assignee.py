from lokay.proc.classify_issue_assignee import classify, foreign, takeable


def test_empty_and_lokaj_are_takeable():
    lokay = "mikolaj92"
    assert takeable({"assignees": []}, lokay)
    assert takeable({"assignees": ["mikolaj92"]}, lokay)
    assert classify({"assignees": []}, lokay)["route"] == "take"


def test_pawel_alone_or_beside_lokaj_is_foreign():
    lokay = "mikolaj92"
    pawel = {"assignees": ["PSyron"]}
    both = {"assignees": ["PSyron", "mikolaj92"]}
    assert foreign(pawel, lokay) == ["PSyron"]
    assert foreign(both, lokay) == ["PSyron"]
    assert not takeable(pawel, lokay)
    assert not takeable(both, lokay)
    assert classify(both, lokay)["reason"] == "foreign_assignee"


def test_configured_lokay_is_the_only_self():
    assert takeable({"assignees": ["lokay-bot"]}, "lokay-bot")
    assert not takeable({"assignees": ["mikolaj92"]}, "lokay-bot")
from lokay.proc.classify_issue_assignee import classify, foreign, takeable


def test_empty_and_lokaj_are_takeable():
    mill = "mikolaj92"
    assert takeable({"assignees": []}, mill)
    assert takeable({"assignees": ["mikolaj92"]}, mill)
    assert classify({"assignees": []}, mill)["route"] == "take"


def test_pawel_alone_or_beside_lokaj_is_foreign():
    mill = "mikolaj92"
    pawel = {"assignees": ["PSyron"]}
    both = {"assignees": ["PSyron", "mikolaj92"]}
    assert foreign(pawel, mill) == ["PSyron"]
    assert foreign(both, mill) == ["PSyron"]
    assert not takeable(pawel, mill)
    assert not takeable(both, mill)
    assert classify(both, mill)["reason"] == "foreign_assignee"


def test_configured_mill_is_the_only_self():
    assert takeable({"assignees": ["mill-bot"]}, "mill-bot")
    assert not takeable({"assignees": ["mikolaj92"]}, "mill-bot")
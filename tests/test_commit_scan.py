from lokay.commit_scan import scan_added


def test_added_secret_is_flagged():
    diff = "+++ b/config\n+api_key = sk-live\n"
    assert scan_added(diff)["secrets_hit"] is True


def test_removed_secret_is_not_flagged():
    diff = "--- a/config\n-api_key = sk-live\n"
    assert scan_added(diff) == {"secrets_hit": False, "conflict_markers": False}


def test_conflict_marker_is_flagged():
    diff = "+++ b/file\n+<<<<<<< HEAD\n"
    assert scan_added(diff)["conflict_markers"] is True

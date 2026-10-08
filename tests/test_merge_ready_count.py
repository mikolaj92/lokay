from lokay.proc.launch_issue_to_pr import merge_ready_count


def test_count_only_labeled_prs():
    rows = [{'labels': ['ai:merge-ready']}, {'labels': ['ai:pr-opened']}, 'nope']
    assert merge_ready_count(rows) == 1

from lokay.events import project_work_items


def test_projection_covers_the_named_side_states():
    events = [
        {'work_id': 'w', 'kind': 'admitted'},
        {'work_id': 'w', 'kind': 'owner_feedback'},
        {'work_id': 'h', 'kind': 'human_owned'},
        {'work_id': 'q', 'kind': 'quarantined'},
    ]
    assert project_work_items(events) == {'w': 'needs_human', 'h': 'human_owned', 'q': 'quarantined'}

from lokay.compose.human_mailbox import compose_human_mailbox


def test_mailbox_lists_merge_ready(monkeypatch):
    class Repo:
        name = 'o/r'
    class Cfg:
        config_path = 'c'
        needs_feedback_label = 'ai:needs-feedback'
        def active_repos(self):
            return [Repo()]
    class PR:
        number = 7
        title = 't'
        url = 'u'
        labels = ['ai:merge-ready']
    monkeypatch.setattr('lokay.compose.human_mailbox.load_cfg', lambda args: Cfg())
    monkeypatch.setattr('lokay.compose.human_mailbox.runner', lambda cfg: object())
    monkeypatch.setattr('lokay.compose.human_mailbox.list_issues_with_label', lambda *a, **k: [])
    monkeypatch.setattr('lokay.compose.human_mailbox.list_open_ai_prs', lambda *a, **k: [PR()])
    out = compose_human_mailbox(config_path=None, live=False)
    assert out['items'][0]['label'] == 'ai:merge-ready'

from lokay.events import Log


def test_same_idem_appends_once(tmp_path):
    log = Log(tmp_path / 'lokay.db')
    first = log.append('admitted', work_id='w1', idem='same', data={'n': 1})
    second = log.append('admitted', work_id='w1', idem='same', data={'n': 2})
    assert isinstance(first, int)
    assert second is None
    assert log.count() == 1

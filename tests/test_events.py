from lokay.events import Log


def test_same_idem_appends_once(tmp_path):
    log = Log(tmp_path / 'lokay.db')
    first = log.append('admitted', work_id='w1', idem='same', data={'n': 1})
    second = log.append('admitted', work_id='w1', idem='same', data={'n': 2})
    assert isinstance(first, int)
    assert second is None
    assert log.count() == 1

def test_killed_append_leaves_the_database_ok(tmp_path):
    import os
    import signal
    import sqlite3
    path = tmp_path / 'lokay.db'
    log = Log(path)
    if os.fork() == 0:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        log.db.execute('BEGIN')
        log.append('admitted', work_id='w', idem='die', data={'n': 1})
        os.kill(os.getpid(), signal.SIGKILL)
    else:
        os.wait()
    check = sqlite3.connect(path).execute('PRAGMA integrity_check').fetchone()[0]
    assert check == 'ok'

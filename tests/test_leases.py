import multiprocessing
from pathlib import Path

from lokay.events import Log


def _take(path, holder, out):
    log = Log(path)
    out.append(log.acquire('repo:a/b', holder, ttl_s=300))


def test_two_processes_get_one_token(tmp_path):
    path = tmp_path / 'lokay.db'
    Log(path).append('admitted', work_id='w', idem='seed', data={})
    ctx = multiprocessing.get_context('fork')
    results = ctx.Manager().list()
    procs = [ctx.Process(target=_take, args=(str(path), name, results)) for name in ('a', 'b')]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(5)
    tokens = [item for item in results if item is not None]
    assert len(tokens) == 1
    assert tokens[0] > 0

def test_stale_token_fails_after_reacquire(tmp_path):
    log = Log(tmp_path / 'lokay.db')
    first = log.acquire('repo:a/b', 'old', ttl_s=300)
    log.db.execute("UPDATE leases SET expires_at=datetime('now','-1 second') WHERE token=?", (first,))
    log.db.commit()
    second = log.acquire('repo:a/b', 'new', ttl_s=300)
    assert first is not None and second is not None and second > first
    assert log.check('repo:a/b', first) is False
    assert log.check('repo:a/b', second) is True

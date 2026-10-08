from lokay.events import blob_get, blob_put


def test_same_bytes_store_once(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    first = blob_put(b'abc')
    second = blob_put(b'abc')
    assert first == second
    assert blob_get(first) == b'abc'
    files = list((tmp_path / '.lokay' / 'blobs').rglob('*'))
    assert sum(path.is_file() for path in files) == 1


def test_corrupt_blob_raises(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    ref = blob_put(b'abc')
    path = next(path for path in (tmp_path / '.lokay' / 'blobs').rglob('*') if path.is_file())
    path.write_bytes(b'nope')
    try:
        blob_get(ref)
    except ValueError:
        return
    raise AssertionError('corrupt blob was returned')

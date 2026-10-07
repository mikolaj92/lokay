from lokay.config import Config, _yaml_mode


def test_enabled_without_mode_stays_off():
    assert _yaml_mode(None, merge_enabled=True) == 'off'
    cfg = Config(merge_enabled=True)
    assert cfg.merge_mode == 'off'


def test_always_must_be_written():
    assert _yaml_mode('always', merge_enabled=False) == 'always'

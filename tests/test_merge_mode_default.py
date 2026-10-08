from lokay.config import Config, _yaml_mode


def test_enabled_without_mode_stays_off():
    assert _yaml_mode(None, merge_enabled=True) == 'off'
    cfg = Config(merge_enabled=True)
    assert cfg.merge_mode == 'off'


def test_always_must_be_written():
    assert _yaml_mode('always', merge_enabled=False) == 'always'

def test_enabled_true_without_mode_is_off(tmp_path):
    from lokay.config import load_config
    path = tmp_path / 'c.yaml'
    path.write_text('mode: dry-run\nmerge:\n  enabled: true\nrepos: []\n')
    assert load_config(path).merge_mode == 'off'


def test_example_config_is_off():
    from pathlib import Path
    from lokay.config import load_config
    example = Path('config.live-autonomous.example.yaml')
    assert load_config(example).merge_mode == 'off'

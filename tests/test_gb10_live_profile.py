"""The live example pins every semantic route and agent to GB10, not a combo."""

from pathlib import Path

from lokay.agent import build_agent_argv
from lokay.config import load_config
from lokay.typed_decisions import NODES


def test_live_profile_pins_all_decisions_and_agent_to_gb10(tmp_path):
    cfg = load_config(Path('config.live-autonomous.example.yaml'))
    assert cfg.decision_routes == {node: 'gb10' for node in NODES}
    assert set(cfg.decision_endpoints) == {'gb10'}
    endpoint = cfg.decision_endpoints['gb10']
    assert endpoint['url'] == 'http://192.168.1.60:8888/v1/decisions'
    assert endpoint['protocol'] == 'decisions'
    assert endpoint['model'] == 'GLM-5.3-Flash-EXL3'
    argv = build_agent_argv(cfg, worktree=tmp_path, prompt='One task')
    assert argv[argv.index('--provider') + 1] == 'omniroute'
    assert argv[argv.index('--model') + 1] == 'gb10/GLM-5.3-Flash-EXL3'
    assert argv[argv.index('--thinking') + 1] == 'off'

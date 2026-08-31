from pathlib import Path

from lokay.config import load_config


def test_review_style_can_be_configured_per_repository(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text(
        """
mode: dry-run
executor:
  enabled: false
  agent: pi
  command: pi
  args: ["-p", "{prompt}"]
repos:
  - name: a/one
    clone_path: /tmp/one
    review_style: en+kofte
  - name: a/two
    clone_path: /tmp/two
    review_style: en+polish_direct
""",
        encoding="utf-8",
    )
    cfg = load_config(config)
    assert cfg.review_style_for("a/one") == "en+kofte"
    assert cfg.review_style_for("a/two") == "en+polish_direct"
    assert cfg.review_style_for("a/missing") == ""

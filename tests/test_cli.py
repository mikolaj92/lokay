from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from lokay.cli import cmd_validate


def test_validate_lists_only_lokay_from_product_catalog(tmp_path: Path, capsys) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
repos:
  - name: mikolaj92/Temida
    clone_path: {tmp_path / 'Temida'}
  - name: mikolaj92/lokay
    clone_path: {tmp_path / 'lokay'}
  - name: mikolaj92/takt
    clone_path: {tmp_path / 'takt'}
  - name: other/repo
    clone_path: {tmp_path / 'other'}
""",
        encoding="utf-8",
    )

    assert cmd_validate(Namespace(config=str(config))) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["repos"] == ["mikolaj92/lokay"]
    assert payload["repos_disabled"] == []
    assert payload["repos_total"] == 1


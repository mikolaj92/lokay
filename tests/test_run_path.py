from __future__ import annotations

import json

import pytest

from lokay.proc import run_path


def _payload(capsys: pytest.CaptureFixture[str]) -> dict:
    return json.loads(capsys.readouterr().out)






def test_describe_without_repo_still_describes_package(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        run_path, "describe_package", lambda package: {"package": package or "default"}
    )

    assert run_path.main(["--describe"]) == 0
    assert _payload(capsys) == {"ok": True, "package": "default"}

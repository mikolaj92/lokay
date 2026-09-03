"""Host materialization keeps only the requested Fala path."""

from pathlib import Path

from lokay.graph_run import _materialize_package, find_default_package


def test_materialize_keeps_only_requested_path(tmp_path: Path):
    dest = tmp_path / "lokay.fala-package.toml"
    _materialize_package(
        find_default_package(),
        dest,
        project=tmp_path / "checkout",
        path_id="daemon_cycle",
    )
    text = dest.read_text(encoding="utf-8")
    assert text.count("[[correlation_paths]]") == 1
    assert 'id = "daemon_cycle"' in text
    assert 'id = "closeout_prs"' not in text
    assert 'id = "survey_prs"' not in text
    assert 'id = "factory_pass"' not in text
    assert 'id = "last_pass_moving"' in text
    assert "PLACEHOLDER_PROJECT" not in text
    assert str((tmp_path / "checkout").resolve()) in text
    assert "[runtime.backend]" in text


def test_materialize_unknown_path_fails_closed(tmp_path: Path):
    dest = tmp_path / "lokay.fala-package.toml"
    try:
        _materialize_package(
            find_default_package(),
            dest,
            project=tmp_path / "checkout",
            path_id="not_a_real_path",
        )
    except ValueError as exc:
        assert "unknown Fala correlation path" in str(exc)
        assert not dest.exists()
    else:
        raise AssertionError("expected ValueError")


def test_factory_pass_uses_wrapper_journal():
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "compose"
        / "factory.py"
    ).read_text(encoding="utf-8")
    assert "wrapper_journal_dir" in src
    assert 'Path.home() / ".lokay" / "fala" / "factory"' not in src

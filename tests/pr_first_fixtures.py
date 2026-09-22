"""Offline physical PR-list evidence for detached lifecycle tests."""

from lokay.config import Config, RepoConfig
from lokay.runner import CommandResult


def empty_pr_survey(tmp_path, monkeypatch):
    cfg = Config(
        mode="live", state_path=tmp_path / ".lokay" / "state.jsonl",
        repos=[RepoConfig(name="mikolaj92/lokay", clone_path=tmp_path)],
    )
    monkeypatch.setattr("lokay.config.load_config", lambda *_: cfg)
    monkeypatch.setattr("lokay.gh_prs.survey_pace", lambda *_: None)

    def checked(self, spec, **kwargs):
        assert spec.argv[:3] == ("gh", "pr", "list"), spec.argv
        return CommandResult(spec=spec, executed=True, returncode=0, stdout="[]")

    monkeypatch.setattr("lokay.runner.Runner.run_checked", checked)

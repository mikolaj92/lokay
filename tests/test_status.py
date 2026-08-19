"""DoD status: mill_ready and blockers."""

from pathlib import Path

from lokay.cli import build_parser
from lokay.compose.status import compose_status
from lokay.pass_receipt import write_pass_receipt


def _write_cfg(
    tmp_path: Path,
    *,
    mode: str,
    executor: bool,
    merge: bool,
    k: int = 1,
    repos: tuple[str, ...] = ("mikolaj92/lokay",),
) -> Path:
    cfg_path = tmp_path / "config.yaml"
    repo_yaml = "\n".join(
        f"  - name: {repo}\n    clone_path: {tmp_path / repo.split('/')[-1]}"
        for repo in repos
    )
    cfg_path.write_text(
        f"""
mode: {mode}
repos:
{repo_yaml}
executor:
  enabled: {str(executor).lower()}
  agent: grok
  command: grok
  args: ["{{prompt}}"]
merge:
  enabled: {str(merge).lower()}
  require_checks: true
limits:
  max_issue_to_pr_per_pass: {k}
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    return cfg_path


def test_status_reports_blockers_when_dry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    cfg_path = _write_cfg(tmp_path, mode="dry-run", executor=False, merge=False)
    result = compose_status(config_path=str(cfg_path))
    assert result["mill_ready"] is False
    assert any("mode is not live" in b for b in result["blockers"])
    assert any("executor.enabled" in b for b in result["blockers"])
    assert any("merge.enabled" in b for b in result["blockers"])
    assert "LOKAY_AGENT" not in result["live_env_hint"]
    assert result["merge_enabled"] is False
    assert result["require_checks"] is True
    assert result["require_llm_review"] is True
    assert result["k"] == 1
    assert result["max_issue_to_pr_per_pass"] == 1


def test_require_checks_is_policy_not_hard_blocker(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    cfg_path = _write_cfg(tmp_path, mode="live", executor=True, merge=True)
    result = compose_status(config_path=str(cfg_path))
    assert result["mill_ready"] is True
    assert result["blockers"] == []
    assert any("require_checks" in n for n in result.get("policy_notes") or [])


def test_local_status_skips_survey(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    cfg_path = _write_cfg(tmp_path, mode="live", executor=True, merge=True)

    def boom(*_a, **_k):
        raise AssertionError("full survey must not run on --local")

    monkeypatch.setattr("lokay.compose.status.compose_tick", boom)
    result = compose_status(config_path=str(cfg_path), survey=False)
    assert result["ok"] is True
    assert result["survey"] is False
    assert result["mill_ready"] is True
    assert result["health"] == "local"
    assert result["remaining"] == {"note": "survey_skipped"}
    assert result["idle"] is None
    assert "lease_ok" in result
    assert "lease_reason" in result
    assert result["merge_enabled"] is True
    assert result["require_checks"] is True
    assert result["require_llm_review"] is True
    assert result["k"] == 1


def test_local_status_uses_last_pass_health(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    cfg_path = _write_cfg(tmp_path, mode="live", executor=True, merge=True, k=5)
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    write_pass_receipt(
        {
            "kind": "pass_receipt",
            "health": "repairing",
            "idle": False,
            "merge_enabled": True,
            "max_issue_to_pr_per_pass": 5,
            "remaining": {
                "ready": 1,
                "by_repo": [{"repo": "a/b", "ready": 1, "actionable_open_ai_prs": 0}],
            },
            "human_residuals": {"count": 2},
            "by_repo": [{"repo": "a/b", "ready": 1, "actionable_open_ai_prs": 0}],
        },
        state_path=state,
    )
    monkeypatch.setattr(
        "lokay.compose.status.compose_tick",
        lambda **k: (_ for _ in ()).throw(AssertionError("survey")),
    )
    result = compose_status(config_path=str(cfg_path), survey=False)
    assert result["health"] == "repairing"
    assert result["k"] == 5
    assert result["last_pass"]["health"] == "repairing"
    assert result["by_repo"][0]["repo"] == "a/b"
    assert result["human_residuals"]["count"] == 2


def test_status_surveys_only_lokay_from_mixed_catalog(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    cfg_path = _write_cfg(
        tmp_path,
        mode="live",
        executor=True,
        merge=True,
        repos=("mikolaj92/Temida", "mikolaj92/takt", "mikolaj92/lokay"),
    )
    surveyed: list[str] = []

    def fake_proc(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        surveyed.append(repo)
        if fn.__module__ == "lokay.proc.list_prs":
            return {"ok": True, "prs": []}
        return {"ok": True, "issues": []}

    monkeypatch.setattr("lokay.compose.tick._run", fake_proc)
    monkeypatch.setattr(
        "lokay.compose.status.compose_human_mailbox",
        lambda **_kwargs: {"ok": True, "count": 0, "items": [], "errors": []},
    )
    result = compose_status(config_path=str(cfg_path))

    assert result["ok"] is True
    assert surveyed
    assert set(surveyed) == {"mikolaj92/lokay"}
    assert [row["repo"] for row in result["remaining"]["by_repo"]] == [
        "mikolaj92/lokay"
    ]
    assert result["remaining"]["by_repo"][0]["survey_error"] is False


def test_status_product_only_catalog_skips_survey(tmp_path: Path, monkeypatch):
    cfg_path = _write_cfg(
        tmp_path,
        mode="live",
        executor=True,
        merge=True,
        repos=("mikolaj92/Temida", "mikolaj92/takt"),
    )

    monkeypatch.setattr(
        "lokay.compose.status.compose_tick",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("product survey")),
    )
    result = compose_status(config_path=str(cfg_path))

    assert result["ok"] is True
    assert result["idle"] is True
    assert result["remaining"]["by_repo"] == []


def test_status_survey_exposes_by_repo_and_human(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    cfg_path = _write_cfg(tmp_path, mode="live", executor=True, merge=True, k=4)

    def fake_tick(*, config_path, live=False):
        return {
            "ok": True,
            "idle": False,
            "health": "waiting",
            "remaining": {
                "inbox": 1,
                "ready": 2,
                "open_ai_prs": 1,
                "actionable_open_ai_prs": 1,
                "survey_errors": 0,
                "max_issue_to_pr_per_pass": 4,
                "by_repo": [
                    {
                        "repo": "a/b",
                        "inbox": 1,
                        "ready": 2,
                        "open_ai_prs": 1,
                        "actionable_open_ai_prs": 1,
                        "manual_open_ai_prs": 0,
                        "survey_error": False,
                    }
                ],
            },
            "pass_receipt_path": str(tmp_path / "last-pass.json"),
        }

    monkeypatch.setattr("lokay.compose.status.compose_tick", fake_tick)
    monkeypatch.setattr(
        "lokay.compose.status.compose_human_mailbox",
        lambda **k: {
            "ok": True,
            "count": 1,
            "items": [
                {
                    "kind": "issue",
                    "repo": "a/b",
                    "number": 9,
                    "title": "eyes",
                    "label": "ai:needs-feedback",
                }
            ],
            "errors": [],
            "note": "Human queue is exception reporting only",
        },
    )
    result = compose_status(config_path=str(cfg_path), survey=True)
    assert result["ok"] is True
    assert result["health"] == "waiting"
    assert result["merge_enabled"] is True
    assert result["k"] == 4
    assert result["by_repo"][0]["actionable_open_ai_prs"] == 1
    assert result["human_residuals"]["count"] == 1
    assert result["human_residuals"]["mill_blocked"] is False


def test_local_status_still_fails_when_not_mill_ready(tmp_path: Path, monkeypatch):
    cfg_path = _write_cfg(tmp_path, mode="dry-run", executor=False, merge=False)
    monkeypatch.setattr(
        "lokay.compose.status.compose_tick",
        lambda **k: (_ for _ in ()).throw(AssertionError("survey")),
    )
    result = compose_status(config_path=str(cfg_path), survey=False)
    assert result["ok"] is False
    assert result["survey"] is False
    assert result["mill_ready"] is False


def test_cli_status_local_flag_wiring():
    parser = build_parser()
    args = parser.parse_args(["status", "--local", "--config", "c.yaml"])
    assert args.local is True
    args_skip = parser.parse_args(["status", "--skip-survey"])
    assert args_skip.local is True


def test_cli_status_human_flag_wiring():
    parser = build_parser()
    args = parser.parse_args(["status", "--human", "--config", "c.yaml"])
    assert args.human is True


def test_status_human_mailbox_not_mill_brake(tmp_path: Path, monkeypatch):
    cfg_path = _write_cfg(tmp_path, mode="live", executor=True, merge=True)

    def fake_mailbox(*, config_path, live=True):
        return {
            "ok": True,
            "kind": "human_mailbox",
            "mill_blocked": False,
            "count": 2,
            "items": [
                {
                    "kind": "issue",
                    "repo": "a/b",
                    "number": 1,
                    "title": "needs eyes",
                    "label": "ai:needs-feedback",
                },
                {
                    "kind": "pr",
                    "repo": "a/b",
                    "number": 2,
                    "title": "review me",
                    "label": "ai:needs-review",
                },
            ],
            "note": "Human queue is exception reporting only",
            "errors": [],
        }

    monkeypatch.setattr(
        "lokay.compose.status.compose_human_mailbox",
        fake_mailbox,
    )
    result = compose_status(config_path=str(cfg_path), human=True)
    assert result["ok"] is True
    assert result["mill_blocked"] is False
    assert result["count"] == 2
    assert "exception" in (result.get("note") or "").lower()


def test_mill_daemon_does_not_override_configured_executor_metadata():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "lokay-mill-daemon.sh").read_text(encoding="utf-8")
    assert 'export LOKAY_AGENT=' not in script
    assert 'LOKAY_AGENT:-grok' not in script

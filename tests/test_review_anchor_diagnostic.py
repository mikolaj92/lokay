import json

import pytest

from lokay.proc.pr_review_plugin import PluginFailure, _decode_plugin_envelope


def test_host_retains_only_verified_anchor_metadata():
    request = {"head_sha": "b" * 40, "diff_paths": [{"path": "src/demo.py"}],
               "changed_ranges": {"src/demo.py": [[12, 13]]}}
    diagnostic = {"reason": "anchor_outside_changed_lines", "comment_index": 1,
                  "path": "src/demo.py", "start_line": 12, "end_line": 14,
                  "changed_intervals": [[1, 100]], "intervals_truncated": False,
                  "thinking": "private", "content": "secret"}
    envelope = {"ok": False, "error": {"code": "ocr_contract_incomplete",
                "detail": "finding anchor is not within changed lines", "diagnostic": diagnostic}}
    with pytest.raises(PluginFailure) as caught:
        _decode_plugin_envelope(json.dumps(envelope).encode(), 1, request=request)
    actual = caught.value.diagnostic
    assert actual["changed_intervals"] == [[12, 13]]
    assert actual["head_sha"] == "b" * 40
    assert actual["path"] == "src/demo.py"
    assert "thinking" not in actual and "content" not in actual


@pytest.mark.parametrize("field,value", [("path", "../secret"), ("path", "/tmp/secret"),
    ("path", "src/other.py"), ("start_line", True), ("end_line", -1),
    ("comment_index", 0), ("end_line", 2147483648)])
def test_host_discards_malformed_anchor_metadata(field, value):
    from lokay.proc.pr_review_plugin import sanitize_anchor_diagnostic
    request = {"head_sha": "b" * 40, "diff_paths": [{"path": "src/demo.py"}],
               "changed_ranges": {"src/demo.py": [[12, 13]]}}
    raw = {"reason": "anchor_outside_changed_lines", "comment_index": 1,
           "path": "src/demo.py", "start_line": 12, "end_line": 14}
    raw[field] = value
    assert sanitize_anchor_diagnostic(raw, request) is None


def test_rejection_archive_retains_verified_anchor_without_vendor_warnings(tmp_path):
    from lokay.config import Config
    from lokay.proc.pr_review_artifacts import persist_rejected_vendor

    evidence = {"head_sha": "b" * 40, "diff_paths": [{"path": "src/demo.py"}],
                "changed_ranges": {"src/demo.py": [[12, 13]]}}
    diagnostic = {"reason": "anchor_outside_changed_lines", "comment_index": 1,
                  "path": "src/demo.py", "start_line": 12, "end_line": 14,
                  "thinking": "private", "changed_intervals": [[1, 100]]}
    cfg = Config(pr_review_artifacts_dir=tmp_path)
    archive = persist_rejected_vendor(cfg=cfg, repo="acme/demo", pr=84, evidence=evidence,
                                      reason="ocr_contract_incomplete", diagnostic=diagnostic)
    assert archive["ok"] is True
    from pathlib import Path
    payload = json.loads(Path(archive["path"]).read_text())
    assert payload["diagnostic"]["changed_intervals"] == [[12, 13]]
    assert "thinking" not in json.dumps(payload)


@pytest.mark.parametrize("archive_fails", [False, True])
def test_review_agent_archives_anchor_failure_without_warnings(tmp_path, monkeypatch, archive_fails):
    from pathlib import Path
    from lokay.config import Config
    from lokay.proc import run_pr_review_agent as agent
    from lokay import pr_review_io

    cfg = Config(pr_review_artifacts_dir=tmp_path)
    evidence = {"head_sha": "b" * 40, "task": {}, "diff_paths": [{"path": "src/demo.py"}],
                "changed_ranges": {"src/demo.py": [[12, 13]]}}
    diagnostic = {"reason": "anchor_outside_changed_lines", "comment_index": 1,
                  "path": "src/demo.py", "start_line": 12, "end_line": 14}
    calls = []
    monkeypatch.setattr(agent, "load_config", lambda path: cfg)
    monkeypatch.setattr(pr_review_io, "revalidate_pr_identity", lambda *args, **kwargs: {})
    def reject(*args):
        calls.append(1)
        raise PluginFailure("ocr_contract_incomplete: finding anchor is not within changed lines",
                            diagnostic=diagnostic)
    monkeypatch.setattr(agent, "invoke_plugin", reject)
    if archive_fails:
        from lokay.proc import pr_review_artifacts
        monkeypatch.setattr(pr_review_artifacts, "persist_rejected_vendor",
                            lambda **kwargs: {"ok": False, "reason": "artifact_write_failed"})
    result = agent.run_review_agent(config_path=None, repo="acme/demo", pr=84,
                                    evidence=evidence, live=True)
    assert result["route"] == "fail_closed"
    assert calls == [1]
    if archive_fails:
        return
    artifacts = list(Path(tmp_path).glob("rejections/acme__demo/84/*.json"))
    assert len(artifacts) == 1
    assert json.loads(artifacts[0].read_text())["diagnostic"]["end_line"] == 14

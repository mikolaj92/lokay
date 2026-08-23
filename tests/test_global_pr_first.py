"""Per-repo PR-first: actionable AI PRs freeze only their own repository."""

from __future__ import annotations

from lokay.passkit import io as pass_io
from lokay.compose import tick


def _run_pr_survey(module, pass_dir):
    from lokay.passkit.support import is_manual_pr

    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    by = {}
    actions = list(working.get("actions") or [])
    for repo in begin.get("repos") or []:
        out = module._run(module.p_list_prs.main, ["--repo", repo])
        rows = list(out.get("prs") or []) if out.get("ok") else []
        by[repo] = rows
        actions.append({"step": "list_prs", "repo": repo, **out})
    working.update(
        actions=actions,
        prs_by_repo=by,
        remaining_prs=sum(len(v) for v in by.values()),
        actionable_prs=sum(not is_manual_pr(x) for v in by.values() for x in v),
        manual_prs=sum(is_manual_pr(x) for v in by.values() for x in v),
        pr_survey_failed=[],
    )
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {"ok": True}


def _run_closeout(module, pass_dir):
    from lokay.passkit.support import is_manual_pr

    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    prs = dict(working.get("prs_by_repo") or {})
    actions = list(working.get("actions") or [])
    merged = []
    needs = pending = green = limbo = progress = 0
    for repo, rows in prs.items():
        kept = []
        for pr in rows:
            if is_manual_pr(pr):
                kept.append(pr)
                continue
            checks = module._run(
                module.p_checks.main, ["--repo", repo, "--pr", str(pr["number"])]
            )
            status = str(checks.get("status") or "")
            if status == "pending":
                pending += 1
                kept.append(pr)
                continue
            if status == "failed":
                needs += 1
                module.compose_pr_repair(
                    config_path=None,
                    repo=repo,
                    pr_number=pr["number"],
                    branch=pr.get("head_ref", ""),
                    live=True,
                )
                kept.append(pr)
                continue
            tri = module.compose_pr_triage(
                config_path=None,
                repo=repo,
                pr_number=pr["number"],
                branch=pr.get("head_ref", ""),
                live=True,
            )
            actions.append({"step": "pr_triage", "pr": pr["number"], **tri})
            if tri.get("skipped"):
                if tri.get("repairable"):
                    needs += 1
                    rep = module.compose_pr_repair(
                        config_path=None,
                        repo=repo,
                        pr_number=pr["number"],
                        branch=pr.get("head_ref", ""),
                        live=True,
                        review=tri.get("review") or {},
                    )
                    actions.append(
                        {"step": "pr_review_repair", "pr": pr["number"], **rep}
                    )
                else:
                    limbo += 1
                kept.append(pr)
            else:
                progress += 1
                merged.append(repo)
        prs[repo] = kept
    working.update(
        actions=actions,
        prs_by_repo=prs,
        remaining_prs=sum(len(v) for v in prs.values()),
        actionable_prs=sum(not is_manual_pr(p) for v in prs.values() for p in v),
        manual_prs=sum(is_manual_pr(p) for v in prs.values() for p in v),
        needs_repair=needs,
        pending_checks=pending,
        mergeable_green=green,
        review_limbo=limbo,
        merged_this_pass=merged,
        progress=int(working.get("progress") or 0) + progress,
    )
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {"ok": True}


def _run_inbox(module, pass_dir):
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    by = {}
    issues = {}
    for repo in begin.get("repos") or []:
        try:
            out = module._run(module.p_list_inbox.main, ["--repo", repo])
        except AssertionError:
            out = {"ok": True, "issues": []}
        rows = list(out.get("issues") or []) if out.get("ok") else []
        by[repo] = len(rows)
        issues[repo] = rows
    working.update(
        inbox_by_repo=by,
        inbox_issues_by_repo=issues,
        remaining_inbox=sum(by.values()),
        inbox_survey_failed=[],
    )
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {"ok": True}


def _run_selection(pass_dir):
    from lokay.proc.prepare_implementation_selection import prepare
    from lokay.proc.select_implementation_repo_slot import select
    from lokay.proc.inspect_implementation_eligibility import inspect
    from lokay.proc.reduce_implementation_selection import reduce_state
    from lokay.proc.persist_implementation_selection import persist

    prepared = prepare(pass_dir=pass_dir, slot_count=30)
    results = []
    for slot in range(1, 31):
        selected = select(prepared, slot=slot)
        results.append(
            inspect(pass_dir=pass_dir, prepared=prepared, selected=selected)
            if selected.get("route") == "repo"
            else selected
        )
    reduced = reduce_state(
        prepared=prepared,
        results=results,
        working=pass_io.read_json(pass_io.working_path(pass_dir)),
    )
    return persist(pass_dir=pass_dir, reduced=reduced)


def _run_plan(pass_dir):
    from lokay.proc.prepare_pass_plan import prepare
    from lokay.proc.select_plan_repo_slot import select
    from lokay.proc.build_repo_plan_fragment import build
    from lokay.proc.reduce_pass_plan import reduce_state
    from lokay.proc.persist_pass_plan import persist

    prepared = prepare(pass_dir=pass_dir, slot_count=30)
    fragments = []
    for slot in range(1, 31):
        selected = select(prepared, slot=slot)
        fragments.append(
            build(pass_dir=pass_dir, prepared=prepared, selected=selected)
            if selected.get("route") == "repo"
            else selected
        )
    reduced = reduce_state(
        prepared=prepared,
        fragments=fragments,
        working=pass_io.read_json(pass_io.working_path(pass_dir)),
    )
    return persist(pass_dir=pass_dir, reduced=reduced)


def _intake_ok():
    return {
        "ok": True,
        "implementable": True,
        "applied": False,
        "decision": {"decision": "ready", "reason": "intake_ok"},
    }


def _config(tmp_path, repos=("a/one", "a/two"), **limit_overrides):
    path = tmp_path / "config.yaml"
    rows = "\n".join(f"  - name: {repo}\n    clone_path: {tmp_path}" for repo in repos)
    limits = {
        "max_triage_per_tick": 0,
        "max_issue_to_pr_per_pass": 1,
        "max_repairs_per_tick": 0,
        **limit_overrides,
    }
    lim_yaml = "\n".join(f"  {k}: {v}" for k, v in limits.items())
    path.write_text(f"""mode: live
repos:
{rows}
executor:
  enabled: true
  command: true
  args: ["{{prompt}}"]
merge:
  enabled: true
  require_checks: false
limits:
{lim_yaml}
worktrees:
  root: {tmp_path / 'wt'}
state:
  path: {tmp_path / 'state.jsonl'}
""")
    return str(path)


def _pr(number=1, labels=None):
    pr = {
        "number": number,
        "head_ref": f"ai/fix/{number}-x",
        "mergeable": "MERGEABLE",
    }
    if labels is not None:
        pr["labels"] = labels
    return pr


def test_actionable_pr_blocks_same_repo_intake_and_triage(tmp_path, monkeypatch):
    monkeypatch.setattr(
        tick,
        "run_survey_ready",
        lambda **kwargs: (
            pass_io.write_json(
                pass_io.survey_path(kwargs["pass_dir"]),
                pass_io.read_json(pass_io.working_path(kwargs["pass_dir"])),
            )
            and {
                "ok": True,
                "pass_dir": kwargs["pass_dir"],
                "remaining_ready": 0,
                "survey_errors": 0,
            }
        ),
    )
    config = _config(tmp_path, repos=("a/one",), max_triage_per_tick=5)
    triage = []

    def fake_run(fn, argv):
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": [_pr()]}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": [{"number": 3, "repo": "a/one"}]}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [{"number": 2, "repo": "a/one", "title": "next"}],
                "labels": ["work:ready", "ai:ready"],
            }
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "pending"}
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick, "run_path", lambda **kw: triage.append(kw) or {"ok": True}
    )
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **_: (_ for _ in ()).throw(AssertionError("intake ran")),
    )
    monkeypatch.setattr(tick, "run_queue_conflict", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(tick, "run_resolve_conflicts", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(
        tick,
        "run_select_implement",
        lambda **kwargs: _run_selection(kwargs["pass_dir"]),
    )
    monkeypatch.setattr(
        tick, "run_plan_pass", lambda **kwargs: _run_plan(kwargs["pass_dir"])
    )
    monkeypatch.setattr(tick, "run_refresh_occupancy", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(
        tick, "run_survey_inbox", lambda **kwargs: _run_inbox(tick, kwargs["pass_dir"])
    )
    monkeypatch.setattr(
        tick,
        "run_closeout_prs",
        lambda **kwargs: _run_closeout(tick, kwargs["pass_dir"]),
    )
    monkeypatch.setattr(
        tick,
        "run_survey_prs",
        lambda **kwargs: _run_pr_survey(tick, kwargs["pass_dir"]),
    )
    result = tick.compose_tick(config_path=config, live=True)

    assert triage == []
    assert any(
        a.get("step") == "skip_inbox_triage_repo_backpressure"
        for a in result["actions"]
    )
    assert any(a.get("step") == "skip_ready_open_ai_pr" for a in result["actions"])
    assert result["remaining"]["intake_skip_reason"] is None


def test_merge_then_same_repo_does_not_start_sibling(tmp_path, monkeypatch):
    monkeypatch.setattr(
        tick,
        "run_survey_ready",
        lambda **kwargs: (
            pass_io.write_json(
                pass_io.survey_path(kwargs["pass_dir"]),
                pass_io.read_json(pass_io.working_path(kwargs["pass_dir"])),
            )
            and {
                "ok": True,
                "pass_dir": kwargs["pass_dir"],
                "remaining_ready": 0,
                "survey_errors": 0,
            }
        ),
    )
    """Just-merged repo stays occupied this pass — do not publish #288 from stale main."""
    config = _config(tmp_path, repos=("a/one",), max_issue_to_pr_per_pass=1)
    listed = {"prs": 0}

    def fake_run(fn, argv):
        if fn is tick.p_list_prs.main:
            listed["prs"] += 1
            # Start-of-pass survey sees the mergeable PR. Refresh after merge
            # sees GitHub without it — occupancy, not the stale PR list, must brake.
            if listed["prs"] == 1:
                return {"ok": True, "prs": [_pr(labels=[])]}
            return {"ok": True, "prs": []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [{"number": 2, "repo": "a/one", "title": "sibling"}],
                "labels": ["work:ready", "ai:ready"],
            }
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "none", "merge_ok": True}
        if fn is tick.p_intake.main:
            return _intake_ok()
        raise AssertionError(fn)

    intake = []
    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick, "compose_pr_triage", lambda **_: {"ok": True, "merged": True}
    )
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: intake.append(kw)
        or {"ok": True, "pr": 2, "branch": "ai/fix/2-next"},
    )
    monkeypatch.setattr(tick, "run_queue_conflict", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(tick, "run_resolve_conflicts", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(
        tick,
        "run_select_implement",
        lambda **kwargs: _run_selection(kwargs["pass_dir"]),
    )
    monkeypatch.setattr(
        tick, "run_plan_pass", lambda **kwargs: _run_plan(kwargs["pass_dir"])
    )
    monkeypatch.setattr(tick, "run_refresh_occupancy", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(
        tick, "run_survey_inbox", lambda **kwargs: _run_inbox(tick, kwargs["pass_dir"])
    )
    monkeypatch.setattr(
        tick,
        "run_closeout_prs",
        lambda **kwargs: _run_closeout(tick, kwargs["pass_dir"]),
    )
    monkeypatch.setattr(
        tick,
        "run_survey_prs",
        lambda **kwargs: _run_pr_survey(tick, kwargs["pass_dir"]),
    )
    result = tick.compose_tick(config_path=config, live=True)

    assert intake == []
    actions = result.get("actions") or []
    assert any(row.get("step") == "skip_ready_repo_occupied" for row in actions)


def test_malformed_labels_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        tick,
        "run_survey_ready",
        lambda **kwargs: (
            pass_io.write_json(
                pass_io.survey_path(kwargs["pass_dir"]),
                pass_io.read_json(pass_io.working_path(kwargs["pass_dir"])),
            )
            and {
                "ok": True,
                "pass_dir": kwargs["pass_dir"],
                "remaining_ready": 0,
                "survey_errors": 0,
            }
        ),
    )
    config = _config(tmp_path)

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {
                "ok": True,
                "prs": (
                    [_pr(labels={"name": "ai:needs-review"})] if repo == "a/one" else []
                ),
            }
        if fn in {tick.p_list_inbox.main, tick.p_list_issues.main}:
            return {"ok": True, "issues": []}
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "pending"}
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(tick, "run_queue_conflict", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(tick, "run_resolve_conflicts", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(
        tick,
        "run_select_implement",
        lambda **kwargs: _run_selection(kwargs["pass_dir"]),
    )
    monkeypatch.setattr(
        tick, "run_plan_pass", lambda **kwargs: _run_plan(kwargs["pass_dir"])
    )
    monkeypatch.setattr(tick, "run_refresh_occupancy", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(
        tick, "run_survey_inbox", lambda **kwargs: _run_inbox(tick, kwargs["pass_dir"])
    )
    monkeypatch.setattr(
        tick,
        "run_closeout_prs",
        lambda **kwargs: _run_closeout(tick, kwargs["pass_dir"]),
    )
    monkeypatch.setattr(
        tick,
        "run_survey_prs",
        lambda **kwargs: _run_pr_survey(tick, kwargs["pass_dir"]),
    )
    result = tick.compose_tick(config_path=config, live=True)
    assert result["remaining"]["actionable_open_ai_prs"] == 1
    assert result["remaining"]["manual_open_ai_prs"] == 0


def test_only_parked_needs_review_is_waiting_not_stall(tmp_path, monkeypatch):
    monkeypatch.setattr(
        tick,
        "run_survey_ready",
        lambda **kwargs: (
            pass_io.write_json(
                pass_io.survey_path(kwargs["pass_dir"]),
                pass_io.read_json(pass_io.working_path(kwargs["pass_dir"])),
            )
            and {
                "ok": True,
                "pass_dir": kwargs["pass_dir"],
                "remaining_ready": 0,
                "survey_errors": 0,
            }
        ),
    )
    """No ready work + parked mailbox PR → waiting, never stall/recovery bait."""
    config = _config(tmp_path, repos=("a/one",))

    def fake_run(fn, argv):
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": [_pr(labels=["ai:needs-review"])]}
        if fn in {tick.p_list_inbox.main, tick.p_list_issues.main}:
            return {"ok": True, "issues": []}
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **_: (_ for _ in ()).throw(AssertionError("intake ran")),
    )
    monkeypatch.setattr(tick, "run_queue_conflict", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(tick, "run_resolve_conflicts", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(
        tick,
        "run_select_implement",
        lambda **kwargs: _run_selection(kwargs["pass_dir"]),
    )
    monkeypatch.setattr(
        tick, "run_plan_pass", lambda **kwargs: _run_plan(kwargs["pass_dir"])
    )
    monkeypatch.setattr(tick, "run_refresh_occupancy", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(
        tick, "run_survey_inbox", lambda **kwargs: _run_inbox(tick, kwargs["pass_dir"])
    )
    monkeypatch.setattr(
        tick,
        "run_closeout_prs",
        lambda **kwargs: _run_closeout(tick, kwargs["pass_dir"]),
    )
    monkeypatch.setattr(
        tick,
        "run_survey_prs",
        lambda **kwargs: _run_pr_survey(tick, kwargs["pass_dir"]),
    )
    result = tick.compose_tick(config_path=config, live=True)
    assert result["health"] == "waiting"
    assert result["ok"] is True
    assert result["idle"] is False
    assert result["remaining"]["manual_open_ai_prs"] == 1
    assert result["remaining"]["actionable_open_ai_prs"] == 0
    assert result["remaining"]["ready"] == 0

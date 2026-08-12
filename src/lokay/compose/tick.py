"""Thin bridge: one factory pass via in-process atom spine (order mirrors Fala).

Production mill invokes parent Fala ``factory_pass`` (``compose_factory_pass`` →
``run_path``). This module sequences the same atoms in-process for ``lokay-tick``
and unit tests — it does **not** own fleet scheduling policy. Policy lives in
``lokay-survey-repos``, ``lokay-plan-pass``, ``lokay-select-implement``, and the
dispatch atoms; order lives in ``fala/lokay.fala-package.toml``.
"""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit
from lokay.proc._common import add_config_live, load_cfg  # noqa: F401
from lokay.proc.compute_health import run_compute_health
from lokay.proc.dispatch_closeout import run_dispatch_closeout
from lokay.proc.dispatch_implement import run_dispatch_implement
from lokay.proc.dispatch_triage import run_dispatch_triage
from lokay.proc.factory_begin import run_factory_begin
from lokay.proc.plan_pass import run_plan_pass
from lokay.proc.record_pass import run_record_pass
from lokay.proc.select_implement import run_select_implement
from lokay.proc.survey_repos import run_survey_repos
from lokay.passkit import io as pass_io

# Re-exports for tests that still patch tick.* symbols while the spine migrates.
from lokay.passkit.health import health_payload as _health_payload  # noqa: F401
from lokay.passkit.support import is_manual_pr as _is_manual_pr  # noqa: F401
from lokay.passkit.support import run_proc as _run  # noqa: F401
from lokay.compose.issue_to_pr import compose_issue_to_pr  # noqa: F401
from lokay.compose.pr_repair import compose_pr_repair  # noqa: F401
from lokay.compose.pr_triage import compose_pr_triage  # noqa: F401
from lokay.graph_run import run_path  # noqa: F401
from lokay.preflight import health_lease_status, run_preflight  # noqa: F401
from lokay.proc import intake_issue as p_intake  # noqa: F401
from lokay.proc import label_issue as p_label  # noqa: F401
from lokay.proc import list_inbox as p_list_inbox  # noqa: F401
from lokay.proc import list_issues as p_list_issues  # noqa: F401
from lokay.proc import list_prs as p_list_prs  # noqa: F401
from lokay.proc import pr_checks as p_checks  # noqa: F401
from lokay.proc import pr_close as p_pr_close  # noqa: F401
from lokay.proc import select_issue as p_select  # noqa: F401


def _bind_test_patches() -> None:
    """Keep legacy ``tick.*`` monkeypatches working while atoms own the work.

    Unit tests historically patched ``compose.tick`` symbols. Atoms import their
    collaborators by module attribute; rebind those attributes to this module's
    names so patches on ``tick._run`` / ``tick.run_path`` / composers still apply.
    """
    import lokay.proc.compute_health as compute_health
    import lokay.proc.dispatch_closeout as dispatch_closeout
    import lokay.proc.dispatch_implement as dispatch_implement
    import lokay.proc.dispatch_triage as dispatch_triage
    import lokay.proc.factory_begin as factory_begin
    import lokay.proc.plan_pass as plan_pass
    import lokay.proc.survey_repos as survey_repos

    factory_begin.run_preflight = run_preflight
    factory_begin.health_lease_status = health_lease_status
    factory_begin.load_cfg = load_cfg
    survey_repos.run_proc = _run
    survey_repos.is_manual_pr = _is_manual_pr
    plan_pass.is_manual_pr = _is_manual_pr
    dispatch_closeout.run_proc = _run
    dispatch_closeout.compose_pr_repair = compose_pr_repair
    dispatch_closeout.compose_pr_triage = compose_pr_triage
    dispatch_closeout.is_manual_pr = _is_manual_pr
    dispatch_implement.run_proc = _run
    dispatch_implement.compose_issue_to_pr = compose_issue_to_pr
    dispatch_triage.run_path = run_path
    compute_health.is_manual_pr = _is_manual_pr
    compute_health.health_payload = _health_payload


def compose_tick(*, config_path: str | None, live: bool) -> dict[str, Any]:
    """Run the factory-pass atom spine in conduction order (in-process)."""
    _bind_test_patches()
    begin = run_factory_begin(config_path=config_path, live=live)
    if not begin.get("ok"):
        return begin
    if begin.get("offline"):
        return begin
    pass_dir = str(begin["pass_dir"])
    run_survey_repos(pass_dir=pass_dir, config_path=config_path, live=live)
    run_plan_pass(pass_dir=pass_dir)
    run_dispatch_triage(pass_dir=pass_dir, config_path=config_path, live=live)
    run_dispatch_closeout(pass_dir=pass_dir, config_path=config_path, live=live)
    run_select_implement(pass_dir=pass_dir)
    run_dispatch_implement(pass_dir=pass_dir, config_path=config_path, live=live)
    run_compute_health(pass_dir=pass_dir)
    recorded = run_record_pass(pass_dir=pass_dir)
    tick = recorded.get("tick")
    if isinstance(tick, dict):
        return tick
    # Fail closed if record_pass did not materialize a tick envelope.
    return pass_io.read_json(pass_io.tick_path(pass_dir))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-tick")
    add_config_live(p)
    args = p.parse_args(argv)
    return emit_exit(compose_tick(config_path=args.config, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())

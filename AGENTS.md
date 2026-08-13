# Lokay agent notes

## Composition (non-negotiable)

- Prefer small Unix-style modules/processes; compose them. No fat god-files.
- Multi-step flows: compose with Fala when the work is Python/Mojo process
  orchestration. Multiple Fala runtimes OK.
- Domain engines stay separate; Fala orchestrates.
- Nested Fala OK.

## Design law

**Unix small programs + Fala graph for order + real agent only.**

- See `docs/UNIX.md`, `docs/GRAPH.md`, `docs/WORKING.md`, **`docs/AUTONOMY.md`**, **`docs/NO_STUBS.md`**, **`docs/HTMX.md`**, **`docs/ALPINE.md`**, **`docs/PLATFORM_UI.md`**.
- New capability → `src/lokay/proc/` + `project.scripts`.
- New ordering → `fala/lokay.fala-package.toml` (conduction).
- **Order lives in Fala.** Fleet pass spine is `factory_pass` atoms
  (`host_ff → factory_begin → survey_prs → survey_inbox → survey_ready → plan_pass →
  dispatch_triage → resolve_conflicts → closeout_prs → select_implement →
  queue_conflict → dispatch_implement → compute_health → record_pass`), not a
  fat `compose/tick.py`.
- **Serial by design.** Default `limits.max_issue_to_pr_per_pass` is **1**
  (ticket after ticket). K is an optional pass budget — not concurrent
  worktrees / Pi / tmux. `queue_conflict` is queue hygiene, not a parallel
  scheduler.
- **Trust intentional issues.** Owner / configured-assignee tickets are
  purposeful; no new human-approval gates in the pass spine. Intake CLOSE only
  for clear obsolete / wrong-shape / superseded. Human writes → mill delivers.
- Do **not** grow `compose/*` with GitHub/git/agent / fleet-scheduling logic
  beyond CLI wiring + `graph_run.run_path`.
- JSON on stdout (`envelope.ok` / `envelope.err`).

## Hard bans

- **No** `fake` / `stub` / `mock` / `noop` agent.
- **No** canary-only “fixes” (`LOKAY_CANARY.md` style).
- **No** bare `python3` for product CLI — use **`uv run`**.
- **No** Hermes Kanban as execution ledger.
- **No** re-implementing `factory_pass` order inside Python composers.
- **No** new human-approval / “distrust every ticket” gates in the pass spine.
- **No** hidden SPA / JSON+client-render chrome — server HTML fragments if UI exists (`docs/HTMX.md`).
- **No** app-wide Alpine store / server-state mirrors — local UI only (`docs/ALPINE.md`).
- **No** CDN forks for Basecoat/HTMX/Alpine — product_shell + `/static/platform` if auth UI exists (`docs/PLATFORM_UI.md`).

## Stack

- Executor: **Pi** (`lokay-run-agent`; `executor.command: pi`, model `omniroute/pi`).
- Scope: `repos.mikolaj92.yaml` (managed repos).
- Continuous mill: LaunchAgent `ai.mikolaj.lokay-mill` → `scripts/lokay-mill-daemon.sh`.

## Verify

```bash
uv run pytest -q
uv run lokay validate --config config.yaml
uv run lokay-repos --config config.yaml
uv run lokay status --config config.yaml
```

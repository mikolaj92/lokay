# Lokay agent notes

## Composition (non-negotiable)

- Prefer small Unix-style modules/processes; compose them. No fat god-files.
- Multi-step flows: compose with Fala when the work is Python/Mojo process
  orchestration. Multiple Fala runtimes OK.
- Domain engines stay separate; Fala orchestrates.
- Nested Fala OK.

## State-machine-first (non-negotiable)

- Lokay is a state machine with explicit side effects.
- Before changing routing, update and review the Mermaid state machine in `README.md`.
- Only after the diagram is coherent may the transition be implemented in Fala.
- The README path table and authored Fala paths must stay synchronized.
- Do not use GitHub Actions. Verification and product execution are local.

## Design law

**Product = Fala graph(s).** Unix atoms are replaceable blocks. Coding harness is not the product.

- See **`docs/PROCESS.md`**, `docs/UNIX.md`, `docs/GRAPH.md`, `docs/WORKING.md`, **`docs/AUTONOMY.md`**, **`docs/NO_STUBS.md`**, **`docs/HTMX.md`**, **`docs/ALPINE.md`**, **`docs/PLATFORM_UI.md`**.
- New capability → `src/lokay/proc/` + `project.scripts`.
- New ordering → `fala/lokay.fala-package.toml` (conduction).
- **Order lives in Fala.** Fleet pass spine is `factory_pass` atoms
  (`classify_factory_idle → host_ff → factory_begin_host_gate → factory_begin →
  select_implement → queue_conflict → dispatch_implement → compute_health →
  compact_state → record_pass →
  survey_prs → survey_inbox → survey_ready → ready_hygiene → plan_pass →
  dispatch_triage → resolve_conflicts → closeout_prs → reap_stale_implementing →
  reap_over_budget → refresh_occupancy → reap_stale_worktrees →
  record_factory_idle → factory_pass_terminal`).
  Idle TTL is the first authored atom; compose never skips `run_path`. One pass
  is oil XOR product (product wins). Not a fat `compose/tick.py`.
- Graph may **return** across passes (repair / re-ready / re-survey). Do not
  flatten the mill to one-way issue→done.
- **Serial by design.** Default `limits.max_issue_to_pr_per_pass` is **1**
  (ticket after ticket). K is an optional pass budget — not concurrent
  worktrees / harness / tmux. `queue_conflict` is queue hygiene, not a parallel
  scheduler.
- Coding slot is `executor.command` / `args` (any real worker). Named harnesses
  in examples are illustration, not a dependency.
- **Trust intentional issues.** An open issue is the work. `work:ready` /
  `ai:ready` are optional ledger traces, not the queue. Owner / configured-assignee
  tickets are purposeful; no new human-approval gates in the pass spine. Intake
  CLOSE only for clear obsolete / wrong-shape / superseded / foreign essence
  objections. Others may report hangs or “does not work as described”. They may
  not object to what Lokay *is*. Human writes → mill delivers.
- **One Definition of Done:** quality code merged to `main`. Agent-ok, plan-only,
  `health=progress`, and green tests are not Done. Fast scrap and machines-for-
  machines are worthless. See `docs/WORKING.md`.
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

- Coding slot: `lokay-run-agent` via `executor.command` / `executor.args` (any real harness; current example is `pi` + `omniroute/pi`). Swap is config, not a product change. See `docs/PROCESS.md`.
- Scope: `repos.mikolaj92.yaml` (managed repos).
- Continuous mill: LaunchAgent `ai.mikolaj.lokay-mill` → `scripts/lokay-mill-daemon.sh`.

## Verify

```bash
uv run pytest -q
uv run lokay validate --config config.yaml
uv run lokay-repos --config config.yaml
uv run lokay status --config config.yaml
```

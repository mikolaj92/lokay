# Unix process model (binding)

Lokay is a **pipeline of small programs**, not a monolith.

## Rules

1. **One process = one job.** List issues. Make a branch name. Add a worktree. Run the configured coding executor. Push. Open a PR. Check CI. Merge. Nothing else.
2. **Small files.** Prefer a new module under `src/lokay/proc/` over growing an existing one past ~100 lines of real logic.
3. **Compose, don’t absorb.** Higher-level flows only **call** atomic processes or Fala graphs. They must not reimplement GitHub/git/the coding harness.
4. **Text interfaces.** Each process speaks **JSON on stdout** (one object). Errors: non-zero exit + JSON `{"ok":false,"error":...}` when practical.
5. **Dry-run is explicit non-mutation**, not a fake agent. Use `mode: dry-run` or omit `--live`.
6. **No hidden side channels.** Data flows via CLI args, stdin JSON, or Fala conduction — not Hermes Kanban.
7. **Order is a Fala graph** (or atom pipeline that mirrors it). See `docs/GRAPH.md`.
8. **Always `uv`.** Prefer `uv run lokay …` / `uv run --project …`; do not call bare `python3` for product flows.
9. **No stubs.** See [`NO_STUBS.md`](NO_STUBS.md).
10. **Hypermedia UI (if any):** server owns state, HTML fragments, no SPA. See [`HTMX.md`](HTMX.md).
11. **Alpine (if any):** local UI state only (toggles/menus/disclosure); no app-wide store. See [`ALPINE.md`](ALPINE.md).
12. **Platform stack (if any auth/chrome UI):** `product_shell` + same-origin `/static/platform` Basecoat/HTMX/Alpine; COMPAT tags. See [`PLATFORM_UI.md`](PLATFORM_UI.md).

## Atomic CLI map

| Program | Job |
| --- | --- |
| `lokay-list-inbox` | undecided open issues |
| `lokay-list-issues` | `ai:ready` issues |
| `lokay-triage-issue` | apply triage decision (ready \| split \| rare needs-feedback \| OOS) |
| `lokay-intake-check` | one deterministic intake check (JSON) |
| `lokay-intake-issue` | aggregate intake → CLOSE \| READY \| SPLIT \| NEEDS_HUMAN |
| `lokay-issue-split` | auto-split oversized issue → bounded child issues (gh + rules) |
| `lokay-stage-label` | exclusive issue ledger stage (`ready` / `implementing` / `pr-open` / `ci-waiting` / `repairing` / `clear`) |
| `lokay-select-issue` | pick one issue |
| `lokay-assign-issue` | assign maintainer |
| `lokay-make-branch` | pure branch name |
| `lokay-worktree-add` | git worktree |
| `lokay-plan-issue` | write `.lokay/approach.md` before coding (deterministic evidence) |
| `lokay-run-agent` | **coding harness slot** (binary + args from config only) |
| `lokay-commit-all` | commit if dirty |
| `lokay-test-local` | local pytest gate (skip if no suite; fail-closed if red) |
| `lokay-push` | push (never force) |
| `lokay-pr-create` / `lokay-pr-label` / `lokay-pr-checks` / `lokay-pr-merge` | PR lifecycle |
| `lokay-pr-route` | fail-closed closeout route: wait \| repair \| merge \| skip |
| `lokay-repos` | list managed repos |
| `lokay-factory-begin` | preflight + open pass workspace |
| `lokay-survey-prs` | list open AI PRs (all repos) |
| `lokay-survey-inbox` | list undecided inbox issues |
| `lokay-survey-ready` | list ai:ready; unready covered-by-PR issues |
| `lokay-survey-repos` | thin bridge: survey_prs + inbox + ready |
| `lokay-plan-pass` | select triage / closeout targets (per-repo PR-first) |
| `lokay-dispatch-triage` | run planned inbox triage children |
| `lokay-resolve-conflicts` | close CONFLICTING/DIRTY AI PRs + re-ready |
| `lokay-closeout-pr` | one open AI PR: checks → route → triage/repair/ci-waiting |
| `lokay-closeout-prs` | for-each remaining AI PRs via lokay-closeout-pr |
| `lokay-dispatch-closeout` | thin bridge: resolve_conflicts then closeout_prs |
| `lokay-select-implement` | clean repos eligible for issue_to_pr |
| `lokay-queue-conflict` | contradiction gate (SKIP/CLOSE/READY) before implement |
| `lokay-dispatch-implement` | intake gate + up to K issue_to_pr (serial budget) |
| `lokay-compute-health` | remaining + honest mill health |
| `lokay-record-pass` | write last-pass.json receipt |
| `lokay-factory-pass` / `lokay-factory-tick` | parent Fala `factory_pass` (one mill) |
| `lokay-mill` / `lokay-status` | continuous factory |
| `lokay-wake` | event wake: reason → `issue_triage` / `pr_triage` / bounded `factory_pass` |
| `lokay status --human` | residual human mailbox (exception report; not a mill brake) |

**Factory-pass law:** Fala owns pass order (`factory_pass` conduction). Atoms
above each do one job and return a JSON envelope. `lokay-factory-tick` and
`lokay-factory-pass` both invoke that parent path — not a second in-process
mill. `compose/tick.py` is the hermetic test spine only; do not grow it back
into a multi-repo brain — use new `proc/` atoms + Fala edges.

**Minimize human:** humans author issues; atoms CLOSE / SPLIT / READY+implement.
`ai:needs-feedback` is rare residual — mill keeps other repos moving.

## Anti-patterns

- One 300-line module that does intake + worktree + agent + PR.
- A fat `compose/tick.py` that owns multi-repo scheduling (order belongs in Fala).
- Shared mutable “session” that skips process boundaries.
- Stub/fake coding agents or canary marker files as “success”.
- Hermes Kanban as the ledger for step order.

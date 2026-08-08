# Unix process model (binding)

Lokay is a **pipeline of small programs**, not a monolith.

## Rules

1. **One process = one job.** List issues. Make a branch name. Add a worktree. Run Grok. Push. Open a PR. Check CI. Merge. Nothing else.
2. **Small files.** Prefer a new module under `src/lokay/proc/` over growing an existing one past ~100 lines of real logic.
3. **Compose, don’t absorb.** Higher-level flows only **call** atomic processes or Fala graphs. They must not reimplement GitHub/git/Grok.
4. **Text interfaces.** Each process speaks **JSON on stdout** (one object). Errors: non-zero exit + JSON `{"ok":false,"error":...}` when practical.
5. **Dry-run is explicit non-mutation**, not a fake agent. Use `mode: dry-run` or omit `--live`.
6. **No hidden side channels.** Data flows via CLI args, stdin JSON, or Fala conduction — not Hermes Kanban.
7. **Order is a Fala graph** (or atom pipeline that mirrors it). See `docs/GRAPH.md`.
8. **Always `uv`.** Prefer `uv run lokay …` / `uv run --project …`; do not call bare `python3` for product flows.
9. **No stubs.** See [`NO_STUBS.md`](NO_STUBS.md).
10. **Hypermedia UI (if any):** server owns state, HTML fragments, no SPA. See [`HTMX.md`](HTMX.md).

## Atomic CLI map

| Program | Job |
| --- | --- |
| `lokay-list-inbox` | undecided open issues |
| `lokay-list-issues` | `ai:ready` issues |
| `lokay-triage-issue` | apply triage decision |
| `lokay-select-issue` | pick one issue |
| `lokay-assign-issue` | assign maintainer |
| `lokay-make-branch` | pure branch name |
| `lokay-worktree-add` | git worktree |
| `lokay-run-agent` / `lokay-run-grok` | **real** coding agent |
| `lokay-commit-all` | commit if dirty |
| `lokay-push` | push (never force) |
| `lokay-pr-create` / `lokay-pr-label` / `lokay-pr-checks` / `lokay-pr-merge` | PR lifecycle |
| `lokay-repos` | list managed repos |
| `lokay-mill` / `lokay-status` | continuous factory |

## Anti-patterns

- One 300-line module that does intake + worktree + agent + PR.
- Shared mutable “session” that skips process boundaries.
- Stub/fake coding agents or canary marker files as “success”.
- Hermes Kanban as the ledger for step order.

# Process graph (Fala)

**Order is the product.** Atomic `lokay-*` tools do one job each; Fala declares
which jobs run after which.

## Source of truth

[`fala/lokay.fala-package.toml`](../fala/lokay.fala-package.toml)

### `daemon_cycle` (top-level parent)

```text
recovery_begin
  → recovery_mill
    → recovery_observe
      → recovery_record (persistent 4-of-5 quorum)
        → recovery_incident (skipped until quorum)
          → recovery_run_self_repair (self_repair child Fala)
```

The daemon owns only the singleton lock, health lease and initial carrier
preflight. Fala owns product/recovery order. Every node above is a separate
`lokay-recovery-*` Unix process returning one JSON envelope. A product run that
actually publishes or merges work records no systemic stall fingerprint.

### `factory_pass` (parent)

```text
factory_tick
  ├─→ issue_triage child Fala
  ├─→ pr_repair child Fala
  ├─→ pr_triage child Fala
  └─→ issue_to_pr child Fala
```

The mill invokes this parent path. `factory_tick` owns one bounded multi-repo
pass and starts the smaller paths through `run_path`; the parent journal is
`~/.lokay/fala/factory/state.sqlite`, while child paths use
`~/.lokay/fala/state.sqlite`. This follows Fala's subprocess/separate-journal
parent-child boundary.

### `self_repair` (emergency only)

```text
self_repair_prepare (detached exact origin/main)
  → self_repair_run_agent
    → self_repair_validate (full local suite)
      → self_repair_commit
        → self_repair_push_main (fast-forward only, exact unchanged base)
          → self_repair_activate (exact commit)
            → self_repair_preflight (fresh process)
              → self_repair_close
```

This path is entered only when daemon preflight proves Lokay unhealthy while the
minimal carrier remains healthy. It never creates a branch or PR. The coding
agent can edit only the detached worktree; deterministic atoms alone commit and
push directly to `main`. A successful path always returns `restart_required`;
product work never resumes in the stale daemon process.

### `issue_to_pr`

```text
get_issue
  ├─→ assign_issue
  └─→ make_branch
        └─→ worktree_add
              └─→ run_agent     ← only non-deterministic node
                    └─→ commit_all
                          └─→ push
                                └─→ pr_create
                                      └─→ list_prs
                                            └─→ pr_label
```

### `issue_triage` (inbox → labels)

```text
get_issue
  └─→ triage_issue   ← pure rules → ready candidate | ai:needs-feedback | OOS close
        └─→ intake_issue  ← deterministic intake → CLOSE | READY | NEEDS_HUMAN
```

`ai:ready` is an **outcome** of triage **plus intake**, not the start of the universe.
Intake runs cheap checks first (still-open, superseded/merged PR, playbook/shape
fitness, already-satisfied paths, size/ambiguity). CLOSE posts a short rationale
comment (and drops `ai:ready` when present). NEEDS_HUMAN applies
`ai:needs-feedback`. Inconclusive evidence fails closed to NEEDS_HUMAN (no stub
LLM required). Per-repo PR-first: triage/intake mutations skip a repo that still
has actionable open AI PRs (or a failed PR survey for that repo); other clean
repos continue. Intake still runs inside `issue_triage` whenever triage is
allowed; the mill also re-runs `intake_issue` with `--require-ready` before every
`issue_to_pr`. Up to K `issue_to_pr` child runs per `factory_tick` across
different clean repos (`limits.max_issue_to_pr_per_pass`).

### `pr_repair` (red checks on open ai/fix PR)

```text
pr_checks
  └─→ worktree_add
        └─→ run_agent   ← repair prompt (only non-deterministic node)
              └─→ commit_all
                    └─→ push
```

### `pr_triage` (merge policy → close issue)

```text
pr_checks
  └─→ pr_review    ← structured harness review via run_agent (fail closed)
        └─→ pr_merge     ← skipped when checks not mergeable / review not approve / merge disabled
              └─→ close_issue   ← issue# from ai/fix/N-* branch when known
```

`pr_review` is fail-closed: invalid JSON, `request_changes`, `needs_human`, or `secrets=true` never auto-merges.
Config: `merge.require_llm_review` (default true). Env: `LOKAY_REQUIRE_LLM_REVIEW`.

Tick also handles **merge conflicts** outside this path: `mergeable=CONFLICTING|DIRTY`
→ `lokay-pr-close` + re-label linked issue `ai:ready` so the next pass re-runs
`issue_to_pr` from current main (one stuck conflict must not freeze the mill).

- **conduction** edges = dependencies (Fala will not ready a node until upstream succeeded).
- **run_agent** is the only non-deterministic coding slot — external harness via `executor.command`/`args` (no vendor hardcode). See [`NO_STUBS.md`](NO_STUBS.md).
- Everything else is deterministic (`gh` / `git` / pure functions).

## Run

```bash
# inspect graph
uv run lokay path --describe
# or: uv run lokay-run-path --describe

# execute (Fala host + organ → atoms)
uv run lokay-run-path --config config.yaml --path issue_to_pr \
  --repo mikolaj92/lokay --issue 1
# live mutations:
uv run lokay-run-path --config config.yaml --path issue_to_pr \
  --repo mikolaj92/lokay --issue 1 --live
```

Journal: `~/.lokay/fala/state.sqlite`  
Materialized package: `~/.lokay/fala/lokay.fala-package.toml`  
(`uv run --project <checkout>` filled in for every organ — never bare `python3`)

## Bridge

| Piece | Role |
| --- | --- |
| `fala/lokay.fala-package.toml` | graph |
| `lokay.fala_organ` | one Fala subprocess organ → one atom |
| `lokay.graph_run` | `host_run_package` wrapper |
| `lokay-*` procs | Unix atoms |

Do not put graph order in the coding harness. Do not reintroduce Hermes Kanban as the ledger for step order.

**Runtime note:** Fala is the only workflow composer. Python composers validate the public command contract, invoke
`lokay.graph_run.run_path`, and normalize Fala's terminal per-effector outputs.
`compose_mill` repeats the parent `factory_pass`; it does not invoke child paths
directly. Atomic `lokay-*` processes remain the execution
boundary, but there is no runtime Python fallback graph or engine-selection flag.

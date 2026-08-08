# Process graph (Fala)

**Order is the product.** Atomic `lokay-*` tools do one job each; Fala declares
which jobs run after which.

## Source of truth

[`fala/lokay.fala-package.toml`](../fala/lokay.fala-package.toml)

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
  └─→ triage_issue   ← pure rules → ai:ready | ai:needs-feedback | OOS close
```

`ai:ready` is an **outcome** of triage, not the start of the universe.

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
  └─→ pr_review    ← LLM structured review (non-deterministic; fail closed)
        └─→ pr_merge     ← skipped when checks not mergeable / review not approve / merge disabled
              └─→ close_issue   ← issue# from ai/fix/N-* branch when known
```

`pr_review` is fail-closed: invalid JSON, `request_changes`, `needs_human`, or `secrets=true` never auto-merges.
Config: `merge.require_llm_review` (default true). Env: `LOKAY_REQUIRE_LLM_REVIEW`.

Tick also handles **merge conflicts** outside this path: `mergeable=CONFLICTING|DIRTY`
→ `lokay-pr-close` + re-label linked issue `ai:ready` so the next pass re-runs
`issue_to_pr` from current main (one stuck conflict must not freeze the mill).

- **conduction** edges = dependencies (Fala will not ready a node until upstream succeeded).
- **run_agent** is the only non-deterministic coding slot — **real harness only** (`grok`). See [`NO_STUBS.md`](NO_STUBS.md).
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

**Runtime note:** composers execute the same step order as **Unix atomics** by
default (`lokay.compose.*`). Set `LOKAY_USE_FALA=1` to drive steps via the Fala
host + `lokay.fala_organ` instead.

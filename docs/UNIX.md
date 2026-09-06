# Unix process model (binding)

Lokay is a composition of small programs, not a monolith.

## Rules

1. **One process = one job.** List issues, name a branch, add a worktree, run a worker, publish, check or merge. Separate jobs have separate nodes.
2. **Small files.** Prefer a module under `src/lokay/proc/` over growing a multi-job module.
3. **Compose, don't absorb.** A CLI wrapper invokes one Fala path. It does not chain workflows in Python or reimplement GitHub/git/the coding harness.
4. **Text interfaces.** JSON on stdout, one envelope; explicit errors.
5. **Dry-run is explicit non-mutation**, not a fake agent.
6. **No hidden side channels.** CLI args, JSON and Fala conduction carry data, not Hermes Kanban.
7. **Order is a Fala graph.** See [GRAPH.md](GRAPH.md); Python is not an alternate scheduler.
8. **Always `uv`.** Product commands use `uv run`.
9. **No stubs.** See [NO_STUBS.md](NO_STUBS.md).
10. **Hypermedia UI:** server-owned HTML fragments, no SPA ([HTMX.md](HTMX.md)).
11. **Alpine:** local interactions only, no server-state mirrors ([ALPINE.md](ALPINE.md)).
12. **Platform:** product_shell and same-origin static assets ([PLATFORM_UI.md](PLATFORM_UI.md)).

## Top-level vs nested vs CLI

The table below is an inventory, **not execution order**.

- `top`: an entry or a direct atom of the live daemon/factory parent.
- `nested`: a one-job capability or child workflow, not a parent scheduler.
- `cli-wrapper`: an explicit command/status entry; its presence does not imply daemon conduction.
- `legacy-unused`: retained old-spine surface, not part of the live department parent; cleanup tracked in #998/#999. It is not a recommended second process.

`daemon_cycle` selects recovery XOR one `factory_pass`. The factory conducts
`host_ff`, its host gate and workspace, then five selected departments:
`self_repair`, `issue_triage`, `executor`, `pr_triage`, `pr_repair`.
It records results and returns; `reap_stale_worktrees` is a sibling from
`factory_begin`, never a prerequisite for product work or the receipt.
Implementation lives under `executor_department` / `issue_to_pr`.
`select_implement` is not the first step of the LaunchAgent tick.

The explicit CLI `product_entry` / `product_pass_budget` hosts bounded
multi-pass work and `leftover_closeout`. Its currently repeated slots are
tracked in #996; they are not eight passes inside `daemon_cycle`.
Legacy survey/plan/closeout paths still exist, but existence is not reachability
from the live parent. Do not describe them as its hidden housecleaning branch.

## Atomic CLI map

| Program | Layer | Job |
| --- | --- | --- |
| `lokay-list-inbox` | nested | list undecided open issues |
| `lokay-list-issues` | nested | list intentional open catalog issues |
| `lokay-intake-check` | cli-wrapper | one named deterministic intake check; post-triage overlap tracked in #1001 |
| `lokay-issue-split` | nested | bounded child-issue split |
| `lokay-stage-label` | nested | publish one issue decision |
| `lokay-select-issue` | nested | pick one issue |
| `lokay-assign-issue` | nested | assign maintainer |
| `lokay-make-branch` | nested | name one branch |
| `lokay-worktree-add` | nested | create one worktree |
| `lokay-plan-issue` | nested | persist approach evidence |
| `lokay-localize` | nested | validated edit-path proposal |
| `lokay-run-agent` | nested | configured coding harness slot |
| `lokay-commit-all` | nested | commit dirty work |
| `lokay-assert-real-diff` | nested | reject plan/localize-only output |
| `lokay-test-local` | nested | repository-declared local verification; no declaration is an explicit skip |
| `lokay-push` | nested | publish branch without force |
| `lokay-pr-create` / `lokay-pr-label` / `lokay-pr-checks` / `lokay-pr-merge` | nested | separate PR lifecycle capabilities |
| `lokay-classify-pr-triage-checks` | nested | checks row to wait, repair or review |
| `lokay-select-pr-triage-outcome` | nested | evidence to wait, repair or merge |
| `lokay-pr-route` | nested | closeout route |
| `lokay-repos` | cli-wrapper | read managed scope |
| `lokay-factory-begin` | top | open workspace through child Fala |
| `lokay-host-ff` | top | fetch and ff-only; never reset hard |
| `lokay-survey-prs` | legacy-unused | old fleet PR survey wrapper |
| `lokay-survey-inbox` | legacy-unused | old fleet inbox survey wrapper |
| `lokay-survey-ready` | legacy-unused | old fleet catalog survey wrapper |
| `lokay-survey-repos` | legacy-unused | Python survey chain pending removal (#999), not a valid composition example |
| `lokay-plan-pass` | legacy-unused | old fleet target planning |
| `lokay-dispatch-triage` | legacy-unused | old planned-inbox dispatch |
| `lokay-resolve-conflicts` | legacy-unused | old conflict sweep |
| `lokay-closeout-pr` | nested | one PR closeout child |
| `lokay-closeout-prs` | legacy-unused | old per-repo closeout sweep |
| `lokay-refresh-occupancy` | legacy-unused | old fleet occupancy refresh |
| `lokay-reap-stale-worktrees` | top | independent cleanup sibling |
| `lokay-select-implement` | legacy-unused | old fleet implement selection; not parent-first |
| `lokay-rebase-onto-base` | nested | rebase; conflict fails closed |
| `lokay-queue-conflict` | nested | covering facts then bounded reconciliation |
| `lokay-dispatch-implement` | nested | intake/implementation dispatch child |
| `lokay-compute-health` | cli-wrapper | remaining-work health calculation |
| `lokay-record-pass` | top | truthful receipt: published PR, merge or none; start is occupancy |
| `lokay-last-pass-moving` | top | read last delivery result |
| `lokay-leftover-skip` | nested | classify leftover overflow, not a stall |
| `lokay-select-repair-route` | top | recovery exclusions and confirmed-stall gate |
| `lokay-record-inflight-remaining` | nested | persist working occupancy |
| `lokay-factory-pass` / `lokay-factory-tick` | cli-wrapper | invoke the same parent `factory_pass` |
| `lokay-work` / `lokay-status` | cli-wrapper | work entry / read-only status |
| `lokay-wake` | cli-wrapper | event entry into issue/PR triage or bounded factory work |
| `lokay status --human` | cli-wrapper | residual exception report, not a factory brake |

**Factory-pass law:** the parent conducts five departments, not a Python
select-first/houseclean-otherwise loop. Each department is a child Fala;
CLI wrappers only enter graphs. `compose/tick.py` must not become a fleet
scheduler. Removing old-spine surfaces must preserve required domain jobs
under the appropriate department, not create another CLI org chart.

Humans author intentional issues; the process delivers quality code to main.
A residual human verdict does not stop unrelated work. Never add approval
rituals merely because an issue requires judgment.

## Anti-patterns

- One module doing intake, worktree, coding and publication.
- A Python sequence of multiple workflow calls posing as one atom.
- An agent replacing mechanical list, merge or host-ff effects.
- Shared mutable state hiding process order.
- Fake coding agents or canary-only changes presented as delivery.
- Hermes Kanban as the execution ledger.

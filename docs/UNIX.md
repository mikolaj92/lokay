# Unix process model (binding)

Lokay is a **pipeline of small programs**, not a monolith.

## Rules

1. **One process = one job.** List issues. Make a branch name. Add a worktree. Run Grok. Push. Open a PR. Check CI. Merge. Nothing else.
2. **Small files.** Prefer a new module under `src/lokay/proc/` over growing an existing one past ~100 lines of real logic.
3. **Compose, don’t absorb.** Higher-level flows (`issue-to-pr`, `tick`) only **call** atomic processes in order. They must not reimplement GitHub/git/Grok.
4. **Text interfaces.** Each process speaks **JSON on stdout** (one object). Errors: non-zero exit + JSON `{"ok":false,"error":...}` when practical.
5. **Dry-run is a flag, not a mode buried in business logic.** `--live` opts into mutation; default plans only.
6. **No hidden side channels.** If a step needs data, it takes CLI args or stdin JSON from the previous step — not a secret global blackboard (no Kanban, no Fala journal required).

## Atomic CLI map

| Program | Job |
| --- | --- |
| `lokay-list-issues` | list ready issues for one repo |
| `lokay-select-issue` | pick one issue from a list (stdin) |
| `lokay-assign-issue` | assign maintainer on GitHub |
| `lokay-make-branch` | pure: branch name from repo+number+title |
| `lokay-worktree-add` | create/reuse git worktree |
| `lokay-run-grok` | run Grok coding agent in worktree |
| `lokay-commit-all` | stage+commit if dirty |
| `lokay-push` | push branch (no force) |
| `lokay-pr-create` | open PR |
| `lokay-pr-label` | add labels |
| `lokay-list-prs` | list open `ai/fix/*` PRs |
| `lokay-pr-checks` | report checks green/fail |
| `lokay-pr-merge` | merge if policy allows |
| `lokay-issue-to-pr` | **compose** the above for one issue |
| `lokay-tick` | **compose** intake + triage once |
| `lokay` | umbrella CLI (`init` / `validate` / thin wrappers) |

## Anti-patterns

- One 300-line module that does intake + worktree + agent + PR + triage.
- Shared mutable “session” objects that skip process boundaries.
- Re-introducing Hermes Kanban or Fala graphs **before** the atomic CLI path is boringly reliable.

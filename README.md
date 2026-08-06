# Lokay lite (Unix processes)

Minimal **issue → Grok → PR** automation as **small atomic programs**.

Binding design notes: [`docs/UNIX.md`](docs/UNIX.md).

| Old Lokay | This checkout |
| --- | --- |
| Hermes + Kanban + Fala graph | **standalone** atomics |
| omp | **Grok** |
| one mega tick | **compose** of `lokay-*` tools |

## Install

```bash
cd ~/Developer/OSS/lokay
uv sync
uv run pytest -q
```

## Atomic tools (one job each)

```text
lokay-list-issues      list ready (ai:ready) issues (JSON)
lokay-list-inbox       list undecided open issues
lokay-triage-issue     apply ready / needs-feedback / OOS
lokay-select-issue     pick one issue from stdin JSON
lokay-assign-issue     assign maintainer
lokay-make-branch      pure branch name
lokay-worktree-add     git worktree
lokay-run-grok         coding agent in worktree
lokay-commit-all       commit if dirty
lokay-push             push (never force)
lokay-pr-create        open PR
lokay-pr-label         labels
lokay-list-prs         open ai/fix/* PRs
lokay-pr-checks        CI status
lokay-pr-merge         merge if policy allows
```

Composers (only chain the above):

```text
lokay-issue-to-pr      one issue end-to-end
lokay-tick             multi-repo: inbox triage → ready → PR
lokay                  umbrella: init | validate | tick | run
```

Example pipe:

```bash
uv run lokay-list-issues --config config.yaml --repo owner/name --live \
  | uv run lokay-select-issue \
  | jq .
```

## Happy path

```bash
uv run lokay init --config config.yaml \
  --repo mikolaj92/SOME-REPO \
  --clone /Users/mikomac/Developer/OSS/SOME-REPO \
  --force

uv run lokay validate --config config.yaml
uv run lokay tick --config config.yaml          # dry-run plan
uv run lokay-make-branch --repo a/b --issue 1 --title "demo"
```

Live requires **both**:

1. `mode: live` and `executor.enabled: true` in config  
2. `--live` on the command  

```bash
uv run lokay-issue-to-pr --config config.yaml --repo owner/name --issue 12 --live
```

## Layout

```text
src/lokay/
  proc/           # atomic processes (CLI entrypoints)
  compose/        # only chains atomics
  gh_issues.py    # issue I/O helpers
  gh_prs.py       # PR I/O helpers
  git_*.py        # branch / worktree / commit / push
  grok_agent.py
  models.py
  envelope.py     # JSON ok/err stdout
docs/UNIX.md      # process philosophy (binding)
```

## Safety

- dry-run default  
- no force-push / repo delete / raw curl  
- issue body untrusted in Grok prompt  

## Not goals yet

Hermes, Kanban, Fala multi-effector graphs, launchd immutability theater — only after atomics are boringly reliable.


## Canary status (this machine)

First live e2e on 2026-08-06 (agent=`grok`):

- repo: [mikolaj92/lokay-lite](https://github.com/mikolaj92/lokay-lite)
- issue: #1
- PR: https://github.com/mikolaj92/lokay-lite/pull/2
- steps: get → assign → branch → worktree → agent → commit → push → pr → labels

Swap agent with `executor.agent: grok` when ready; pipeline stays the same.

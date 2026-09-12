# Working agent factories → five Lokay departments

Sources, not invention. The five department bodies are authored child Falas; agents stay leaves inside those children.

## What actually ships (2025–2026)

### GitHub Copilot cloud agent
Primary: `github/docs` `content/copilot/concepts/agents/cloud-agent/about-cloud-agent.md`
How-to: `content/copilot/how-tos/use-copilot-agents/cloud-agent/use-cloud-agent-on-github.md`

- Intake: human assigns the issue to Copilot (or `/task`, agents panel, Slack/Teams).
- One session, one ephemeral Actions sandbox.
- Agent: research repo → plan → code on a new branch → run tests/linters → push → open PR → add human as reviewer.
- Later issue comments are ignored. Steering is PR comments (`@copilot`) or "Fix with Copilot" on a failed Actions run.
- Merge is not the coding session. Human reviews and merges.
- Occupancy is one sandbox per task. No 400-ticket sieve inside the coder.

### Claude Code Action (`anthropics/claude-code-action`)
Primary: `docs/usage.md`, `docs/solutions.md`

- Intake: `@claude` mention, assignee trigger, or label. Separate automation for new issues.
- Issue triage automation: classify, labels, duplicate search. **Does not code.**
- Executor: mention/assign on an issue → edit files, commit, open/update PR.
- PR triage: `pull_request` opened/synchronize → review comments + inline comments. **Does not merge** in the stock solutions.
- Repair: comment on the PR / failed checks → same branch, push more commits.
- Tools are listed (`gh`, edit, git). Progress is a tracking comment with checkboxes.

### Google Jules
Primary: Google Labs blog 2025-05-20, https://jules.google.com/docs

- Asynchronous coding agent. Reads the repo, writes tests, fixes bugs.
- Secure cloud VM. GitHub integration. Opens a PR for a human.
- Not a local state machine of 500 effectors.

### OpenAI Codex
Primary: https://github.com/openai/codex README; cloud at chatgpt.com/codex

- Local CLI pair-programmer **or** cloud agent that opens a PR.
- Coding session ≠ merge session.

### Local skill `github-issue-to-pr` (this machine)
- `gh issue view` → one branch `issue-N-slug` → smallest diff → repo's own tests → commit `Closes #N` → `gh pr create`.
- Stop if covering PR exists, issue is ambiguous, or checks are red.

## Pattern that works (all of the above)

1. **Pick one ticket.** Do not re-sieve the whole catalog inside the coder.
2. **One sandbox / one branch.** Occupied repo with a live launch → skip, do not launch a second. Occupancy with **no covering PR** and a dead wrapper is that ticket: finish the PR, do not return `busy`.
3. **Coder opens a PR. Coder does not merge.** `route=busy` is occupancy in progress, not the slot finishing.
4. **Review is a different session** (comments, CI, quality). Merge is a gate after that. Prefer a green mergeable PR over classifying a red PR as `repair` and stopping.
5. **Repair is the same branch**, triggered by red checks or review comments. A parked / budget-exhausted PR is skipped this pass so another PR can merge.
6. **Watchdog** is retry / "fix this CI" / session restart — not a second product graph, and not a rewrite of lokay for leftover/occupancy/`pass_ceiling`.

## Map onto Lokay's five departments

| Department | Working analogue | This slot does | This slot never does |
|---|---|---|---|
| `issue_triage` | Claude issue auto-triage + Copilot "is this assignable?" | List open intentional issues, skip occupied/foreign/covering-PR, pick shippable `do` up to cap, leftover the rest | Code, branch, PR, `issue_to_pr` |
| `executor` | Copilot assign / Claude implement / skill issue→PR | One issue → worktree → diff → tests → push → open PR. Finish occupancy that has no PR | Merge, second occupancy, sieve, `busy` as success without a PR |
| `pr_triage` | Claude PR review + Copilot "human reviewer" | List `ai/fix` PRs, checks, review, merge quality+green first | Start `pr_repair`, invent a fourth verdict, loop the same red PR while a green one exists |
| `pr_repair` | `@copilot` on PR / "Fix with Copilot" | Same branch, fix red checks or review comments, push | Merge, new ticket |
| `self_repair` | Session retry / watchdog on the factory itself | Only a stall of **lokay** (not leftover/occupancy/idle/`pass_ceiling`) | Product `issue_to_pr`, PR merge, occupancy-without-PR as a lokay rewrite |

Lokay Done = merge to `main`. That is the one place we differ from Copilot/Claude stock: `pr_triage` may merge. The executor still must not. A valid JSON envelope with `outcome=none` is not Done.

## What we will not copy from other factories

The authored children (`issue_sieve_rows`, `issue_to_pr_delivery`, `pr_triage`, `pr_repair`, `self_repair`) are the live department bodies. Other factories inform occupancy and merge-is-not-the-coder. They do not replace those children with five department-wide agents.

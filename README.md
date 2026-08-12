# Lokay

Lokay continuously mills work across configured GitHub repositories: survey and triage first, close out existing AI pull requests, then implement at most one ready issue per tick with a real configured coding executor.

## What one tick does

1. Surveys every enabled repository for inbox issues, `ai:ready` issues, and open `ai/fix/*` pull requests.
2. Triages undecided issues through the `issue_triage` Fala path.
3. Applies global PR-first close-out: conflicts are closed and re-readied, failed work enters `pr_repair`, and approved mergeable work enters `pr_triage`.
4. If no actionable AI PR remains, implements at most one ready issue through `issue_to_pr`, and only in a repository with no open AI PR.
5. Reports truthful health. Remaining work without progress is not reported as idle; waiting and survey errors remain distinct outcomes.

The top-level mill runs the parent `factory_pass` Fala. Its `factory_tick` effector applies the multi-repo pass policy and composes the smaller `issue_triage`, `pr_triage`, `pr_repair`, and `issue_to_pr` child Falas. Parent and child runs use separate journals.

## Architecture

- `src/lokay/proc/`: small command-line atoms. They exchange JSON envelopes on stdout.
- `fala/lokay.fala-package.toml`: authored parent `factory_pass` plus child conduction for `issue_triage`, `pr_triage`, `pr_repair`, and `issue_to_pr`.
- `src/lokay/compose/`: graph entrypoints plus the Python tick, mill, and status policy.
- `executor.command` and `executor.args`: the sole nondeterministic coding slot. Lokay rejects fake, stub, and no-op agents.
- `repos.mikolaj92.yaml`: managed repository scope.

There is no alternate Python fallback graph and no Hermes/Kanban execution ledger.

## Quick start

Requirements: Python 3.12+, [`uv`](https://docs.astral.sh/uv/), authenticated GitHub CLI `gh`, and a local Fala checkout at `../Fala` as configured in `pyproject.toml`.

```bash
uv sync
cp config.example.yaml config.yaml
uv run lokay validate --config config.yaml
uv run lokay-repos --config config.yaml
uv run lokay status --config config.yaml
uv run lokay path --describe
```

Dry-run is the default unless live mode is explicit:

```bash
uv run lokay tick --config config.yaml
uv run lokay mill --config config.yaml --live --max-passes 8
```

## Continuous operation

The product daemon entrypoint owns one OS advisory lock across preflight and work:

```bash
uv run lokay-daemon --config config.yaml --max-passes 8 \
  --outbox ~/.lokay/preflight-bootstrap-incidents.log
```

This machine uses LaunchAgent label `ai.mikolaj.lokay-mill`, `scripts/lokay-mill-daemon.sh`, and logs under `~/.lokay/logs/`. The repository does not install or version a LaunchAgent plist.

## Workflow paths

```text
factory_pass:  factory_tick → composes one or more child path runs
issue_triage: get_issue → triage_issue
pr_repair:    pr_checks → worktree_add → run_agent → commit_all → push
pr_triage:    pr_checks → pr_review → pr_merge → close_issue
issue_to_pr:  get_issue → assign_issue / make_branch → worktree_add
              → run_agent → commit_all → push → pr_create → list_prs → pr_label
```

`run_agent` is the only nondeterministic path node. All other nodes are deterministic GitHub, Git, or pure operations.

## Safety

- Live mutation requires explicit live mode and a healthy preflight lease.
- Dry-run never mutates and is not a substitute agent.
- Issue bodies and repository content are untrusted input to the executor.
- Product runtime does not force-push or delete repositories.
- Invalid structured review, requested changes, secrets, and human-review requirements fail closed.
- Pending CI, manual review, and survey errors are not reported as successful progress.

## Commands and layout

| Path or command | Purpose |
| --- | --- |
| `uv run lokay validate --config config.yaml` | Validate configuration |
| `uv run lokay-repos --config config.yaml` | List managed repositories |
| `uv run lokay status --config config.yaml` | Read-only readiness and remaining work (`--local` skips survey) |
| `uv run lokay path --describe` | Inspect materialized workflow paths |
| `uv run lokay mill --config config.yaml --live --max-passes 8` | Run a bounded live mill |
| `src/lokay/proc/` | Unix atoms |
| `src/lokay/compose/` | Path entrypoints and top-level mill policy |
| `fala/` | Authored Fala package |
| `scripts/lokay-mill-daemon.sh` | Launchd-compatible one-pass wrapper |

## Binding documentation

- [`docs/WORKING.md`](docs/WORKING.md) — working-machine contract and tick order
- [`docs/GRAPH.md`](docs/GRAPH.md) — Fala paths and conduction
- [`docs/UNIX.md`](docs/UNIX.md) — process boundaries and JSON envelopes
- [`docs/NO_STUBS.md`](docs/NO_STUBS.md) — real-agent requirement
- [`docs/HTMX.md`](docs/HTMX.md), [`docs/ALPINE.md`](docs/ALPINE.md), [`docs/PLATFORM_UI.md`](docs/PLATFORM_UI.md) — UI boundaries
- [`repos.mikolaj92.yaml`](repos.mikolaj92.yaml) — managed repository inventory

# Mill health without watching GitHub

Operators should not need chat notifications or the GitHub inbox to know whether
the autonomous mill is healthy. Use local commands and the pass receipt.

## One glance

```bash
uv run lokay status --config config.yaml
```

The JSON envelope includes:

| Field | Meaning |
| --- | --- |
| `mill_ready` | Config can mill live (mode/executor/merge gates) |
| `merge_enabled` | Whether PR merge is armed |
| `max_issue_to_pr_per_pass` / `k` | Parallel `issue_to_pr` budget per factory pass |
| `health` | `idle` / `progress` / `waiting` / `repairing` / `stall` / `survey_error` |
| `remaining` | Aggregate inbox, ready, actionable AI PRs, CI waits, … |
| `by_repo` | Per-repo inbox / ready / actionable open AI PRs |
| `human_residuals` | Compact needs-feedback / needs-review count (not a mill brake) |
| `last_pass` | Prior compact pass receipt (also refreshed by this survey) |

Residual mailbox detail (exception reporting only):

```bash
uv run lokay status --config config.yaml --human
```

Cheap readiness without a multi-repo `gh` survey (uses `last_pass` when present):

```bash
uv run lokay status --config config.yaml --local
```

## Pass receipt (LaunchAgent)

After each `factory_tick` / tick survey, Lokay writes a small JSON receipt next to
the state file (default `~/.lokay/last-pass.json`):

```bash
jq '{health, idle, progress, merge_enabled, k: .max_issue_to_pr_per_pass, remaining, by_repo}' \
  ~/.lokay/last-pass.json
```

Daemon logs remain under `~/.lokay/logs/mill-latest.log` (see
`scripts/lokay-mill-daemon.sh`). The receipt is the structured signal; logs are
the transcript.

## How to read health

| `health` | Operator action |
| --- | --- |
| `idle` | No remaining actionable work — mill may sleep until new issues |
| `progress` | Last pass moved the queue — healthy |
| `waiting` | Pending CI / review limbo / only manual PRs — honest wait |
| `repairing` | Repair / request_changes cycle in flight — honest wait |
| `stall` | Actionable work with no progress — investigate agent/merge/config |
| `survey_error` | `gh` list atoms failed — fix network/auth before trusting idle |

`ok=false` on status means **not working** (work remains but mill not live-ready,
or survey errors). `waiting` / `repairing` with `ok=true` is not a failure.

Human residuals never freeze other repos. High `human_residuals.count` is an
exception mailbox signal, not a mill brake.

## CI (repo checks)

GitHub Actions workflow `.github/workflows/checks.yml` runs `uv sync` +
`uv run pytest -q` on PRs and pushes to `main`. Fala is cloned as a sibling
(`../Fala`) so the path dependency in `pyproject.toml` resolves hermetically —
no Hermes path hygiene, no requirement for a git submodule on the runner.

# Mill health without watching GitHub

Operators should not need chat notifications or the GitHub inbox to know whether
the autonomous mill is healthy. Use local commands and the pass receipt.

**Health is not Done.** `last-pass.json` / `lokay status` tell you whether the
mill is turning. The Definition of Done is still only **quality code merged
to `main`** ([`WORKING.md`](WORKING.md)). `health=progress` with no merges is a
spinning machine, not a working factory.

## One glance

```bash
uv run lokay status --config config.yaml
```

The JSON envelope includes:

| Field | Meaning |
| --- | --- |
| `mill_ready` | Config can mill live (mode/executor/merge gates) |
| `merge_enabled` | Whether trusted auto-merge is armed |
| `require_checks` | Legacy remote-check switch; production keeps it false |
| `require_llm_review` | Structured approve/`merge_ok` required before merge |
| `max_issue_to_pr_per_pass` / `k` | Serial pass budget for `issue_to_pr` (default 1; not concurrency) |
| `health` | `idle` / `progress` / `waiting` / `repairing` / `stall` / `survey_error` |
| `remaining` | Aggregate inbox, ready, actionable AI PRs, waits, `merge_disabled`, … (survey lists the full page; a 50-row newest-first window is a lie) |
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

After each `factory_pass` (`lokay-record-pass`), Lokay writes a small JSON receipt
next to the state file (default `~/.lokay/last-pass.json`):

```bash
jq '{health, idle, progress, merge_enabled, require_checks, require_llm_review, k: .max_issue_to_pr_per_pass, remaining, by_repo}' \
  ~/.lokay/last-pass.json
```

Light glance ratios (ready / open AI PRs / mergeable_green / progress /
`human_residuals.count`) are fine. Do not grow a heavy metrics product around
the receipt — see [`AUTONOMY.md`](AUTONOMY.md).

Daemon logs remain under `~/.lokay/logs/mill-latest.log` (see
`scripts/lokay-mill-daemon.sh`). The receipt is the structured signal; logs are
the transcript. LaunchAgent `StandardOutPath` (`launchd-stdout.log`) is a
bounded glance (`health` / `progress` / optional error) — the full Fala
envelope stays in `mill-*.log`, which is size-capped and rotated. Bound is
in-place (same inode, no full-file slurp) and the tick reopens stdout after
truncate so launchd cannot punch a sparse hole at the old offset. The 60s tick
reinstalls editable `lokay`/`fala` when checkout HEAD or `uv.lock`
moved (`~/.lokay/uv-install.digest`) **or** `site-packages/lokay` still
shadows a different checkout (hatch `force-include` copies the tree and
wins over the editable pth). `PYTHONPATH=$LOKAY_ROOT/src` is exported so
organ subprocesses and detached `issue_to_pr` import the checkout, not a
stale wheel. An overlap envelope does not persist the digest. A failed
reinstall does not persist the digest. In-cycle `host_ff updated=true`
stops the pass (`health=host_updated`) so the next tick reloads. Launchd
`host_ff` skips when `mill.lock` is held; `LOKAY_PROCESS_HEAD` still
lifts `host_updated` if HEAD moved under the live daemon. `LastExitStatus=0` when the pass did work (`health=progress`
or detached `issue_to_pr_started`), even if the Fala wrapper envelope has
`ok: false`. `factory_begin` keeps a handful of `factory-pass-*` workspaces
beside `state.jsonl` and deletes the rest. After occupancy,
`reap_stale_worktrees` drops leftover `~/.lokay/worktrees` corners that
cannot resume (merged / closed CONFLICTING / unpublished-behind-main) and
`reap_stale_worktrees` drops leftover `~/.lokay/worktrees` corners that
cannot resume (merged / closed CONFLICTING / unpublished-behind-main) and
KEEPS a live i2pr (receipts or occupancy), a repo whose PR survey failed,
an open covering PR, or a dirty unpublished leftover. A live receipt with an
unreadable process command stays live; a failed `ps` mutex survey refuses all
new launches. Failed `list_prs`, local process uncertainty, and unreadable
lifecycle receipt state are unknown, not idle: unreadable receipts prevent
new dispatch and keep every corner. Each detach atomically reserves its
receipt *before* spawning and pipe-gates the child until its matching PID
receipt is durable; launcher death before publication releases no worker, so a
later pass can recover that orphan without opening a same-worktree race. If
final PID publication fails it terminates the
process group and retains its reservation unless termination is confirmed.
One `ls-remote --heads` per repo — never a per-branch fetch. A ready published
tip is reaped; `issue_to_pr` RESETs from main.

## How to read health

| `health` | Operator action |
| --- | --- |
| `idle` | No remaining actionable work — mill may sleep until new issues |
| `progress` | Last pass moved the queue — mill is turning; **not** proof of Done |
| `waiting` | legacy remote-check wait / review limbo / green but `merge.enabled` false (`remaining.merge_disabled`) / parked `ai:needs-review` mailbox / ready catalog frozen by per-repo PR-first or occupancy — honest wait |
| `repairing` | Repair / request_changes cycle in flight — honest wait |
| `stall` | Actionable work with no progress — investigate agent/config (not merge-disarmed green) |
| `survey_error` | `gh` list atoms failed — fix network/auth before trusting idle |

`ok=false` on status means **not working** (work remains but mill not live-ready,
or survey errors). `waiting` / `repairing` with `ok=true` is not a failure.

**Merge wait vs stall:** tick/fleet health and `merge_policy` share one soft-wait
matrix (`WAITING_REASONS` → `pending_checks` / `no_checks_blocked` /
`merge_disabled`). Green checks with `merge.enabled` false are `waiting` (mill
ok-stop), never false `stall`. Arm merge to proceed; do not treat this as
recovery.

**Needs-review is mailbox, not stall:** parked `ai:needs-review` PRs are human
mailbox residual (`waiting` / `human_residuals`). They must not count as mill
`stall`, must not mint a recovery fingerprint, and must not PR-first-block
implement of *other* ready issues in that repo.

**Closed-issue abort is done, not stall:** timeout-resume / `pr_create` skip
with `reason=issue_closed` when a sibling already closed the ticket. Harvest
does not bury it; occupancy dies with the pid.

**PR-first / occupancy is wait, not stall:** `remaining.ready` is the survey
catalog. A late covering PR (published after `survey_prs`) or a live / just-
merged occupancy freezes that catalog for the repo — closeout owns the lane.
`refresh_occupancy` must not spend a second 29-repo `gh pr list` on that
frozen set (secondary rate-limit then fingerprints `survey_error`).
Those ready rows must not fill `actionable_now` or the 4-of-5 stall quorum.
A clean repo with leftover ready is still a stall if the mill made no progress.

**GitHub 503 is not missing auth or failed verification:** `github_authentication` must
not treat a transient `gh api user` 5xx as `unavailable` when `gh auth status`
still proves a local token. Separately, `pr_checks` maps GitHub/rate-limit
429/5xx uncertainty to non-green `pending`, so closeout waits rather than
running `pr_repair` against a published tip. Neither case authorizes a merge.

**Recovery boundary:** `waiting` / `repairing` (and other soft mill health) must
not mint systemic stall fingerprints or fill the daemon 4-of-5 quorum into
`self_repair`. Pass receipts and `lokay status` keep reporting those honest
waits; recovery only enters on carrier/preflight failure or confirmed hard
product-mill stalls. See [`WORKING.md`](WORKING.md) (Self-repair / recovery) and
[`GRAPH.md`](GRAPH.md) (`daemon_cycle` / `self_repair`).

Human residuals never freeze other repos. High `human_residuals.count` is an
exception mailbox signal, not a mill brake.

## Lokalne testy repozytorium

Lokay nie używa GitHub Actions ani zdalnego CI. Każde zarządzane repozytorium
deklaruje własne lokalne polecenie testowe w `[tool.lokay] test`. Fala uruchamia
je w worktree przed `push` i ponownie przed `merge`. Brak deklaracji jest jawnym
`skipped`, a nie domyślnym `pytest`.

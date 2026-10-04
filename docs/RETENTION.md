# Retention policy (t_2d81b9c3)

One rule: **execution data is consumable; code and error logs stay.** Code
lives in git; error logs stay in `logs/`, `fail-digests/`, `quarantine/` and
`recovery-history.jsonl` until a hard-cap last resort.

## What is deleted

- **Terminal Fala runs** (`completed`/`failed`/`cancelled`/`timed_out`)
  older than `retention.max_age_days` (default 14) are deletion candidates
  through `fala.maintain_journal` — nonterminal runs are never candidates.
  The newest `retention.journal_keep_last` (default 5) terminal runs are
  kept, and the journal is VACUUMed to return the space. Native maintenance
  keeps the pre-retention contract: probe/apply two-phase, one oversized
  journal per tick (smallest first), VACUUM only when free space can hold
  the compact copy plus a 16 MiB margin, and self-repair reclaim stays on
  the owning recovery path with lease evidence.
- **Wrapper traces** (`daemon-cycle-*`, `daemon-entry-*`, `factory-pass-*`)
  are one-tick pass data: the newest `retention.wrapper_keep` (default 2)
  quiet dirs per prefix survive; anything beyond the window is pruned.
- **Stale journal dirs** (per-issue / per-family) older than
  `max_age_days`, quiet (no fresh `-wal` activity) and holding only
  terminal runs are removed whole. Unreadable journals are retained.
- **Old archives** (`fala-archive-*`, `fala-retained-*`, `cleanup-*`,
  old preflight logs) older than `max_age_days` are removed.

## Hard cap

When `~/.lokay` exceeds `retention.hard_cap_gb` (default 10), the oldest
consumable data is evicted instead of failing the pass — oldest-first across
wrapper traces, dead terminal journals, archives and (last resort) old logs.
Protected state is never evicted: `state.jsonl`, `fail-digests/`,
`decisions.jsonl`, `recovery-history.jsonl`, `quarantine/`, `health-lease*`,
git repos and `worktrees/` (own reap flow with unpublished-work protection).

## Never

- No direct sqlite edits — sidecars (`-wal`/`-shm`) are Fala's.
- No deletion of nonterminal runs or any dir written inside the live grace
  window (1 h).
- No deletion of worktrees with unpublished commits — `reap_stale_worktrees`
  and `remove_worktree` keep their existing safety contracts.

## Config

```yaml
retention:
  max_age_days: 14
  hard_cap_gb: 10
  wrapper_keep: 2
  journal_keep_last: 5
```

Run manually: `uv run lokay-retention` (add `--skip-sqlite` for filesystem
classes only). The daemon cycle applies the policy every tick, resolved
before the pass ceiling is armed, before `run_path`.

## History: retention acceptance (#1107)

Age, wrapper count, or file size is not delivery evidence. The #1107
containment stance (`completion_evidence_required`, dry-run planning) was
superseded by the t_2d81b9c3 policy above: Mikołaj decided execution data is
consumable after age (14 days) instead of waiting for per-artifact completion
proofs. The safety invariants that survived: nonterminal runs are never
deleted, unreadable journals are retained, live writers are protected by the
grace window, sqlite stays behind Fala's native API, and the one-journal-
per-tick vacuum headroom gate is untouched.

Current containment behavior (still enforced where the policy above does not
reach):
- Orphaned or uninspectable worktrees are retained.
- A worktree with commits absent from origin/main is retained, including reset requests.
- TTL archive GC retains recovery copies and reports their paths.
- Log, backup, and subflow-directory age pruning reports completion_evidence_required.
- Fala maintain_journal applies terminal-run deletion on one oversized journal per tick, smallest first. A journal with no terminal-run candidates does not consume the apply slot; the next oversized journal with candidates is reclaimed.
- VACUUM is Fala-owned and runs only when remaining free space can hold the compact copy plus a 16 MiB safety margin.
- Maintenance never finalizes created/running runs. Only the owning recovery path may do so with lease evidence.

Direct archive reclaim now uses pinned-parent, empty-only rmdir. It cannot
destroy nonempty recovery snapshots or ignored/late content. Nonempty snapshots
are retained with their location reported. Complete bounded retention still
requires a verified success-summary/dependency policy; do not close #1107 on
containment tests alone.

# Retention acceptance (#1107)

Age, wrapper count, or file size is not delivery evidence.

Current behavior:
- Orphaned or uninspectable worktrees are retained.
- A worktree with commits absent from origin/main is retained, including reset requests.
- TTL archive GC retains recovery copies and reports their paths.
- Log, backup, and subflow-directory age pruning reports completion_evidence_required.
- Wrapper allocation keeps earlier journals.
- Fala maintain_journal is called with dry_run=True; proposed candidates are not deletions.
- Maintenance never finalizes created/running runs. Only the owning recovery path may do so with lease evidence.

This is containment, not complete bounded retention. Before enabling deletion:
1. Bind the artifact to a completed work unit and its exact revision.
2. Preserve a compact success summary and prove no unpublished content is lost.
3. Prove no live writer or recovery/child reference needs it.
4. Recheck identity/content at deletion, including ignored files and ancestor swaps.
5. Report actual deletion separately from candidates and failed removals.

Direct archive reclaim now uses pinned-parent, empty-only rmdir. It cannot
destroy nonempty recovery snapshots or ignored/late content. Nonempty snapshots
are retained with their location reported. Complete bounded retention still
requires a verified success-summary/dependency policy; do not close #1107 on
containment tests alone.

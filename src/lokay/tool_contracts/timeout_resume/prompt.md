Goal: finish the in-progress fix. The previous coding session was killed after <<timeout_seconds>>s.

Repository: <<repo>>
Branch: <<branch>>
<<issue_line>>

This is the single allowed continue attempt (K=1). The worktree and session are the same as the killed run. Do not start over. Inspect the current tree, keep useful edits, finish the smallest remaining change, then stop.

Rules:
1. Resume — do not wipe or rewrite finished work.
2. Make the smallest safe change that completes the issue; you MUST edit files if work remains.
3. Do NOT merge, force-push, delete branches, open PRs, or push — the orchestrator does that.
4. Leave the tree with your changes (commit if you can; uncommitted is fine).
5. Keep `.lokay/approach.md` and `.lokay/localize.json` on the branch.

Summarize what was already done, what you finished, and residual risk.

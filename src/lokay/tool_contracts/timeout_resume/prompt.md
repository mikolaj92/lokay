Goal: finish the in-progress fix. The previous coding session was killed after <<timeout_seconds>>s.

Repository: <<repo>>
Branch: <<branch>>
<<issue_line>>

This is the single allowed continue attempt (K=1). The worktree and session are the same as the killed run. Do not start over. Inspect the current tree, keep useful edits, finish the smallest remaining change, then stop.

Rules:
1. Resume — do not wipe or rewrite finished work.
2. Make the smallest safe change that completes the issue; you MUST edit files if work remains.
3. Do NOT merge, force-push, delete branches, open PRs, push, claim issues, run take_issue, or call `gh` — the Lokay factory does that. Product AGENTS.md publication rules do not apply here.
4. Leave the tree with your edits uncommitted. Commit, push, and PR are later deterministic atoms, not this slot.
5. Keep `.lokay/approach.md` and `.lokay/localize.json` on the branch.

Finish with ONLY the closed coding JSON: {"verdict":"implemented"|"needs_evidence","evidence_kind":null,"summary":"...","tests_run":["..."],"residual_risk":"..."}.

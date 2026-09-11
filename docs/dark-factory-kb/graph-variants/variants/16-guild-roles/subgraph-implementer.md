# Subgraph: implementer

**Theme:** Guild Implementer — sandboxed coding + local gates → **draft PR only**.  
**Mode mix:** AGENT for code/repair; DET for sandbox, git, checks, open draft PR.

## Flow

```mermaid
flowchart TD
  A([enter: plan ready]) --> B[DET: worktree / sandbox from branch_hint]
  B --> C[AGENT SO: implement against plan]
  C --> D[DET: run linters / types / tests from plan]
  D --> E{green?}
  E -->|no| F{repair attempts < N?}
  F -->|yes| G[AGENT SO: repair_code]
  G --> D
  F -->|no| X([leave: fail bounded — no draft PR])
  E -->|yes| H[DET: stage + commit]
  H --> I[DET: push origin]
  I --> J[DET: open PR as DRAFT]
  J --> K([leave: draft PR open])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,D,H,I,J det
  class C,G agent
```

## Invariant: draft ceiling

- PR is created with **draft: true** (or factory-draft label equivalent).
- Implementer **never** merges, never requests human review as “ready” without Reviewer seat, never flips draft→ready.
- Ceiling of this subgraph = `{draft_pr_url, commit_shas, summary}`.

## Notes

- **Sandbox first.** Repo linters/types/tests run before any PR atom.
- **Bounded repair.** Max N repair loops; then fail closed — no infinite self-healing theatre.
- **Meat ≡ AI.** Same AGENT seat for human pair or coding agent; graph unchanged.
- **Plan is contract.** Implementer follows Planner files/non_goals/stop_if; scope creep → ok:false, not silent expansion.
- **Handoff contract.** Output = `{draft_pr, branch, commits, summary}` for Reviewer.
- **Polish:** implementer klepie i otwiera **draft**; merge nie jest jego sprawą.

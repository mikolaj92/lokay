# Subgraph: det-activities

**Theme:** CODE Activities — klepanie bez entropii: hydrate, plan template, worktree, test, git, open PR, merge policy.  
**Mode mix:** DET Activities. Idempotentne; retry Activity-scoped.

## Flow

```mermaid
flowchart TD
  A([enter: DET Activity scheduled]) --> B{which?}
  B -->|hydrate| H[DET: fetch issue + labels + ready-for-agent]
  B -->|planTemplate| P[DET: checklist from body/template — NOT LLM]
  B -->|claimWorktree| W[DET: branch klepacz/issue-N + occupancy]
  B -->|runTests| T[DET: test runner → junit/log]
  B -->|commitPush| G[DET: git commit + push origin]
  B -->|openPr| PR[DET: gh pr create ai/PR]
  B -->|mergePolicy| M[DET: Off|Classify|Always atom]
  B -->|merge| MG[DET: gh pr merge if allowed]
  H --> R[DET: return structured result]
  P --> R
  W --> R
  T --> R
  G --> R
  PR --> R
  M --> R
  MG --> R
  R --> OUT([leave: resume Workflow])
  T -->|fail| FAIL[DET: ok:false + failure_log]
  FAIL --> OUT

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class H,P,W,T,G,PR,M,MG,R,FAIL det
```

## Notes

- **Plan is DET here.** W odróżnieniu od 15/31: brak `planIssue` LLM Activity. Checklist z issue body / labeli / szablonu — człowiek lub skrypt przygotował ready-for-agent.
- **Idempotency keys.** `claimWorktree(issue-N)`, `openPr(issue-N)` — powtórka Activity po crashu nie dubluje PR.
- **Coder ceiling = open PR.** Merge tylko przez policy + Signal (Off) lub Always+green.
- **Handoff.** Leave = `{activity, ok, artifact_ref, failure_log?}` → Event History.

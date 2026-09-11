# Subgraph: review-merge

**Theme:** critical PR review (separate role) → QA strategy questions → merge.  
**Mode mix:** AGENT review; DET checks and merge.

## Flow

```mermaid
flowchart TD
  A([enter: PR open]) --> B[DET: wait / fetch CI status]
  B --> C{CI green?}
  C -->|no| D[DET: report failure]
  D --> R([leave: changes needed → implement])
  C -->|yes| E[AGENT: critical PR review]
  E --> F[AGENT: QA strategy — uncomfortable questions]
  F --> G{approve?}
  G -->|request changes| R
  G -->|yes| H[DET: apply labels / approvals]
  H --> I[DET: merge PR]
  I --> J[DET: cleanup branch if policy]
  J --> K([leave: merged])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,D,H,I,J det
  class E,F agent
```

## Notes

- **Separate role from implementer.** Critical review is never the same seat that wrote the diff (meat or AI).
- **QA strategy stays.** Uncomfortable questions are first-class: missing tests, unclear acceptance, silent scope creep, rollback story.
- **CI is DET gate.** No AGENT override of red builds in the thin path.
- **Merge is script.** After approve + green checks → merge; humans only on conflict/policy.
- **Changes-requested loops to implement** at top level — this subgraph does not re-implement in place.
- **Handoff contract.** Output = `{merged: true, pr, merge_sha}` or `{merged: false, feedback}` for re-implement.


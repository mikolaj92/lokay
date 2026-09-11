# Subgraph: review-merge

**Theme:** critical review (osobna rola) → QA questions → DET merge policy.  
**Mode mix:** AGENT SO review; DET labels + merge. Zakładamy współpracującego reviewera.

## Flow

```mermaid
flowchart TD
  A([enter: PR + CI green]) --> B[AGENT SO: critical PR review]
  B --> C[AGENT SO: QA strategy — uncomfortable questions]
  C --> D{verdict?}
  D -->|request changes| E([leave: feedback → implement-ship])
  D -->|approve| F[DET: apply review labels / approvals]
  F --> G{MergePolicy}
  G -->|Off| H([leave: PR open — human merge])
  G -->|Classify low / Always| I[DET: merge PR]
  G -->|Classify high| H
  I --> J([leave: merged])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class F,I det
  class B,C agent
```

## Notes

- **Separate role.** Reviewer ≠ implementer (meat lub AI — inne siedzenie).
- **QA strategy stays.** Brak testów, creep scope, rollback — first-class, nie ozdoba.
- **Optimistic Classify.** Przy green CI i niskim ryzyku Classify/Always może mergować bez czekania na człowieka; Off default per repo nadal OK.
- **Never LLM-merge.** Gałka MergePolicy jest DET — prompt nie „decyduje merge”.
- **Changes → ship.** Feedback wraca do implement-ship na top-level; ten podgraf nie koduje.
- **Handoff:** `{merged:true, merge_sha}` | `{hold:true, reason}` | `{changes:true, feedback[]}`.

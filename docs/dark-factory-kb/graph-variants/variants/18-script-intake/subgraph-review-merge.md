# Subgraph: review-merge

**Theme:** CI → critical review (osobna rola) → merge DET.  
**Mode mix:** AGENT review + QA strategy; DET checks / merge.

## Flow

```mermaid
flowchart TD
  A([enter: PR open]) --> B[DET: wait CI / checks]
  B --> C{CI green?}
  C -->|no| D[DET: report red]
  D --> R([leave: changes → implement-ship])
  C -->|yes| E[AGENT: critical PR review]
  E --> F[AGENT: QA — niewygodne pytania]
  F --> G{verdict?}
  G -->|changes / reject| R
  G -->|approve| H[DET: labels / approvals]
  H --> I[DET: merge PR]
  I --> J[DET: cleanup branch if policy]
  J --> K([leave: merged])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,D,H,I,J det
  class E,F agent
```

## Notes

- **Osobna rola.** Reviewer ≠ implementer (meat lub AI — to samo siedzenie, inna osoba/instancja).
- **QA strategy stays.** Scope creep, brak testów, rollback, „czemu nie prościej?” — first-class, nie fluff.
- **CI = DET gate.** AGENT nie overridenuje czerwonego builda na thin path.
- **Merge = skrypt.** Po approve + green → merge. Konflikt / policy block → człowiek.
- **Changes loop** wraca do implement-ship na top-level — bez re-pick (issue zamrożone z script-intake).
- **Handoff:** `{merged:true, merge_sha}` albo `{merged:false, feedback}`.

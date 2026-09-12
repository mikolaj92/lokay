# Subgraph: review-merge

**Theme:** krytyczny review (osobna rola) → DET merge policy; arch receipt wymagany gdy trzeba.  
**Mode mix:** AGENT SO (review) + DET (policy / merge) + hard check na arch-gate.

## Flow

```mermaid
flowchart TD
  A([enter: PR open, CI green]) --> B{arch_touch?}
  B -->|true| C{arch_approved receipt?}
  C -->|no| X([leave: fail-closed → arch-gate])
  C -->|yes| D[AGENT SO: critical review]
  B -->|false| D
  D --> E{verdict}
  E -->|changes_requested| F([leave: feedback → ship])
  E -->|approve| G[DET: apply MergePolicy]
  G --> H{policy}
  H -->|Off| I([leave: left_open — waiting human merge])
  H -->|Classify| J{risk class}
  J -->|high| I
  J -->|low/med + checks| K[DET: merge]
  H -->|Always| L{high-risk?}
  L -->|yes| X2([leave: blocked — high_risk_never_Always])
  L -->|no| K
  K --> M{merge ok?}
  M -->|conflict / block| F
  M -->|merged| N([leave: merged → qa-audit])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class C,G,K det
  class D agent
  class X,X2 bad
```

## Notes

- **Reviewer ≠ Implementer.** Osobna rola AGENT SO: spójność, fit architektoniczny (gdy arch już approved), komentarze, structured verdict.
- **Arch receipt jest twardym checkiem.** Bez niego nie ma ścieżki do merge — nawet gdy review jest zielony.
- **MergePolicy Off default.** Never LLM merge. Always + high-risk = zabronione.
- **left_open is honest.** Policy Off → PR zostaje otwarty z receipt; człowiek merżuje gdy chce — nie limbo theatre.
- **Handoff:** `{merged:true, merge_sha}` | `{left_open:true, reason}` | `{changes_requested, feedback}` | `{blocked, reason}`.

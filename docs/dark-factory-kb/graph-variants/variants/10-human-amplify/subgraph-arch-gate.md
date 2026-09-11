# Subgraph: arch-gate

**Theme:** jawna bramka HUMAN na zmianę architektury — approve / reject / redesign / hold.  
**Mode mix:** 100% HUMAN (+ DET receipt). Agent nie zatwierdza własnej zmiany kontraktu.

## Flow

```mermaid
flowchart TD
  A([enter: PR + arch_touch=true]) --> B[DET: package arch diff brief]
  B --> C[HUMAN engineer: read contracts / topology / blast radius]
  C --> D{decision}
  D -->|approve| E[DET: write receipt arch_approved]
  E --> F([leave: approved → review-merge])
  D -->|reject| G[DET: write receipt arch_rejected + feedback]
  G --> H([leave: redesign → ship])
  D -->|redesign request| G
  D -->|hold / need more context| I[DET: write receipt arch_hold]
  I --> J([leave: human hold — no limbo])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef human fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,E,G,I det
  class C human
  class J bad
```

## Notes

- **To jest rdzeń human-amplify.** Architektura nie jest „komentarzem w review” — jest osobnym siedzeniem HUMAN z binding decision.
- **Fail-closed.** `arch_touch=true` bez `arch_approved` receipt → merge zabroniony (nawet przy MergePolicy Always).
- **Pytania inżyniera (minimum):**
  1. Jaki kontrakt się zmienia i kto go konsumuje?
  2. Czy da się osiągnąć cel bez ruszania granicy modułu?
  3. Jaki jest rollback / compat path?
  4. Czy ADR / docs trzeba zaktualizować w tym samym PR?
- **DET tylko pakuje brief i pisze receipt.** Nie „sugeruje approve”. Nie limbo label — `arch_hold` / `arch_rejected` / `arch_approved` z id.
- **Meat nie siedzi tu jako AGENT.** Gate jest ludzki z definicji; AI może przygotować brief, nie decyzję.
- **Handoff:** `{arch:approved, receipt_id}` | `{arch:rejected, feedback}` | `{arch:hold, receipt_id}`.

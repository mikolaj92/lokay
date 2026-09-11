# Subgraph: review-fix

**Theme:** niezależny review slot + bounded fix przez etykiety (nie chat-loop w jednym mózgu).  
**Mode mix:** AGENT SO review/fixer; DET cap, label flips, CI re-check.

## Flow

```mermaid
flowchart TD
  A([enter: stage validating / fixing]) --> B[DET: load PR diff + attempt counter]
  B --> C{stage == fixing?}
  C -->|yes| D[AGENT SO: fixer apply review comments]
  D --> E[DET: test + push]
  E --> F{green?}
  F -->|no / cap| X([leave: needs-human])
  F -->|yes| G[DET: label → validating]
  G --> H
  C -->|no| H[AGENT SO: adversarial / critical review]
  H --> I{verdict?}
  I -->|approve| J[DET: label → workflow:pr-open]
  J --> Z0([leave: advance pr-open])
  I -->|changes| K{attempts < MAX?}
  K -->|yes| L[DET: label → workflow:fixing + bump counter]
  L --> Z1([leave: reenter implement/fix])
  K -->|no| X

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,E,G,J,L det
  class D,H agent
  class X bad
```

## Notes

- **Reviewer ≠ implementer.** Osobny job/profil (gp-foundry reviewer; chippingway Codex review; jnurre adversarial). Write limited do komentarzy / werdyktu SO.
- **Werdykt = enum.** `{verdict: approve|changes|block, comments[]}`. DET mapuje na label — model nie „klika merge”.
- **Bounded fix.** MAX (np. 3) w metadata issue/PR. Cap → `workflow:needs-human` / `agent:review-unresolved`. Escape obowiązkowy jak w gp-foundry model-check.
- **Fixing to osobny stage.** Etykieta `workflow:fixing` (jnurre `agent:revision`) wraca do implement-validate albo lokalnego fixer slota — zawsze przez spine, nie przez ukryty goto w prompcie.
- **CI wait.** Opcjonalny DET check-run przed approve; czerwone CI ≠ approve.
- **Handoff:** `{verdict, attempts}` → merge-escape albo re-enter.

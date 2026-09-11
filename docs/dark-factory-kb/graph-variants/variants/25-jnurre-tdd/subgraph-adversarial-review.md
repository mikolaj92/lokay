# Subgraph: adversarial-review

**Theme:** niezależny adversarial review + bounded revision przez etykiety (circuit breaker).  
**Mode mix:** AGENT SO review/fixer; DET cap, label flips, re-test.

## Flow

```mermaid
flowchart TD
  A([enter: after TDD green / agent:revision]) --> B[DET: load diff + attempt counter]
  B --> C{stage == revision?}
  C -->|yes| D[AGENT SO: apply review comments]
  D --> E[DET: AGENT_TEST_COMMAND + push]
  E --> F{green?}
  F -->|no / cap| X([leave: agent:review-unresolved])
  F -->|yes| G[DET: reenter review slot]
  G --> H
  C -->|no| H[AGENT SO: adversarial / critical review]
  H --> I{verdict?}
  I -->|approve| J[DET: label → agent:pr-open]
  J --> Z0([leave: advance pr-open])
  I -->|changes| K{attempts < MAX?}
  K -->|yes| L[DET: label → agent:revision + bump]
  L --> Z1([leave: reenter tdd-implement])
  K -->|no| X

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,E,G,J,L det
  class D,H agent
  class X bad
```

## Notes

- **Reviewer ≠ implementer.** Osobny dispatch profile (Claude vs Codex hybrid OK) — write limited do komentarzy / werdyktu SO. Duch jnurre „adversarial review loop”.
- **Werdykt = enum.** `{verdict: approve|changes|block, comments[]}`. DET mapuje na `agent:pr-open` / `agent:revision` / `agent:review-unresolved`. Model nie klika merge.
- **Circuit breaker.** MAX revision (np. 3) w metadata. Cap → `agent:review-unresolved` — obowiązkowy escape, nie limbo.
- **TDD też na revision.** Po fixerze znowu `AGENT_TEST_COMMAND` zanim wrócimy do review — czerwone nie wraca jako „approve z gwiazdką”.
- **Handoff:** `{verdict, attempts, pr_ready?}` → pr-cleanup albo re-enter TDD.

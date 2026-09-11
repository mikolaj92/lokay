# Subgraph: intake

**Theme:** wejdź do PM → weź **jeden** labeled ticket → worktree/branch.  
**Mode mix:** wyłącznie DET. Agent nie wybiera roboty (SOUL + compose).

## Flow

```mermaid
flowchart TD
  A([enter: daemon tick]) --> B[DET: list open issues]
  B --> C[DET: filter label ready-for-agent]
  C --> D{any labeled?}
  D -->|no| E([leave: idle — no work])
  D -->|yes| F[DET: pick one K=1]
  F --> G{acceptance present?}
  G -->|no underspecified| H([leave: skip underspecified])
  G -->|yes| I[DET: normalize ticket facts]
  I --> J[DET: assert occupancy K=1]
  J --> K{slot free?}
  K -->|busy| E
  K -->|free| L[DET: branch name from issue id]
  L --> M[DET: worktree add / checkout]
  M --> N[DET: ralph_tick_used = 0]
  N --> O([leave: issue + worktree → ralph-tick])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,F,I,J,L,M,N det
  class E,H bad
  class O ok
```

## Notes

- **Intake = skrypty.** Zero LLM przed pick. Ralph nie „szuka sobie roboty z czatu”.
- **K=1.** Jeden ticket, jeden przyszły PR; occupancy DET blokuje równoległe Ralph-pętle na tym samym repo (domyślnie).
- **Acceptance jest kontraktem pętli.** Bez kryteriów → skip, nie „agent wymyśli DONE”.
- **Licznik startuje na 0.** `ralph_tick_used` żyje w stanie grafu; implement/review go nie resetują.
- **Arch hint (opcjonalny DET).** Jeśli label/tytuł zawiera migration/auth/api — można od razu podnieść flagę pod późniejszy HITL; nie zastępuje review.
- **Handoff.** `{issue_id, acceptance[], branch, worktree, ralph_tick_used:0}` | `{idle:true}` | `{skip:true, reason:underspecified}`.

# Subgraph: review-merge

**Theme:** critical PR review (osobna rola) → MergePolicy DET.  
**Mode mix:** AGENT SO `pr_review`; DET CI wait + merge policy.

## Flow

```mermaid
flowchart TD
  A([enter: PR open]) --> B[DET: wait / fetch CI status]
  B --> C{CI green?}
  C -->|no| D[DET: report failure]
  D --> R([leave: changes needed → implement])
  C -->|yes| E[AGENT SO: pr_review]
  E --> F{verdict}
  F -->|changes| R
  F -->|reject / risk high| S[DET: leave open — never Always-merge]
  S --> T([leave: blocked for human])
  F -->|approve| G{MergePolicy DET}
  G -->|Off| H[DET: leave open for human]
  H --> U([leave: waiting human])
  G -->|Classify or Always| I[DET: merge_commit]
  I --> J[DET: close_issue / cleanup branch]
  J --> K([leave: merged])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,D,S,G,H,I,J det
  class E agent
```

## Structured output (`pr_review`)

```json
{
  "verdict": "approve"|"changes"|"reject",
  "reasons": ["..."],
  "risk": "low"|"high"
}
```

## Notes

- **Reviewer ≠ implementer.** Osobne siedzenie (mięso lub AI); zero self-approve.
- **QA strategy stays.** Niewygodne pytania (scope creep, brak testów, rollback) żyją w reasons.
- **CI is DET gate.** Agent nie override'uje czerwonego builda.
- **MergePolicy Off|Classify|Always.** Start zwykle Off lub Classify — nie L5 auto-merge theatre.
- **reject / high risk** blokuje Always; zostawia PR człowiekowi.
- **Changes-requested** wraca do implement (SO leaf), potem znowu przez git-pr DET — nie „agent pushuje z review”.
- **Handoff contract.** `{merged:true, merge_sha}` albo `{merged:false, feedback}` / `{waiting_human:true}`.
- **Polish:** krytyczny przegląd to osobna rola; merge to skrypt po zielonym werdykcie.

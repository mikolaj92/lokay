# Subgraph: mode-fix

**Theme:** stały job GHA `mode: fix` — komentarz `claude-fix` na PR → zastosuj feedback → push na ten sam branch.  
**Mode mix:** DET harness + AGENT leaf (`mode: fix`).

## Flow

```mermaid
flowchart TD
  A([enter: claude-fix on PR]) --> B[DET: if-guard association + has PR]
  B --> C[DET: checkout fetch-depth 0]
  C --> D[DET: setup-node + claude-code]
  D --> E[DET: wire tokens + pr-number]
  E --> F[AGENT: issue2claude mode=fix]
  F --> G[AGENT: read review comments / thread]
  G --> H[AGENT SO: apply requested changes]
  H --> I{ok / in scope?}
  I -->|out of scope / dangerous| J[DET: comment ask-or-stop]
  J --> Z0([leave: skip])
  I -->|true| K[DET: push same branch]
  K --> L([leave: PR updated — still Off])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,C,D,E,J,K det
  class F,G,H agent
  class Z0 bad
```

## Notes

- **Reuse fidelity.** Marketplace: „Claude reads your review comments and applies the changes — then pushes to the same branch.”
- **Same branch = K=1.** Fix nie otwiera nowego PR; coder ceiling nadal „PR open”, nie merge.
- **Token, nie LLM-router.** Obecność `claude-fix` w body wybiera ten job w YAML `if:` — model nie decyduje „wejść w fix mode”.
- **Bounded.** Poza Allowed / auth / billing / migracje → ask-or-stop, nie „ulepsz po drodze”.
- **Handoff contract.** `{pr_number, branch, shas[]}` \| `{skip, reason}`.

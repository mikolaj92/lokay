# Subgraph: pr-ceiling

**Theme:** coder ceiling = otwarty (draft) PR + etykieta `*-done`; merge zostaje przy człowieku.  
**Mode mix:** DET open PR + label flip; zero LLM-merge.

## Flow

```mermaid
flowchart TD
  A([enter: branch pushed]) --> B[DET: gh pr create draft Closes N]
  B --> C[DET: flip label → *-done]
  C --> D[DET: remove in-progress / start label]
  D --> E{MergePolicy}
  E -->|Off default JP| F([leave: PR open — human review + merge])
  E -->|Always| G{CI green?}
  G -->|yes| H[DET: merge]
  G -->|no| F
  E -->|Classify| I{risk low + CI green?}
  I -->|yes| H
  I -->|no / high| F
  H --> J([leave: merged])
  F -->|re-label auto-fix / agentic-fix| K([re-enter: label-fsm])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,D,E,G,H,I det
  class F stop
  class J ok
```

## Notes

- **Coder ≠ merge.** JP autorzy: zawsze ludzki merge. Default MergePolicy **Off** — zgodne z KLEPACZ / ready-for-agent.
- **Closes #N.** DET body PR linkuje issue; branch już `auto-fix/issue-N` (lub `fix/issue-N`).
- **`*-done` vs merge.** Done = „klepacz skończył sufit PR”, nie „weszło na main”. Failed path nigdy tu nie wchodzi (zostaje w leaf/gha).
- **JBS promotion.** Opc. PR do `devops` potem HITL `devops→dev→main` — nadal poza liściem Claude; człowiek na każdym stopniu.
- **Fix loop.** Re-label start albo review comments → z powrotem do label-fsm → GHA → worktree → leaf; nie merge z liścia.
- **NOT L5.** PR open + human merge = sukces klepacza; QA trzyma niewygodne pytania.
- **Handoff.** `{pr_url, number, labels: [*-done], policy_verdict: hold|merged}`.

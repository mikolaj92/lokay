# Subgraph: mode-rebase

**Theme:** stały job GHA `mode: rebase` — komentarz `claude-rebase` na PR z konfliktami → rebase + resolve → push.  
**Mode mix:** DET harness + AGENT leaf (`mode: rebase`).

## Flow

```mermaid
flowchart TD
  A([enter: claude-rebase on PR]) --> B[DET: if-guard association + PR thread]
  B --> C[DET: checkout fetch-depth 0]
  C --> D[DET: setup-node + claude-code]
  D --> E[DET: wire tokens + pr-number + repo]
  E --> F[AGENT: issue2claude mode=rebase]
  F --> G[DET/git: rebase onto base]
  G --> H{conflicts?}
  H -->|none| I[DET: push]
  H -->|yes| J[AGENT SO: resolve conflicts intelligently]
  J --> K{resolved clean?}
  K -->|no| L[DET: comment fail receipt]
  L --> Z0([leave: skip — human])
  K -->|yes| I
  I --> M([leave: PR rebased — still Off])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,C,D,E,G,I,L det
  class F,J agent
  class Z0 bad
```

## Notes

- **Reuse fidelity.** Marketplace: „Comment `claude-rebase` on a PR with merge conflicts. Claude rebases the branch, resolves conflicts intelligently, and pushes.”
- **fetch-depth: 0.** Wymagane do sensownego rebase — DET w spine, nie „agent sam zgaduje historię”.
- **Liść, nie merge.** Rebase + push kończy na zaktualizowanym PR; MergePolicy nadal Off domyślnie.
- **Fail closed.** Nierozwiązywalne / niebezpieczne konflikty → comment + human, nie force-merge z liścia.
- **Handoff contract.** `{pr_number, branch, rebase_ok: true}` \| `{skip, reason}`.

# Subgraph: post-merge

**Theme:** sprzątanie po merge — branch delete, label done, receipt.  
**Mode mix:** wszystko DET. Optymista domyka pętlę czysto.

## Flow

```mermaid
flowchart TD
  A([enter: merged]) --> B[DET: delete remote branch if policy]
  B --> C[DET: flip issue labels → done / remove ready-for-agent]
  C --> D[DET: write success receipt]
  D --> E[DET: optional notify channel]
  E --> F([leave: done — tip green])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,D,E det
  class F ok
```

## Notes

- **Close the loop.** Zmergowane bez sprzątania = pół sukcesu; etykiety i branche nie wiszą.
- **DET only.** Zero agenta po merge — housekeeping jest tanie i pewne.
- **Receipt > JSON theatre.** Zapis `{pr, merge_sha, ticket, closed_at}` na tipie hosta.
- **Notify optional.** Slack/webhook jeśli skonfigurowane; brak ≠ fail.
- **Handoff:** `{done:true, receipt}` → top-level DONE.

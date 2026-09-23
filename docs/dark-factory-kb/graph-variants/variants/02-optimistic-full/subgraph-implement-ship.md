# Subgraph: implement-ship

**Theme:** implement według planu → lokalny check → commit → push → open PR.  
**Mode mix:** AGENT SO implement; DET git/PR. Jedyna ciężka entropia kodu.

## Flow

```mermaid
flowchart TD
  A([enter: ticket + plan + branch]) --> B[AGENT SO: implement]
  B --> C{SO ok + files?}
  C -->|empty / ok:false| B
  C -->|ok| D[DET: local lint / test if configured]
  D --> E{green?}
  E -->|no| F[AGENT SO: light fix once]
  F --> D
  E -->|yes| G[DET: stage + commit]
  G --> H[DET: push origin]
  H --> I[DET: open PR — Closes N + plan summary]
  I --> J([leave: PR open])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class D,G,H,I det
  class B,F agent
```

## Notes

- **Implement = entropy sink.** Tylko tu (i light fix) wolno przepisywać product code.
- **Plan is input, not gospel.** Agent może odstąpić z uzasadnieniem w SO summary.
- **Optimistic local loop.** Jeden light fix; zakładamy, że lokalne checki szybko wracają na zielono.
- **Coder ceiling = open PR.** Implementer nie merguje.
- **DET owns git.** Commit message z ticket ID; push; PR template z `Closes #N`.
- **One ticket, one PR.**
- **Handoff:** `{pr_url, branch, head_sha, summary}`.

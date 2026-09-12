# Subgraph: worktree-implement

**Theme:** świeży git worktree + DevAgent → commit/push/open PR; sufit = `workflow:validating`.  
**Mode mix:** DET worktree/git + AGENT implement slot.

## Flow

```mermaid
flowchart TD
  A([enter: stage=implementing|fixing]) --> B[DET: create/reuse worktree + branch]
  B --> C[DET: write pin.worktree/branch]
  C --> D[AGENT: DevAgent in worktree]
  D --> E{SO ok + local tests?}
  E -->|fail / empty| F([leave: handoff hitl escape])
  E -->|ok| G[DET: commit + push + open PR]
  G --> H[DET: pin.pr_url + label → validating]
  H --> I([leave: advance validating])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef ag fill:#2a2a1a,stroke:#b8a03a,color:#fff8e8
  class B,C,G,H det
  class D ag
```

## Notes

- **Sandbox = worktree.** Host jest granicą; danger-mode świadomy.
- **Coder ceiling.** DevAgent nie merge'uje i nie ustawia `in_review`.
- **Handoff:** `{pr_url, branch}` → spine `validating`.

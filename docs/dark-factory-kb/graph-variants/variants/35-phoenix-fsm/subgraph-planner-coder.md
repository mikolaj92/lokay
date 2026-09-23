# Subgraph: planner-coder

**Theme:** stała oś **Planner → Coder** (Watcher label SM). Agenty = liście SO; nie flipują labels, nie otwierają PR.  
**Mode mix:** DET orchestracja kolejności + AGENT leaves (Planner, Coder).

## Flow

```mermaid
flowchart TD
  A([enter: from watcher-labels — ai:in-progress + branch]) --> B[DET: load issue body + context]
  B --> C[AGENT: Planner — plan SO]
  C --> D{plan structured + actionable?}
  D -->|no / empty| E[DET: receipt plan_reject]
  E --> Z0([leave: fail → tester or failed])
  D -->|yes| F[DET: write plan artifact to worktree]
  F --> G[AGENT: Coder — implement SO against plan]
  G --> H{diff non-empty + on branch?}
  H -->|no| I[DET: receipt empty_diff]
  I --> Z1([leave: fail])
  H -->|yes| J[DET: stage commits on phoenix/issue-N]
  J --> K([leave: handoff tester-baseline])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef ag fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,F,J det
  class C,G ag
  class E,I,Z0,Z1 bad
```

## Notes

- **SM order is law.** Watcher label SM: **Planner→Coder→Tester→PR**. Coder nie startuje przed planem; Tester nie przed Coderem.
- **Light agents.** Planner tylko planuje (structured output). Coder tylko implementuje względem planu. Żaden nie jest orkiestratorem tool-callingiem całego grafu (SOUL: lekkie, wąskie agenty).
- **DET owns git.** Branch, commit message template, paths allowlist — skrypt. AGENT produkuje diff / pliki.
- **Meat ≡ AI.** Człowiek-klepacz może wypełnić ten sam slot Planner albo Coder bez zmiany krawędzi.
- **Handoff contract.** `{plan_artifact, branch, commit_sha?}` albo `{fail: plan_reject|empty_diff}`.

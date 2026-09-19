# Subgraph: pr-revise

**Theme:** **PR Agent** + coder ceiling `ai:review`; pętla **failed → revise**; merge tylko człowiek → `ai:done`.  
**Mode mix:** DET open-PR / label flips + AGENT leaf (PR body); HITL merge.

## Flow

```mermaid
flowchart TD
  A([enter: tester OK | fail path]) --> B{path}
  B -->|OK| C[AGENT: PRAgent — title/body SO]
  C --> D[DET: push branch phoenix/issue-N]
  D --> E[DET: gh pr create Closes N]
  E --> F[DET: flip ai:in-progress → ai:review]
  F --> G([leave: HOLD human merge])
  G -->|merge| H[DET: ai:done]
  G -->|re-label ai:revise| I([leave: re-enter watcher])
  B -->|fail| J[DET: flip → ai:failed + comment evidence]
  J --> K{AUTO_REVISE budget?}
  K -->|yes| L[DET: flip → ai:revise]
  L --> I
  K -->|no| M([leave: ESCAPE failed receipt])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef ag fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  classDef hitl fill:#3a3a1a,stroke:#b8a03a,color:#fff8e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class D,E,F,H,J,K,L det
  class C ag
  class G hitl
  class M bad
```

## Notes

- **Coder ceiling.** Sukces = otwarty PR + `ai:review`. Merge **nie** jest w kompetencji Watchera ani agenta (MergePolicy default **Off**).
- **PR Agent = leaf.** Pisze tytuł/opis; `gh pr create` i flip label = DET.
- **Revise loop.** `ai:failed` → (budget) `ai:revise` → Watcher od `subgraph-watcher-labels`. Cap = escape z evidence.
- **Human path.** Merge → `ai:done`. Komentarze review mogą wrócić przez ręczne `ai:revise`.
- **Handoff contract.** `{pr_url, label: ai:review}` | `{label: ai:revise, budget_left}` | `{label: ai:failed, terminal: true}`.

# Subgraph: intake

**Theme:** enter PM → pick one labeled job → normalize ticket → occupancy gate.  
**Mode mix:** pure DET. No planner, no coder here.

## Flow

```mermaid
flowchart TD
  A([enter subgraph]) --> B[DET: authenticate / enter PM]
  B --> C[DET: pick_one_labeled ready-for-agent]
  C --> D{one actionable?}
  D -->|none| E[DET: record none / idle]
  E --> Z([leave: idle])
  D -->|one| F{repo occupied? K=1}
  F -->|live launch| G[DET: defer]
  G --> Z
  F -->|free| H[DET: normalize ticket fields]
  H --> I[DET: derive branch name + base_ref]
  I --> J[DET: ensure clean workspace / worktree signal]
  J --> K([leave: ticket + branch context])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,E,G,H,I,J det
```

## Notes

- **Label = start.** Tylko `ready-for-agent` / `ai:ready` (operator). Zero „weź z czatu”.
- **K=1 occupancy.** Jeden live launch na repo; defer zamiast równoległego chaosu.
- **Normalize once.** Title, ID, acceptance hints, links → stabilny payload dla plan leaf.
- **Fail closed.** Auth / pick fail → stop; nie wymyślaj roboty.
- **Handoff contract.** Output = `{ticket, branch_hint, base_ref}` dla subgraph-plan.
- **Polish:** drzwi wejściowe są skryptem — człowiek/agent wchodzi dopiero przy planie.

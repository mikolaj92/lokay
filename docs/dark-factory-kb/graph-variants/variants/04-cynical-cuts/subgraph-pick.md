# Subgraph: pick

**Theme:** etykieta → jeden issue → branch. Nic więcej.  
**Mode mix:** 100% DET. Zero agenta. Zero „wybieram z czatu”.

## Flow

```mermaid
flowchart TD
  A([enter]) --> B[DET: list issues with ready-for-agent]
  B --> C{any?}
  C -->|no| Z([leave: none])
  C -->|yes| D[DET: pick exactly one K=1]
  D --> E{ticket has acceptance + verify?}
  E -->|no| F[DET: skip — do not invent work]
  F --> Z
  E -->|yes| G[DET: worktree_add / branch from ticket id]
  G --> H([leave: issue + branch])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,D,F,G det
```

## Notes

- **Label = start.** Bez `ready-for-agent` / `ai:ready` nie ma wejścia. Chat nie jest intake.
- **K=1.** Jeden ticket. Nie katalog, nie batch, nie „przy okazji sąsiad”.
- **Underspecified = skip.** Brak acceptance / verification → wyjście. Nie plan-leaf, nie enrich, nie limbo label.
- **Branch name = skrypt.** Z ID ticketa. Człowiek/agent nie wymyśla nazwy.
- **CUT vs inni:** auth theatre jako osobny węzeł, normalize fields, ensure clean workspace, occupancy/orphan/defer FSM — nie rysujemy. Albo worktree się uda, albo fail closed.
- **Handoff:** `{issue_id, branch, base_ref}` albo `none`.

# Subgraph: plan-approve

**Theme:** Drake plan (LLM leaf) → approval gate HITL/code.  
**Mode mix:** AGENT plan + DET/HITL approve. Zero merge.

## Flow

```mermaid
flowchart TD
  A([enter: stage=plan]) --> B[DET: pack issue context / constraints]
  B --> C[AGENT: Drake plan SO — scope, files, risks, verify plan]
  C --> D[DET: validate plan schema]
  D --> E{schema ok?}
  E -->|no| F{attempts left?}
  F -->|yes| C
  F -->|no| G([leave: hold — bad plan])
  E -->|yes| H{approval gate}
  H -->|HITL deny / timeout| I([leave: denied — idle])
  H -->|code policy deny| I
  H -->|approve| J[DET: stamp approved plan + stage=build]
  J --> K([leave: approved → spine])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class B,D,J det
  class C agent
  class G,I,K stop
```

## Notes

- **Plan is bounded SO.** Scope, touched paths, test commands, risks — nie swobodny esej. Schema fail = retry albo hold.
- **Approve ≠ merge.** Gate zatrzymuje *ryzykowne wejście w build*; nie klik merge.
- **HITL first-class.** Konfigurowalna zgoda (UI / reaction / code allowlist). Alfred „nie merguje własnych PR by default” — ta sama filozofia na approve.
- **Engine = DET route.** Claude/Codex/OpenCode wypełnia slot Drake; routing nie jest promptem „wybierz model”.
- **Handoff.** `{plan_so, approved:true, stamp}` | `{approved:false, reason}`.

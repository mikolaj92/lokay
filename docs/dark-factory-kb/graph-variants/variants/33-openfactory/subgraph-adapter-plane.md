# Subgraph: adapter-plane

**Theme:** Pluggable adapter axes — tracker / board / forge / CI / sandbox / notifier (agent axis → osobny liść).  
**Mode mix:** DET I/O. Swap implementacji bez przełączania grafu.

## Flow

```mermaid
flowchart TD
  A([enter: adapter op scheduled]) --> B[DET: resolve axis + plugin]
  B --> C{axis?}
  C -->|tracker| T[DET: fetch issue / work item]
  C -->|board| BD[DET: column / claim / labels]
  C -->|forge| F[DET: branch / commit / push / open_pr]
  C -->|ci| CI[DET: trigger / poll checks]
  C -->|sandbox| S[DET: provision Docker worker box]
  C -->|notifier| N[DET: stall options → human channel]
  C -->|agent| FORBID[DET: refuse — use agent-leaf]
  T --> D{ok?}
  BD --> D
  F --> D
  CI --> D
  S --> D
  N --> D
  D -->|ok| OK[DET: write adapter result + refs]
  D -->|fail / timeout| NO[DET: write fail enum + retry policy]
  OK --> OUT([leave: resume temporal-spine])
  NO --> OUT
  FORBID --> OUT

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef warn fill:#3a1a1a,stroke:#a05050,color:#ffe8e8
  class B,T,BD,F,CI,S,N,OK,NO det
  class FORBID warn
```

## Notes

- **Osie, nie monolit.** GH Issues+Projects / Jira / Azure DevOps to **tracker+board** pluginy. GitHub/GitLab = forge. Zamiana = nowy adapter, ten sam FSM.
- **Idempotent keys.** Ponowny `open_pr` / `claim` nie duplikuje PR ani double-claim przy replay.
- **Agent axis ≠ ten subgraph.** Wywołanie `agent` stąd jest refuse — entropy idzie przez `subgraph-agent-leaf.md`, żeby silnik (Claude/Codex/…) był jawnie liściem.
- **Sandbox przed spend.** Provision box jest DET; `box prove` żyje w prove-review-merge, ale box ref pochodzi stąd.
- **Notifier = HITL surface.** Stall z executable options → człowiek; nie chat-loop w RAM workera.
- **Handoff contract.** Leave = `{axis, op, ok, refs, reason?, attempts}` → zapis w run state.

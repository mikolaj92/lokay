# Subgraph: sqlite-dag

**Theme:** SQLite DAG = źródło prawdy; supervisor / executor **DET** — schedule + apply, zero LLM.  
**Mode mix:** 100% DET. Runners tylko yield.

## Flow

```mermaid
flowchart TD
  A([enter: init / resume session]) --> B[DET: open .dagain/state.sqlite]
  B --> C[DET: load nodes + deps + mailbox]
  C --> D{mailbox pause/cancel?}
  D -->|cancel| Z([leave: session cancel])
  D -->|pause| Y([leave: paused — wait resume])
  D -->|ok| E[DET: select ready nodes — deps done]
  E --> F{ready empty?}
  F -->|yes + all terminal| G([leave: session done / pr path])
  F -->|yes + blocked checkpoint| H([yield: checkpoint-pr])
  F -->|yes + exhausted| I([leave: idle / escalate])
  F -->|no| J[DET: build fresh packet per node]
  J --> K([yield: runner-agents])
  K --> L[DET: parse propose next]
  L --> M{proposal valid?}
  M -->|no| N[DET: mark fail / retry policy]
  M -->|yes| O[DET: APPLY setStatus / addNodes / kv]
  N --> P[DET: checkpoint write + history]
  O --> P
  P --> C

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef store fill:#1a1a2a,stroke:#6a6ab8,color:#e8e8ff
  class B,C,E,J,L,N,O,P det
  class B store
```

## Notes

- **Graph-is-SQLite.** Topologia i stan żyją w tabelach — nie w prompcie „zrób następny krok”.
- **Supervisor owns the loop.** Wybór ready, apply, retry counters, mailbox — wyłącznie DET.
- **Apply is load-bearing.** Runner nigdy nie pisze `nodes.status` sam; tylko propozycja → walidacja → apply + `kv_history`.
- **Inspectable.** `sqlite3 .dagain/state.sqlite "SELECT * FROM nodes"` = debug; brak Redis/sofy zewnętrznej.
- **Klepacz bind.** Seed nodes: `plan_issue`, `implement` (+ opc. breakdown), `verify`, `integrate_pr`, `checkpoint_review` — nie feature-mill catalogue.
- **Handoff contract.** Yield = `{node_ids[], packet_paths[], session_id}`; resume = `{node_id, proposal, runner_id, ok}` → apply result `{applied|rejected, reason?}`.

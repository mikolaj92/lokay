# Subgraph: det-walk

**Theme:** `PipelineRunner` chodzi po krawędziach; parallelogram = tool/shell; diamond = warunek.  
**Mode mix:** DET spine. Wzywa box-llm tylko gdy natrafi na `shape=box`.

## Flow

```mermaid
flowchart TD
  A([enter: walk plan]) --> B[DET: PipelineRunner next node]
  B --> C{node shape?}
  C -->|parallelogram pick| D[DET: pick_one_labeled]
  D --> E{one issue?}
  E -->|none| IDLE([leave: idle])
  E -->|one| F[DET: occupancy K=1 / worktree_add]
  C -->|parallelogram test| G[DET: run_tests]
  G --> H{green?}
  H -->|red| R[DET: bounded retry budget?]
  R -->|yes resume box| BOX([yield: box-llm repair])
  R -->|exhausted| SKIP([leave: skip])
  H -->|green| B
  C -->|parallelogram git/pr| I[DET: commit + push + open_pr]
  I --> B
  C -->|parallelogram merge| J[DET: merge_policy atom]
  J --> HITL([yield: hitl-exit])
  C -->|diamond| K[DET: evaluate condition]
  K --> B
  C -->|box| BOX2([yield: box-llm])
  C -->|hexagon| HITL
  C -->|Msquare| DONE([leave: done])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,D,F,G,I,J,K,R det
```

## Notes

- **Runner nie myśli.** Kolejność = krawędzie DOT + wynik diamond. Żaden AGENT nie wybiera „co dalej”.
- **Parallelogram = skrypt.** pick / worktree / test / commit / push / open_pr / merge_policy — atomy DET z WORKING_KLEPACZ_GRAPH.
- **Yield, nie orkiestracja.** Natrafienie na box/hexagon = przekazanie do subgraphu liścia; po SO/HITL resume na tej samej krawędzi.
- **Checkpoint.** Po każdym węźle stan walki; restart bez ponownego „agent odkrywa świat”.
- **K=1 occupancy.** Live launch → defer; dead wrapper → finish_orphan_PR; free → worktree — wszystko DET diamond/parallelogram.
- **Handoff contract.** Yield box = `{node_id, prompt_ref, schema, ticket_ctx}`; yield hitl = `{pr, review_verdict, policy}`; leave idle/skip/done = receipt.

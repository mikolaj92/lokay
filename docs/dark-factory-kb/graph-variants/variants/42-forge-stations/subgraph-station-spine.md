# Subgraph: station-spine

**Theme:** LangGraph StateGraph jako DET maszyna typowanych stacji.  
**Mode mix:** wyłącznie DET — enum stacji, krawędzie, checkpointy, budgety. Zero LLM w ciele spine.

## Flow

```mermaid
flowchart TD
  A([enter: webhook / daemon tick]) --> B[DET: claim ticket K=1]
  B --> C{claimed?}
  C -->|none / busy| IDLE([leave: idle])
  C -->|ok| D[DET: load checkpoint / journal]
  D --> E{current TypedStation?}
  E -->|plan| P([leave → plan-station])
  E -->|impl| I([leave → impl-station])
  E -->|ci| CI([leave → ci-review-station])
  E -->|review| R([leave → ci-review-station])
  E -->|done| DONE([leave: done])
  E -->|failed / budget| ESC([leave: escalate])

  P -.-> F[DET: on return — assert SO ok + advance enum]
  I -.-> F
  CI -.-> F
  R -.-> F
  F --> G[DET: persist checkpoint + external journal]
  G --> E

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class B,D,F,G det
  class IDLE,ESC stop
```

## Notes

- **TypedStation enum.** `plan | impl | ci | review | done | failed`. Przejścia tylko przez DET `advance(station, gate_result)` — nie przez tekst z modelu.
- **Agent nie routuje.** Liść SO zwraca structured payload dla *bieżącej* stacji; spine decyduje o krawędzi. Zakaz `next_station` w SO.
- **Checkpoint + journal.** LangGraph checkpointer trzyma stan grafu; osobny journal efektów (Jira comment id, PR number, Podman run id) dla idempotencji / replay.
- **Budżety.** `ci_repair_n`, occupancy K=1, timeout stacji — fail closed → `failed` / escalate, nie limbo.
- **Handoff contract.** `{ticket, station, checkpoint_id, worktree_or_podman_ref, artifacts[]}` albo idle/escalate.

## Station advance (DET)

```json
{
  "from": "plan",
  "gate": "human_approve_plan",
  "result": "approved",
  "to": "impl"
}
```

```json
{
  "from": "ci",
  "gate": "ci_status",
  "result": "red",
  "repair_used": 2,
  "repair_budget": 3,
  "to": "ci"
}
```

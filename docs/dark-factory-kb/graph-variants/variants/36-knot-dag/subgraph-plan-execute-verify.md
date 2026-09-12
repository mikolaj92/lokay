# Subgraph: plan-execute-verify

**Theme:** role **plan → execute → verify → integrate** jako węzły DAG (nie fazy w LLM-orkiestratorze).  
**Mode mix:** AGENT w liściach ról; DET edges / retry / escalate-to-plan.

## Flow

```mermaid
flowchart TD
  A([enter: PEV subgraph / seeded nodes]) --> B[node: plan — runner]
  B --> C{plan ok?}
  C -->|no| X[DET: escalate / checkpoint]
  C -->|yes| D[DET: materialize execute nodes + deps]
  D --> E[node: execute — runner pool]
  E --> F{execute ok?}
  F -->|retry budget| E
  F -->|exhausted| G[DET: escalate → nearest plan replan]
  F -->|ok| H[node: verify — runner / shellVerify]
  H --> I{verify ok?}
  I -->|no + budget| G
  I -->|no + exhausted| X
  I -->|yes| J[node: integrate — DET+thin runner]
  J --> K{integrate → PR ready?}
  K -->|yes| L([leave: ship → checkpoint-pr])
  K -->|no| X
  G --> B

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class D,F,G,I,J,K det
  class B,E,H agent
  class X stop
```

## Notes

- **SQLite executor owns PEV.** „Owns plan/execute/verify” = supervisor trzyma pętlę i edges; runners tylko wypełniają węzły.
- **Plan is a node.** Replan = nowy / zresetowany plan node + history w `kv_history` — nie „agent zmienił zdanie w chacie”.
- **Execute may fan-out.** Niezależne implement nodes OK; klepacz default K=1 / wąski łańcuch.
- **Verify first-class.** `shellVerify` / test command z planu; fail → retry → escalate-to-plan (dagain failure model), nie ciche „napraw świat”.
- **Integrate ≠ merge.** Integrator składa artefakty / otwiera PR; merge zostaje HITL / MergePolicy.
- **Reviewer ≠ implementer.** Opcjonalny `pr_review` runner przed integrate — osobne siedzenie.
- **Handoff contract.** Pass = `{phase, node_id, artefacts[], verify: ok}`; replan = `{reset_to: plan_id, reason}`; exhaust = `{ok:false, reason: "pev_exhausted"}`.

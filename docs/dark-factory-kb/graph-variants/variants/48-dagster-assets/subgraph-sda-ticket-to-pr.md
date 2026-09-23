# Subgraph: sda-ticket-to-pr

**Theme:** Software-Defined Assets — stałe deps `ticket → branch → diff → tests → pr`.  
**Mode mix:** DET spine; tylko `diff` (i opcjonalnie plan/repair) ma AGENT op leaf.

## Flow

```mermaid
flowchart TD
  A([enter: job selection for partition]) --> T[DET asset: ticket hydrate]
  T --> BR[DET asset: branch / worktree claim]
  BR --> DF[asset: diff — LLM op leaf]
  DF --> TE[DET asset: tests runner]
  TE --> CHK{AssetCheck tests.ok?}
  CHK -->|fail + budget left| RP[asset: repair — LLM op leaf bounded]
  RP --> TE
  CHK -->|fail budget 0| FAIL[DET: materialize fail / escalate]
  CHK -->|ok| PR[DET asset: open_pr]
  PR --> OUT([leave: pr AssetMaterialization])
  FAIL --> OUT2([leave: failed run])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class T,BR,TE,CHK,PR,FAIL det
  class DF,RP agent
```

## Notes

- **Deps są programem.** Kolejność nie jest promptem — graf AssetKey jest fixed w Definitions.
- **Materializacja = checkpoint.** Restart joba pomija już zmaterializowane upstream (Dagster IO manager / versioning wg setupu).
- **`tests` ≠ LLM.** Skrypt / pytest / CI wrapper; wynik strukturalny dla AssetCheck.
- **Coder ceiling = `pr`.** Open PR kończy rolę implementera; review/merge to osobny subgraph.
- **Bounded repair.** Osobny asset / multi-asset z limitem N; nie nieskończona pętla w jednym op.
- **Handoff.** Leave = `{partition, AssetKey:pr, metadata.pr_url}` → materialize-merge.

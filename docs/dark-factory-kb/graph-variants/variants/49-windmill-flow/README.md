# 49 — Windmill flow compose

**Persona:** `windmill-flow compose` — [Windmill](https://www.windmill.dev/) **scripts + flows** jako DET atoms; topologia ticket→PR żyje w flow YAML/UI; **LLM tylko w typowanych script leaves**; **approval** = HITL; sufit kodera = **open PR**.

**Approach:** `compose`. Nie monolit — składamy małe skrypty (Python/TS/Bash) w flow. Distinct od Prefect (47) i Temporal (46): Windmill = self-hostable script hub + flow DAG + native approval steps.

## Design notes

- **Flow owns next step.** Edges w flow; 0 tokenów orkiestracji.
- **Scripts = atoms.** DET: claim, worktree, test, git, `gh pr create`. AGENT: typed `plan` / `implement` scripts z SO.
- **Approval step = HITL.** Native Windmill approval — nie LLM-judge merge.
- **Meat ≡ AI** w tym samym script leaf.
- **NOT L5.** MergePolicy default **Off**.
- **Cel (SOUL):** zdjąć klepanie ticket→PR; energia na architekturę.

## Top-level flowchart

```mermaid
flowchart TD
  START([labeled issue / webhook]) --> FM[subgraph: flow-modules]
  FM -->|invalid flow| IDLE([idle / config])
  FM -->|run started| SL[subgraph: script-leaves]
  SL -->|need plan/impl| SL
  SL -->|DET gates fail| IDLE
  SL -->|ready review| AP[subgraph: approval-hitl]
  AP -->|reject| SL
  AP -->|approve| PR[subgraph: pr-ceiling]
  PR -->|PR open| HOLD([MergePolicy Off — human])
  HOLD --> DONE([done])

  classDef sub fill:#1a2a3a,stroke:#3a7ab8,color:#e8f2ff
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class FM,SL,AP,PR sub
  class IDLE,HOLD stop
  class DONE ok
```

**DET vs AGENT**

| Layer | Mode | Uwaga |
|-------|------|-------|
| Flow DAG / webhook trigger | DET | agent nie pickuje |
| DET scripts (claim/wt/test/git/gh) | DET | atoms |
| Typed plan/implement scripts | AGENT leaf | SO only |
| Approval step | HITL | nie LLM judge |
| open PR | DET | coder ceiling |
| merge | HITL / policy | default Off |

## Index of subgraphs

| File | Theme |
|------|--------|
| [subgraph-flow-modules.md](./subgraph-flow-modules.md) | flow = program |
| [subgraph-script-leaves.md](./subgraph-script-leaves.md) | DET atoms + LLM leaves |
| [subgraph-approval-hitl.md](./subgraph-approval-hitl.md) | Windmill approval |
| [subgraph-pr-ceiling.md](./subgraph-pr-ceiling.md) | open PR + MergePolicy |

## Mapowanie Windmill → klepacz

| Windmill | Klepacz |
|----------|---------|
| Flow + webhook/label | DET intake |
| Script modules | unix-like atoms |
| LLM script leaf | plan/implement SO |
| Approval | HITL plan/PR |
| `gh` script | PR ceiling |
| LLM as flow router | **FORBIDDEN** |

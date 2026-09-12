# Subgraph: llm-op-leaf

**Theme:** LLM siedzi **wewnątrz** jednego op / `compute_fn` assetu — wypełnia SO; nie routuje joba ani sensora.  
**Mode mix:** AGENT leaf only. Job/SDA decyduje *kiedy*; op decyduje *jak* w budżecie.

## Flow

```mermaid
flowchart TD
  A([enter: asset op scheduled]) --> B[DET: load prompt_ref + schema + ticket_ctx + IO]
  B --> C[DET: enforce timeout / token / tool budget]
  C --> D{leaf kind?}
  D -->|plan| P[AGENT SO: plan files / tests / stop_if]
  D -->|diff implement| I[AGENT SO: edit in worktree]
  D -->|repair| F[AGENT SO: bounded fix from failure_log]
  D -->|pr_review optional| R[AGENT SO: critical review verdict]
  P --> E{ok structured?}
  I --> E
  F --> E
  R --> E
  E -->|ok:true| OK[DET: yield AssetMaterialization + artifact]
  E -->|ok:false| NO[DET: fail op / reason enum]
  OK --> OUT([leave: resume SDA downstream])
  NO --> OUT
  C -->|budget hard stop| KILL[DET: raise / fail materialization]
  KILL --> OUT

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,C,OK,NO,KILL det
  class P,I,F,R agent
```

## Notes

- **Not a router.** Model nie woła `materialize`, nie zmienia job selection, nie przestawia label FSM, nie merge’uje.
- **One asset, one leaf.** Plan / implement / repair / review = osobne AssetKeys (osobne materializacje). Reviewer ≠ implementer.
- **Structured output.** `ok:true` + artefakt albo `ok:false` + reason enum — brak limbo chat.
- **Op retry ≠ blind re-prompt.** Infra retry przy crashu; semantyka „napraw testy” = nowy asset `repair` zaplanowany przez deps/check po fail `tests`.
- **Meat ≡ AI.** Ten sam schema seat pod assetem.
- **Handoff.** Leave = materialization metadata `{ok, artifact_ref, reason?, usage}` → downstream DET.

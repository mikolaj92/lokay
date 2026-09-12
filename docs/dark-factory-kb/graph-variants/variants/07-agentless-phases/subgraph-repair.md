# Subgraph: repair

**Theme:** faza 2 Agentless — generowanie kandydatów patchy (multi-sample).  
**Mode mix:** DET context pack + jeden AGENT SO slot `repair_samples`. Zero tool-loop; zero apply/test w tym podgrafie.

## Flow

```mermaid
flowchart TD
  A([enter: locs + ticket_ctx + worktree]) --> B[DET: pack context snippets from locs]
  B --> C[AGENT SO: repair_samples N]
  C --> D{ok && samples ≥ 1?}
  D -->|false| X([leave: skip / fail])
  D -->|true| E[DET: normalize patches — path check, reject binary/out-of-locs]
  E --> F{any sample kept?}
  F -->|no| X
  F -->|yes| G([leave: samples[] for validate])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,E det
  class C agent
```

## Notes

- **Multi-sample, jeden slot.** Jedno wywołanie SO (temperature/N) → `samples[1..N]` z `diff` lub `edits[]`. Model nie iteruje „spróbuj toola”.
- **Repair ≠ validate.** Tu **nie** uruchamiamy testów i **nie** commitujemy. Selekcja jest fazą 3 (DET).
- **Kontekst z locs.** DET pakuje tylko pliki/elementy z localize — wąskie okno, nie cały repo dump.
- **Guardrails DET po SO.** Patch poza `files[]`, touch `stop_if` paths, pusty diff → drop sample. Zostaje lista czysta dla validate.
- **Bounded N.** Domyślnie N=3..5 (koszt/skuteczność jak w paperze); nie „generuj aż przejdzie”.
- **Meat ≡ AI.** Człowiek może ręcznie dostarczyć samples w tym samym schema; faza nie wie.
- **Handoff.** `{samples: [{id, summary, edits|diff}], locs, test_command, worktree}` albo skip.

## Structured output — `repair_samples`

```json
{
  "ok": true,
  "samples": [
    {
      "id": "s1",
      "summary": "fix null check in Foo.bar",
      "edits": [
        {"file": "src/foo.py", "unified_diff": "--- a/src/foo.py\n+++ b/src/foo.py\n@@ ..."}
      ]
    },
    {
      "id": "s2",
      "summary": "alt: early return",
      "edits": [{"file": "src/foo.py", "unified_diff": "..."}]
    }
  ]
}
```

```json
{ "ok": false, "reason": "cant_comply|needs_split|blocked_path|empty_samples" }
```

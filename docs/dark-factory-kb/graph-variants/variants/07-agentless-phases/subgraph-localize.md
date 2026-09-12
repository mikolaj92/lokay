# Subgraph: localize

**Theme:** faza 1 Agentless — hierarchiczne zawężenie miejsca zmiany.  
**Mode mix:** DET intake (pick / worktree) + jeden AGENT SO slot `localize_hierarchy`. Zero ReAct, zero git w slocie.

## Flow

```mermaid
flowchart TD
  A([enter: daemon tick]) --> B[DET: pick_one_labeled]
  B --> C{one issue?}
  C -->|none| IDLE([leave: idle])
  C -->|one| D[DET: occupancy K=1 / worktree_add]
  D --> E{worktree ok?}
  E -->|defer / orphan| IDLE
  E -->|ready| F[DET: pack repo skeleton — tree / symbols index]
  F --> G[AGENT SO: localize_hierarchy]
  G --> H{ok?}
  H -->|false| SKIP([leave: skip — underspecified / too_large])
  H -->|true| I[DET: assert locs ⊆ repo + non-empty]
  I --> J{locs valid?}
  J -->|no| SKIP
  J -->|yes| K([leave: locs + ticket_ctx + worktree])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,D,F,I det
  class G agent
```

## Notes

- **Faza stała.** Po pick/worktree zawsze slot localize — nie „agent decyduje czy szukać”.
- **Hierarchia (kanon Agentless).** SO zwraca warstwy: `files[]` → opcjonalnie `elements[]` (symbol / zakres linii). Najpierw pliki, potem elementy wewnątrz.
- **LLM bez narzędzi.** Slot dostaje skeleton/index + treść ticketa; **nie** woła shell/`grep` w pętli. Eksploracja = prompt + indeks DET, nie ACI.
- **DET assert.** Puste locs, ścieżki poza repo, `stop_if` overlap → `ok:false` / skip. Fail closed.
- **Ticket jasność.** Brak acceptance/verification w ticketcie może dać `reason: underspecified` — taniej niż ReAct limbo.
- **Handoff contract.** `{issue, worktree, locs: {files[], elements[]}, test_command}` albo idle/skip.

## Structured output — `localize_hierarchy`

```json
{
  "ok": true,
  "files": ["src/foo.py", "tests/test_foo.py"],
  "elements": [
    {"file": "src/foo.py", "symbol": "Foo.bar", "lines": [40, 88]}
  ],
  "rationale": "short why these loci",
  "confidence": "high"
}
```

```json
{ "ok": false, "reason": "underspecified|too_large|dangerous|no_loci" }
```

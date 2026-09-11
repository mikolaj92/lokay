# Subgraph: ralph-tick

**Theme:** jedno przejście **implement → review** (ciało pętli Ralph).  
**Mode mix:** AGENT SO ×2 (osobne role) + DET bump licznika / lokalny test. **Bez** git push/PR w środku ticka.

## Flow

```mermaid
flowchart TD
  A([enter: worktree + acceptance + tick state]) --> B[DET: ralph_tick_used += 1]
  B --> C[AGENT SO: implement_tick]
  C --> D{ok + files?}
  D -->|ok:false needs_arch| X1([leave: signal needs_arch_human])
  D -->|ok:false other| X2([leave: signal reject/skip to gate])
  D -->|ok| E[DET: run test_command]
  E --> F{green?}
  F -->|red| G[AGENT SO: implement_tick repair hint in same tick?]
  G -->|optional one local fix| E
  F -->|red after local| H[pack failure log]
  H --> I[AGENT SO: review_tick on red]
  F -->|green| I2[AGENT SO: review_tick]
  I --> J[collect loop_status]
  I2 --> J
  J --> K([leave: tick result → loop-gate])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,E det
  class C,G,I,I2 agent
  class X1,X2 bad
  class K ok
```

## Notes

- **Tick = para ról, nie monolit.** `implement_tick` i `review_tick` to osobne liście SO. Ten sam model w obu siedzeniach jest OK organizacyjnie, ale **kontrakt roli** jest rozdzielony (reviewer ≠ stempel implementera).
- **Licznik DET przed pracą.** Bump na wejściu ticka — agent nie „prosi o darmowy tick”.
- **Lokalny test jest wyrocznią postępu**, nie zastępuje `loop_status`. Zielony ≠ `LOOP_COMPLETE`; complete ogłasza tylko review względem acceptance.
- **Ceiling kodera w ticku = working tree.** Żadnego `git push` / `gh pr create` tutaj — to `subgraph-git-pr.md` po bramce.
- **Czerwony lokalny.** Review nadal dostaje log (żeby ustawić `continue` z powodami albo `reject`); nie otwieramy PR na czerwono później.
- **Handoff.** `{tick, implement_so, test_green, review_so{verdict, loop_status, reasons, risk, arch_flags}}`.

## Structured output

### implement_tick

```json
{
  "ok": true,
  "tick": 2,
  "summary": "wire handler + test",
  "files_touched": ["src/x.ts", "src/x.test.ts"],
  "tests_run_locally": true,
  "acceptance_progress": ["done: handler returns 200", "todo: error path"]
}
```

### review_tick

```json
{
  "verdict": "approve_progress",
  "loop_status": "continue",
  "reasons": ["happy path ok; missing 404 case from acceptance"],
  "risk": "low",
  "arch_flags": []
}
```

`loop_status` ∈ `continue` | `LOOP_COMPLETE` | `needs_arch_human` | `reject`.

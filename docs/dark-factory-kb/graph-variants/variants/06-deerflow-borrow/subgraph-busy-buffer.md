# Subgraph: busy-buffer

**Theme:** **Busy follow-up buffer** — ConflictError nie = cichy drop.  
**Mode mix:** 100% DET (watcher + FIFO drain).

## Flow

```mermaid
flowchart TD
  A([enter: runs.create on thread]) --> B{ConflictError / already running?}
  B -->|no| GO([leave: run accepted — handoff agent-leaf])
  B -->|yes busy| C[DET: enqueue inbound into per-thread buffer]
  C --> D[DET: subscribe StreamBridge run_id until END_SENTINEL]
  D --> E[DET: drain FIFO batch ≤10]
  E --> F[DET: coalesce → single follow-up input block]
  F --> G[DET: runs.create next fire_and_forget]
  G --> H{more buffered?}
  H -->|yes| E
  H -->|no| GO2([leave: chain complete / idle])
  C --> L[DET: log THREAD_BUSY — no false user ferry on GitHub]

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class C,D,E,F,G,L det
```

## Notes

- **Problem (DeerFlow #4121).** Przy `multitask_strategy="reject"` drugi komentarz na zajętym threadzie → ConflictError → `_send_error(THREAD_BUSY_MESSAGE)`. Ale GitHub outbound jest **log-only**, więc komunikat „busy” idzie w log, a follow-up **ginie**. Człowiek myśli, że bot zignorował komentarz.
- **Fix pattern (buffer + drain + watcher).** Na busy: **kolejkuj** inbound per thread; watcher na `StreamBridge.subscribe(run_id)` do `END_SENTINEL` (push, zero poll `runs.get`); po zakończeniu **drain FIFO** (batch ~10), coalesce w jeden follow-up `runs.create`, naturalnie chainuje gdy >10.
- **Nie mylić z dedupe.** Dedupe (`delivery_id` / `message_id`) chroni przed **redelivery** tego samego eventu. Buffer chroni przed **nowym** komentarzem w trakcie lotu. Oba potrzebne.
- **Self-event vs busy.** Self-event = skip przed enqueue (nie buforujemy własnych `gh` echo). Busy = cudzy/human follow-up gdy run leci.
- **Klepacz mapping.** SOUL: free humans — nie zmuszaj człowieka do „wyślij jeszcze raz za 20 min”. DET babysitting concurrency zamiast cichego dropu.
- **Fail-closed.** Watcher timeout / bridge down → receipt `busy_buffer_orphan` + zostaw PR/issue bez udawania sukcesu; nie limbo labels.
- **Handoff contract.** `{buffered:true, queue_depth, active_run_id}` → później `{drained:n, next_run_id}` albo `{ok:false, reason: buffer_orphan|bridge_down}`.

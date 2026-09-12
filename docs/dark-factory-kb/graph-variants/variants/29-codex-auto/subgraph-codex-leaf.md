# Subgraph: codex-leaf

**Theme:** OpenAI Codex CLI (`codex exec`) jako **liść AGENT** — implement; nie orkiestrator.  
**Mode mix:** AGENT tylko w procesie CLI; branch name + stop + verify = DET konwencja / harness.

## Flow

```mermaid
flowchart TD
  A([enter: codex exec invoked]) --> B[AGENT: Codex CLI headless]
  B --> C{scope clear?}
  C -->|underspecified / dangerous / blocked_path| D[DET: ask-or-stop comment]
  D --> Z0([leave: skip — no limbo])
  C -->|in scope| E[AGENT SO: implement leaf]
  E --> F{ok?}
  F -->|false| D
  F -->|true| G[DET: run verification from issue]
  G --> H{local green?}
  H -->|no, attempts < N| I[AGENT SO: repair_code bounded]
  I --> G
  H -->|no, budget out| D
  H -->|yes| J[DET: commit on codex/issue-N]
  J --> K[DET: push branch]
  K --> L([leave: branch ready])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class D,G,J,K det
  class B,E,I agent
```

## Notes

- **Reuse fidelity.** Codex Auto = headless CLI w Actions: czyta issue, edytuje pliki, kończy. To nadal **liść** — nie flipuje stage-labeli fabryki ani merge policy.
- **Branch `codex/issue-N`.** Stała konwencja nazwy; jeden ticket → jeden branch. Occupancy DET w harness przed invoke.
- **Liść, nie orkiestrator.** Codex nie decyduje „uruchom następny workflow” ani „zmień MergePolicy”. Wynik = diff + branch / fail.
- **Ask-or-stop.** Auth, billing, migracje, deps poza Allowed → comment + stop (KLEPACZ), nie „ulepsz po drodze”.
- **Meat ≡ AI.** To samo siedzenie: headless Codex w CLI albo człowiek-klepacz w tym samym runner contract — graf bez zmian.
- **Bounded.** CLI flags / max turns / sandbox = budżet DET wokół liścia; wyczerpanie → skip + evidence.
- **Kontrakt SO (WORKING_KLEPACZ_GRAPH):** implement `{ok, summary, files_touched, tests_run}` — fail = `{ok:false, reason:enum}`.
- **Handoff contract.** `{branch: codex/issue-N, shas[], summary}` \| `{skip, reason}`.

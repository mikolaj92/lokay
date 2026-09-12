# Subgraph: claude-leaf

**Theme:** `anthropics/claude-code-action` jako **liść AGENT** — implement / Q&A / review; nie orkiestrator.  
**Mode mix:** AGENT tylko w action; branch name + stop = DET konwencja.

## Flow

```mermaid
flowchart TD
  A([enter: action invoked]) --> B[AGENT: Claude Code in runner]
  B --> C{mode detected}
  C -->|implement issue| D[AGENT SO: code changes]
  C -->|question / triage| E[AGENT SO: comment only]
  C -->|PR review| F[AGENT SO: review comments]
  D --> G{ok / clear scope?}
  G -->|underspecified / dangerous| H[DET: ask-or-stop comment]
  H --> Z0([leave: skip — no limbo])
  G -->|true| I[DET: commit on claude/issue-N]
  I --> J[DET: push branch]
  J --> K([leave: branch ready])
  E --> L([leave: comment done])
  F --> M([leave: review done])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class H,I,J det
  class B,D,E,F agent
```

## Notes

- **Reuse fidelity.** Action inteligentnie wybiera *tryb wykonania* (interactive / automation) z kontekstu workflow — to nadal **liść**: nie flipuje stage-labeli fabryki ani merge policy.
- **Branch `claude/issue-N`.** Stała konwencja nazwy; jeden ticket → jeden branch. Occupancy DET przed invoke.
- **Liść, nie orkiestrator.** Claude nie decyduje „uruchom następny workflow” ani „zmień MergePolicy”. Wynik = diff + branch / komentarz / fail.
- **Ask-or-stop.** Auth, billing, migracje, deps poza Allowed → comment + stop (KLEPACZ), nie „ulepsz po drodze”.
- **Meat ≡ AI.** To samo siedzenie: headless Claude w action albo człowiek-klepacz w tym samym runner contract — graf bez zmian.
- **Bounded.** `claude_args` (`--max-turns`, allowedTools) = budżet DET wokół liścia; wyczerpanie → skip + evidence.
- **Handoff contract.** `{branch: claude/issue-N, shas[], summary}` \| `{comment_only}` \| `{skip, reason}`.

# Subgraph: agent-leaf

**Theme:** headless agent jako **liść** — implement (+ opcjonalny review SO); meat ≡ AI.  
**Mode mix:** AGENT SO tylko w liściach; test/commit lokalne = DET.

## Flow

```mermaid
flowchart TD
  A([enter: cell ready]) --> B[AGENT SO: implement leaf]
  B --> C{ok?}
  C -->|false: underspecified / dangerous / blocked_path| D[DET: skip — no limbo]
  D --> Z([leave: skip])
  C -->|true| E[DET: run verification from issue]
  E --> F{local green?}
  F -->|no, attempts < N| G[AGENT SO: repair_code bounded]
  G --> E
  F -->|no, budget out| D
  F -->|yes| H[DET: stage + commit + push]
  H --> I{optional agent review?}
  I -->|yes| J[AGENT SO: pr_review leaf — no write]
  I -->|no / default thin| K([leave: branch pushed — ready for PR])
  J --> L{verdict}
  L -->|approve / low| K
  L -->|changes / high| G2[AGENT SO: pr_repair bounded max N]
  G2 --> H
  L -->|reject| D

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class E,H,D det
  class B,G,J,G2 agent
```

## Notes

- **Reuse fidelity.** ready-for-agent: headless Claude/Codex/OpenCode/Grok w worktree — *implement + review + PR*. Tu PR open jest DET na top-level; liść kończy na pushed branch (coder ≠ merge).
- **Liść, nie orkiestrator.** Agent dostaje structured output schema; nie routuje całego factory_pass. Fail = `{ok:false, reason:enum}` → skip bez park labels.
- **Meat ≡ AI.** To samo siedzenie: człowiek-klepacz albo model — graf i kontrakt SO bez zmian (SOUL).
- **Głupi i posłuszny.** Inteligentny klepacz „ulepszający po drodze” = ryzyko (KLEPACZ). Trzymaj się issue: In scope / Out / Ask-or-stop (auth, billing, migracje, deps).
- **Bounded repair.** max N na repair_code / pr_repair; potem skip + evidence — nie wieczne limbo.
- **Reviewer bez write (opc.).** `pr_review` SO: `{verdict, reasons[], risk}` — komentarz/werdykt, zero merge auth. `reject`/`high` → nigdy Always w merge-policy.
- **Kontrakty SO (WORKING_KLEPACZ_GRAPH):**
  - implement: `{ok, summary, files_touched, tests_run}`
  - pr_review: `{verdict: approve|changes|reject, reasons, risk: low|high}`
- **Handoff contract.** Output = `{branch, commit_shas, summary, review?}` → DET open PR `Closes #N`, albo `{skip, reason}`.

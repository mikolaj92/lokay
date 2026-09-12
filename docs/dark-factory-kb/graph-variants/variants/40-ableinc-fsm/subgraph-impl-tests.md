# Subgraph: impl-tests

**Theme:** liść **Implement** + **suite testów repo** w worktree; harness owns test gate.  
**Mode mix:** AGENT ImplementAgent + DET test suite.

## Flow

```mermaid
flowchart TD
  A([enter: HITL implement + worktree]) --> B[DET: ensure worktree clean + plan artifact visible]
  B --> C[AGENT: ImplementAgent — claude implement bypassPermissions]
  C --> D{diff non-empty on branch?}
  D -->|no| E[DET: receipt empty_diff]
  E --> Z0([leave: fail escape])
  D -->|yes| F[DET: run repo test suite in worktree]
  F --> G{tests exit}
  G -->|fail| H[DET: capture log + fail receipt]
  H --> I([leave: handoff draft-pr with fail evidence OR escape])
  G -->|pass| J[DET: capture pass receipt]
  J --> K([leave: handoff draft-pr])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef ag fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,F,H,J det
  class C ag
  class E,Z0 bad
```

## Notes

- **LLM only impl.** ImplementAgent pisze kod w worktree; **nie** pushuje, **nie** otwiera PR, **nie** flipuje labels.
- **Harness owns tests.** Komenda suite z configu repo; wynik (pass/fail + log excerpt) jedzie do draft PR body.
- **bypassPermissions** dotyczy sandboxa worktree — nie host git remote / GitHub write poza harnessem.
- **Fail ≠ silent.** Fail receipt zostaje; draft-pr może i tak otworzyć PR z evidence albo escape do HITL / re-ready (policy).
- **Handoff contract.** `{worktree, branch, test_status, test_log_excerpt}` albo `{fail: empty_diff}`.

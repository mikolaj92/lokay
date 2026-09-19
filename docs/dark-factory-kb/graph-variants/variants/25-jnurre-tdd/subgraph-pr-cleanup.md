# Subgraph: pr-cleanup

**Theme:** coder ceiling = `agent:pr-open`; revision z review PR; post-merge cleanup DET.  
**Mode mix:** DET open PR / labels / cleanup; HITL merge; AGENT tylko gdy revision wraca do TDD.

## Flow

```mermaid
flowchart TD
  A([enter: review approved / pr-open / merged]) --> B{event?}
  B -->|approved first time| C[DET: open PR Closes N + label agent:pr-open]
  C --> D([leave: PR open — MergePolicy Off])
  B -->|already pr-open| E{PR review / merge?}
  E -->|changes requested| F[DET: label → agent:revision]
  F --> G([leave: reenter tdd-implement])
  E -->|approve stay| D
  E -->|merged| H[DET: post-merge cleanup worktree + labels]
  H --> I[DET: strip agent* / mark done receipt]
  I --> Z0([leave: done])
  E -->|MergePolicy Classify|Always + green| J{policy allow?}
  J -->|yes| K[DET: merge + cleanup]
  K --> Z0
  J -->|no / Off| D

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class C,F,H,I,K det
  class D stop
  class Z0 ok
```

## Notes

- **Coder ceiling.** Sufit sandbox-pal = otwarty PR + `agent:pr-open`. Implementer / review liść **nie** merguje.
- **Default merge = Off.** Człowiek merguje; Classify|Always to opcjonalna polityka DET (KLEPACZ), nie persona LLM.
- **Revision z PR.** `pull_request_review: changes_requested` → DET stawia `agent:revision` → ten sam łańcuch TDD→review. Bez ukrytego goto w prompcie.
- **Post-merge cleanup.** Worktree remove, etykiety `agent*` zdejmowane, runner artifacts — skrypt GHA. Bez cleanup = wyciek komórek na self-hosted.
- **Meat ≡ AI.** Merge button może kliknąć człowiek-klepacz; graf identyczny gdy policy Always zmerguje DET.
- **Handoff:** `{pr_url, state: open|merged|revision}` → terminal albo re-enter.

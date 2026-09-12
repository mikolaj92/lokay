# Subgraph: git-pr

**Theme:** po `LOOP_COMPLETE` — commit → push → open/update PR → CI → merge policy.  
**Mode mix:** **wyłącznie DET**. Żaden liść Ralph nie woła gita ani `gh`.

## Flow

```mermaid
flowchart TD
  A([enter: LOOP_COMPLETE + green tree]) --> B[DET: ensure clean staged intent]
  B --> C[DET: commit with issue id summary]
  C --> D[DET: push origin branch]
  D --> E{PR already exists?}
  E -->|no| F[DET: open PR Closes issue]
  E -->|yes| G[DET: update PR body / head]
  F --> H[DET: wait CI]
  G --> H
  H --> I{CI green?}
  I -->|red| J([leave: left_open CI red — no agent merge])
  I -->|green| K[DET: MergePolicy Off|Classify|Always]
  K -->|Off| L([leave: PR open — human merge])
  K -->|Classify low| M[DET: merge]
  K -->|Classify high / Always blocked| L
  M --> N([leave: merged done])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef hold fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  class B,C,D,F,G,H,K det
  class N ok
  class J,L hold
```

## Notes

- **Cały git/PR = DET atoms.** Branch już z intake; tu tylko commit(y), push, PR, CI oracle, policy.
- **Jeden ticket, jeden PR.** Jeśli Ralph pushował commity wcześniej (opcjonalny partial) — update tego samego PR; nie otwieraj drugiego.
- **Domyślnie MergePolicy Off.** Zgodne z SOUL: człowiek przy skutku; nie L5 self-merge.
- **CI jest wyrocznią.** Agent nie nadpisuje czerwonego CI werdyktem review.
- **Nigdy LLM merge.** Classify/Always to skrypt + reguły ryzyka, nie „model uważa że OK”.
- **Handoff.** `{branch, head_sha, pr_url, ci: green|red, merge: merged|left_open|blocked}`.

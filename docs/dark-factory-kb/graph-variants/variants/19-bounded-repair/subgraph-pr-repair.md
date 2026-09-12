# Subgraph: pr-repair

**Theme:** critical review → przy `changes` → `pr_repair` max N na **tym samym** PR; po N → skip/left_open bez limbo.  
**Mode mix:** AGENT SO review + `pr_repair`; DET CI re-assert, counter, merge policy. To jest **drugi** bounded loop wariantu.

## Flow

```mermaid
flowchart TD
  A([enter: PR open]) --> B[DET: wait/re-assert CI green]
  B --> C{CI?}
  C -->|red / timeout| X([leave: fail ci → skip-escape])
  C -->|green| D[AGENT SO: critical_review]
  D --> E{verdict}
  E -->|reject| X2([leave: fail review_reject → skip-escape])
  E -->|approve| F[DET: MergePolicy Off|Classify|Always]
  F --> G{policy result}
  G -->|merged| DONE([leave: merged])
  G -->|left_open hold| HOLD([leave: left_open — human])
  G -->|blocked| X3([leave: fail merge_blocked → skip-escape])
  E -->|changes| H{pr_repair_used < N?}
  H -->|no — exhausted| X4([leave: skip pr_repair_exhausted — PR left open])
  H -->|yes| I[DET: pr_repair_used += 1]
  I --> J[AGENT SO: pr_repair]
  J --> K{ok + files?}
  K -->|ok:false| X4
  K -->|ok| L[DET: local test gate]
  L --> M{green?}
  M -->|red| X4
  M -->|yes| N[DET: commit + push same branch]
  N --> B

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,F,H,I,L,N det
  class D,J agent
  class X,X2,X3,X4 bad
  class DONE,HOLD ok
```

## Notes

- **Review = osobna rola.** Nie ten sam seat co `implement` / `repair_code`. SO: `{verdict, reasons[], risk}`.
- **`changes` nie jest limbo.** To sygnał do `pr_repair` **tylko** gdy `pr_repair_used < N`. Po N → skip-escape z PR left open + receipt — człowiek widzi feedback w review, nie etykietę „deferred”.
- **Ten sam PR.** `pr_repair` pushuje na istniejący branch. Zakaz drugiego PR na ten ticket.
- **Lokalny test przed push.** Czerwony po `pr_repair` nie spala CI — od razu skip (`pr_repair_local_red` / traktuj jak exhausted path).
- **CI re-assert przed każdym review.** Flake / force-push między pętlami — pessimista sprawdza.
- **MergePolicy Off default.** Approve ≠ auto-merge. Always zabronione przy `risk=high`.
- **Reject = escape, nie repair.** `review_reject` nie zużywa `pr_repair` budget — idzie prosto do skip-escape.
- **Handoff.** `{merged:true, sha}` | `{left_open:true, pr_url}` | `{fail:true, reason: pr_repair_exhausted|review_reject|ci_red|merge_blocked, pr_repair_used}`.

## Structured output — `critical_review`

```json
{
  "verdict": "changes",
  "reasons": ["missing edge-case test for empty input", "public API rename without changelog"],
  "risk": "medium"
}
```

`verdict`: `approve` | `changes` | `reject`

## Structured output — `pr_repair`

```json
{
  "ok": true,
  "attempt": 1,
  "summary": "add empty-input test; restore changelog line",
  "files": ["tests/test_foo.py", "CHANGELOG.md"],
  "addresses": ["missing edge-case test", "changelog"]
}
```

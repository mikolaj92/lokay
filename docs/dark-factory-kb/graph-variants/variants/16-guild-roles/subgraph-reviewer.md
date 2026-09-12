# Subgraph: reviewer

**Theme:** Guild Reviewer — separate agent reviews draft; promote or request changes; **HUMAN owns outcome**.  
**Mode mix:** DET for CI; AGENT SO for critical review; HUMAN for merge/hold.

## Flow

```mermaid
flowchart TD
  A([enter: draft PR]) --> B[DET: wait / fetch CI on draft]
  B --> C{CI green?}
  C -->|no| D[DET: report CI failure]
  D --> R([leave: changes needed → Implementer])
  C -->|yes| E[AGENT SO: pr_review — separate seat]
  E --> F{verdict?}
  F -->|request_changes| G[DET: comment + keep draft]
  G --> R
  F -->|approve_promote| H[DET: promote draft → ready / factory-approved signal]
  H --> I[HUMAN: own outcome — merge, hold, or send back]
  I --> J{human decision}
  J -->|merge| K[DET: merge only after human intent]
  K --> L([leave: merged — human accountable])
  J -->|hold| M([leave: open — waiting on human])
  J -->|send back| R

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef human fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  class B,D,G,H,K det
  class E agent
  class I human
```

## Structured output (pr_review)

```json
{
  "ok": true,
  "verdict": "approve_promote"|"request_changes",
  "reasons": ["..."],
  "qa_questions": ["czemu tak — nie da się prościej?"],
  "architecture_fit": "ok"|"risk"|"blocks"
}
```

## Notes

- **Separate role.** Reviewer never wrote the diff (Guild + godark pattern: reviewer without write to product paths in this seat).
- **Promote ≠ merge.** `approve_promote` only lifts draft / stamps factory-approved; **merge requires HUMAN**.
- **Humans own the outcome.** Explicit Guild rule in klepacz form: factory does not merge its own PRs; people own ship/hold.
- **QA strategy stays.** Uncomfortable questions are first-class in `qa_questions` — energy preserved for humans after agents did the klepanie.
- **Changes-requested loops to Implementer** at top level with feedback payload; bounded pr_repair may apply upstream.
- **Handoff contract.** Output = `{promoted: bool, verdict, reasons}` then HUMAN `{merged|held|sent_back}`.
- **Polish:** recenzent promuje draft; człowiek odpowiada za merge i skutek.

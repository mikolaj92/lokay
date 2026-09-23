# Subgraph: validate

**Theme:** faza 3 Agentless — walidacja kandydatów testami, wybór najlepszego, submit jako PR.  
**Mode mix:** prawie cały DET; opcjonalny AGENT SO `pr_review` po otwarciu PR. Zero ReAct.

## Flow

```mermaid
flowchart TD
  A([enter: samples[] + worktree]) --> B[DET: for each sample — apply in sandbox]
  B --> C[DET: run test_command]
  C --> D{green?}
  D -->|record result| E{more samples?}
  E -->|yes| B
  E -->|no| F[DET: rank — green first, then minimal churn]
  F --> G{any green?}
  G -->|no| X([leave: fail — no valid patch])
  G -->|yes| H[DET: materialize best on worktree]
  H --> I[DET: commit + push origin]
  I --> J[DET: open PR Closes issue]
  J --> K{review enabled?}
  K -->|no| L[DET: merge_policy Off|Classify|Always]
  K -->|yes| M[AGENT SO: pr_review]
  M --> N{verdict?}
  N -->|approve| L
  N -->|changes, budget left| R([leave: re-enter repair bounded])
  N -->|reject / high / exhausted| X2([leave: PR open hold / fail])
  L --> O{policy?}
  O -->|merged or left open| DONE([leave: done])
  O -->|hold| DONE

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,C,F,H,I,J,L det
  class M agent
```

## Notes

- **Walidacja = DET, nie vibe check.** Zieloność mierzy `test_command` z ticketa / localize. Model nie przewiduje wyniku testów zamiast runnera.
- **Sandbox per sample.** Apply → test → revert/isolate; kandydaci nie zanieczyszczają się nawzajem.
- **Ranking deterministyczny.** (1) przechodzi testy, (2) mniej plików/hunków, (3) stabilny tie-break po `id`. Żaden LLM judge nie wybiera „najładniejszego”.
- **Submit = open PR.** Mapowanie Agentless submit → klepacz: commit + push + `gh pr create` z `Closes #N`. To koniec fazy kodera.
- **Review osobna rola (opcjonalna).** `pr_review` SO nigdy nie merżuje i nie jest tym samym siedzeniem co repair.
- **Bounded re-enter.** `changes` wraca do repair **raz** (budżet w MANIFEST); potem hold/fail — nie nieskończony ReAct.
- **Merge policy DET.** Off = zostaw PR; Classify/Always = skrypt/gałka — nie prompt.
- **Handoff.** `{pr_url, branch, head_sha, winning_sample_id, test_receipt}` albo fail/hold.

## Structured output — opcjonalny `pr_review`

```json
{
  "verdict": "approve",
  "reasons": ["tests green", "locs respected"],
  "risk": "low"
}
```

`verdict`: `approve` | `changes` | `reject` — `reject` / `risk:high` ⇒ nigdy Always-merge.

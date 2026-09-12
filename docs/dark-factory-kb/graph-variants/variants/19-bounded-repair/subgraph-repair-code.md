# Subgraph: repair-code

**Theme:** lokalny test jako wyrocznia; przy red → `repair_code` max N; po wyczerpaniu → skip (nie limbo).  
**Mode mix:** DET test + counter; AGENT SO `repair_code` w liściu. To jest **pierwszy** bounded loop wariantu.

## Flow

```mermaid
flowchart TD
  A([enter: draft diff + worktree]) --> B[DET: run test_command]
  B --> C{green?}
  C -->|yes| D[DET: commit + push origin]
  D --> E[DET: open PR Closes issue]
  E --> F{PR ok?}
  F -->|no| X([leave: fail push/pr → skip-escape])
  F -->|yes| G([leave: PR open → pr-repair])
  C -->|red| H{repair_code_used < N?}
  H -->|no — exhausted| X2([leave: skip local_test_red_exhausted])
  H -->|yes| I[DET: repair_code_used += 1]
  I --> J[AGENT SO: repair_code]
  J --> K{ok + files?}
  K -->|ok:false / empty| X2
  K -->|ok| B

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,D,E,H,I det
  class J agent
  class X,X2 bad
  class G ok
```

## Notes

- **Test jest wyrocznią.** `test_command` z ticketa / repo. Model nie przewiduje zieloności zamiast runnera.
- **N jest twarde.** Default N=2 (MANIFEST). Po `repair_code_used >= N` → **natychmiast** skip-escape z `local_test_red_exhausted`. Żadnego „jeszcze raz”.
- **Counter DET.** Agent dostaje `{attempt, n_max, last_failure_log}`; nie wolno mu pisać do licznika.
- **Jeden liść, jeden slot.** `repair_code` = wąski SO na czerwony log + diff. Nie zagnieżdżony SDLC, nie multi-sample catalogue (to wariant 07).
- **Nie otwieraj PR na czerwono.** Commit/push/PR tylko po green. Pessimista woli skip niż czerwony CI theatre.
- **ok:false w środku budżetu = skip.** Nie spalaj reszty N na puste naprawy — fail-closed.
- **Handoff.** `{pr_url, branch, head_sha, repair_code_used}` | `{fail:true, reason: local_test_red_exhausted|push_fail|pr_open_fail, repair_code_used}`.

## Structured output — `repair_code`

```json
{
  "ok": true,
  "attempt": 1,
  "summary": "fix assertion: expect 404 not 500",
  "files": ["src/foo.py", "tests/test_foo.py"]
}
```

```json
{ "ok": false, "attempt": 2, "reason": "cant_fix|needs_product_decision|blocked_path" }
```

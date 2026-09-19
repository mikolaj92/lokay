# Subgraph: implement-leaf

**Theme:** faza 2 — **jedyny** slot AGENT: wypełnij liść implement pod `public_pack`.  
**Mode mix:** AGENT SO implement; apply/smoke opc. = DET. Agent **nie** grade'uje i **nie** otwiera PR.

## Flow

```mermaid
flowchart TD
  A([enter: public_pack + worktree + seal_token]) --> B[DET: render implement prompt from public_pack]
  B --> C[AGENT SO: implement_leaf — patch / files]
  C --> D{ok + non-empty?}
  D -->|ok:false / empty| X([leave: fail SO])
  D -->|ok| E[DET: apply_patch_sandbox on worktree]
  E --> F{apply clean?}
  F -->|conflict / reject| X2([leave: fail apply])
  F -->|yes| G{public_smoke_cmd?}
  G -->|no| H([leave: patch ready → grade-oracle])
  G -->|yes| I[DET: run_public_smoke]
  I --> J{smoke exit 0?}
  J -->|no| K{local_public_repair ≤1?}
  K -->|yes| C
  K -->|no| X3([leave: fail smoke])
  J -->|yes| H

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,E,I det
  class C agent
  class X,X2,X3 bad
```

## Notes

- **Agent fills implement leaf only.** Structured output; zero tool-routingu po grafie. Nie woła oracle, nie czyta `holdout/`, nie pisze `grade.json`, nie `gh pr create`.
- **Kontekst = public_pack.** Prompt buduje DET wyłącznie z issue + public fixtures. `seal_token` może być w metadanych (audit), nie jako treść testów.
- **Public smoke ≠ pass.** Opcjonalny fail-fast; zielony smoke **nie** uprawnia do ship — to robi sealed oracle.
- **Bounded local repair.** Max 1 powrót do SO na czerwony public smoke (budżet `local_public_repair`); osobno od `implement_attempts` na poziomie top-level po czerwonym oracle.
- **Meat ≡ AI.** To samo siedzenie SO.
- **Handoff.** `{patch_ref, files[], worktree, seal_token, smoke_receipt?}` → grade-oracle.

## Structured output — `implement_leaf`

```json
{
  "ok": true,
  "summary": "fix null deref in parser",
  "files": [{"path": "src/parser.py", "action": "modify"}],
  "patch_unified": "--- a/src/parser.py\n+++ b/src/parser.py\n@@ …"
}
```

`ok:false` ⇒ escape; pusty `files` / brak patcha ⇒ fail-closed.

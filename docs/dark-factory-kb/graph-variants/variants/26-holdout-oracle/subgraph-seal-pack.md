# Subgraph: seal-pack

**Theme:** faza 1 holdout-oracle — rozdziel public vs holdout, **zaplombuj** suite oceniającą, zbuduj `public_pack` dla liścia implement.  
**Mode mix:** 100% DET. Zero LLM. Agent jeszcze nie startuje.

## Flow

```mermaid
flowchart TD
  A([enter: labeled ticket / issue id]) --> B[DET: pick_one_labeled K=1]
  B --> C{ticket?}
  C -->|none| X([leave: idle])
  C -->|yes| D[DET: worktree_add fresh cell]
  D --> E[DET: split_public_vs_holdout paths]
  E --> F{holdout present?}
  F -->|missing required| X2([leave: fail — no oracle])
  F -->|ok| G[DET: seal_holdout_tests → seal_token]
  G --> H[DET: pack_public_context — issue + public fixtures]
  H --> I[DET: write seal receipt — paths hashed, no holdout body]
  I --> J([leave: public_pack + seal_token + worktree])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,D,E,G,H,I det
  class X,X2 bad
```

## Notes

- **Seal first.** Zanim jakikolwiek prompt do modelu: holdout jest poza worktree widocznym dla agenta (osobny mount / chmod / ephemeral grader volume). `seal_token` = hash ścieżek + policy id — nie treść testów.
- **Public pack only.** Issue body, acceptance criteria widoczne, opc. public smoke fixtures. Żadnych assertów z holdoutu, żadnych golden outputów z oracle.
- **Fail closed.** Brak holdout suite gdy wymaga go ticket type → skip, nie „odpalamy LLM bez grade”.
- **K=1.** Jedna komórka worktree na ticket; occupancy DET.
- **Handoff.** `{ticket, worktree, public_pack, seal_token, public_smoke_cmd?}` — **bez** holdout sources.

## Receipt (DET)

```json
{
  "seal_token": "sha256:…",
  "public_paths": ["tests/public/**"],
  "holdout_sealed": true,
  "holdout_visible_to_agent": false
}
```

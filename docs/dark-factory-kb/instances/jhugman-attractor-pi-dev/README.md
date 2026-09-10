<!-- spine: spine_deterministic -->
# jhugman/attractor-pi-dev (`@jhugman/attractor-pi`)

**spine: deterministic** — `attractor-pi run workflow.dot` / `--simulate`; backend LLM = pi.dev.

**Confidence: 88** — publikowany npm CLI; przykłady issue-loop (Ralph) i spec-to-beads jako **stałe** DOT.

## Co to jest

TS implementacja Attractor na pi-mono. Graf = źródło prawdy; silnik: execute → evaluate edge → checkpoint → repeat.

## Graf (FIXED — `examples/ralph-wiggum/pipeline.dot`)

```mermaid
flowchart TD
  start([start]) --> list[list_ready shell/br code]
  list --> has{has_task? diamond code}
  has -->|no id| exit([exit])
  has -->|has id| plan[plan LLM]
  plan --> implement[implement LLM]
  implement --> validate[validate LLM]
  validate --> check{passed? diamond code}
  check -->|fail| implement
  check -->|ok| complete[complete LLM]
  complete --> sync[sync shell code]
  sync --> commit[commit LLM]
  commit --> list
```

## LLM vs code

| Węzeł | Typ |
|-------|-----|
| `parallelogram` tool_command / diamond conditions | **code** |
| `prompt=` / `@prompts/*.md` | **LLM** leaf |
| validate CLI / simulate mode | **code** |

## Linki

- https://github.com/jhugman/attractor-pi-dev
- npm: `@jhugman/attractor-pi`

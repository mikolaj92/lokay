# Tool contracts and publication style

Lokay separates three concerns:

1. A tool's model instructions live in that tool's complete `src/lokay/tool_contracts/<tool>/prompt.md`.
2. Python and Fala enforce schemas, enums, evidence rounds, routing, limits, and side effects.
3. Kofte may style public PR-review prose only after the structured decision is validated.

Each contract is independent. There are no shared prompt fragments, includes, inheritance, or policy DSL. If two tools need the same instruction, each contract states it explicitly. The mechanical `render_contract` loader loads exactly one file and rejects missing or unknown `<<placeholder>>` values.

PR-review contracts are separate for initial review, validator retry, and the single evidence round. The review policy begins with the ticket's observable product goal, requires evidence for external contracts and defects, and asks for the smallest sufficient fix rather than speculative architecture.

## Kofte

A repository may opt into public PR-review styling in its catalog row:

```yaml
repos:
  - name: owner/repo
    clone_path: /path/to/repo
    review_style: en+kofte
```

Other examples are `en+polish_direct` or an empty value for neutral rendering. Kofte receives only the human prose after verdict validation. It cannot change the structured verdict, findings, evidence selection, merge policy, or repair routing.

Configure Kofte's replaceable OpenAI-compatible LLM with:

```text
KOFTE_LLM_BASE_URL
KOFTE_LLM_MODEL
KOFTE_LLM_API_KEY  # optional
```

If Kofte or its LLM is unavailable, Lokay publishes the deterministic neutral review comment.

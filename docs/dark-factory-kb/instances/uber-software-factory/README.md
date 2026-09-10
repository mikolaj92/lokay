# Uber Software Factory

**Confidence: 88** — talk AI Engineer 2026 + blogi Uber/port; brak publicznego repo factory; platforma (6 bloków) + managed agents (m.in. Minion — **≠ Stripe Minions**).

## Co to jest

Wewnętrzna **agentic SDLC platform** Ubera: Model Gateway, MCP Gateway, DevPods, Skills Marketplace, Context Graph, Cortana — na tym workflows (spec→draft PR, inner-loop validation, self-healing CI, managed maintenance). >70% PR z local/cloud agents; człowiek review/escalation.

## Graf

```mermaid
flowchart TD
  surf[Cortana Slack / CLI / Web] --> gw[LLM Model Gateway PII+guard]
  surf --> mcp[MCP Gateway OmniMCP / CLI / code-mode]
  surf --> graph[Context Graph org knowledge]
  surf --> skills[Skills Marketplace 3k+]
  surf --> pod[Warm DevPod / balloon K8s]
  pod --> minion[Managed coding agent Minion]
  minion --> inner[Inner loop: lint / visual / staging]
  inner --> draft[Draft PR stop before CI waste]
  draft --> ci[Outer CI + self-heal + uReview]
  ci --> human[Human review / escalate]
  maint[Managed maintenance loops] -.-> skills
  maint -.-> minion
```

## Co / gdzie / jak

| Element | Wartość |
|---------|---------|
| Trigger | Interactive Cortana **lub** managed agents (review, CI heal, bugs, maintenance) |
| Run | Pre-warmed **DevPods** (K8s balloon pods, snapshotted repos) |
| Tools | MCP Gateway (>1k tools); CLI resolve + code-mode by default (token tax) |
| Models | Central LLM gateway; Pareto routing per managed agent (np. uReview) |
| Context | Context graph (dziesiątki mln nodes/edges) zamiast detective-turns |
| Skills | Registry + lint/review + usage evals (tysiące skills, dziesiątki k exec/dzień) |
| Validation | Inner-loop przed CI; visual + integration skills |
| Merge | Human; self-heal CI; maintenance loops z capami |
| Nie robi | Public OSS factory; mylić z Stripe „Minions” |

## Linki

- https://www.uber.com/us/en/blog/efficient-software-factory/ (cost layers + managed agents)
- https://ai.engineer/talks/17-YSUHo6Lk-agentic-sdlc-at-uber-building-blocks-ubers (Building Blocks talk)
- https://newsletter.port.io/p/how-uber-built-a-software-factory (platform + workflows summary)
- https://www.uber.com/gf/en/blog/solving-the-agent-identity-crisis/ (agent identity / A2A)

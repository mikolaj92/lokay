# Subgraph: webhook-ff

**Theme:** GitHub **fire_and_forget webhook** + **self-event gate** (DeerFlow borrow).  
**Mode mix:** 100% DET — tani ACK, zero LangGraph w routerze.

## Flow

```mermaid
flowchart TD
  A([enter: POST /webhooks/github]) --> B[DET: HMAC verify sha256]
  B -->|bad sig| R401([401/403 fail-closed])
  B -->|ok| C[DET: fanout_event — registry mtime-cached]
  C --> D{matched agents for repo+event?}
  D -->|none| IDLE([200 OK + skipped:no_binding])
  D -->|each match| E{self-event gate}
  E -->|sender.login ∈ bot_login / mention_logins / agent.name| SKIP([skip: self_event])
  E -->|human / other bot| F{event_should_fire trigger?}
  F -->|no| SKIP2([skip: trigger_miss])
  F -->|yes| G[DET: build_prompt + preferred_thread_id]
  G --> H[DET: publish_inbound InboundMessage]
  H --> I[DET: runs.create fire_and_forget=True]
  I --> J([leave: 200 OK — run pending])
  SKIP --> J
  SKIP2 --> J
  IDLE --> J

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class B,C,E,F,G,H,I det
  class R401,SKIP,SKIP2 stop
```

## Notes

- **Borrow fidelity.** DeerFlow: webhook handler stays cheap — no `runs.wait`, no LLM w routerze — żeby zmieścić się w GitHub 10s delivery timeout. `ChannelRunPolicy.fire_and_forget=True` → `client.runs.create` wraca gdy run jest `pending`.
- **Self-event gate.** `_is_self_event(sender.login)` używa tej samej precedence co mention gate: `trigger.mention_login` → `github.bot_login` → `default_mention_login` → `agent.name`. Komentarz, który agent sam wstawił przez `gh`, nie odpala ponownie **tego samego** agenta (pętla webhook→run→gh→webhook).
- **Fail-closed HMAC.** Zła sygnatura = reject. Authenticity na webhooku, nie per-sender `/connect` (DeerFlow: `requires_bound_identity=False` dla GitHub).
- **Trigger list = enablement.** Event poza `bindings[].triggers` = nie ładujemy agenta. `DEFAULT_TRIGGERS` tylko field-level defaults (np. `require_mention`), nie lista włączeń.
- **Klepacz mapping.** To jest „label = start” w świecie eventów: start = dostawa GitHub + binding, nie chat pick. Agent nie wybiera sobie pracy.
- **Handoff contract.** Output = `{fired:[{agent, thread_id, run_id}], skipped:[{reason: self_event|trigger_miss|no_binding}]}` + HTTP 200 do GitHub.

# Commercial / product AI software factories — INDEX

Baza wiedzy: jak zespoły produktowe prowadzą autonomiczne / near-lights-out fabryki kodu.  
Język: PL summaries, EN product names. Stan research: **2026-09-10**.

## Pliki (1 per system)

| Plik | System | Open/Closed | Default handoff |
|------|--------|-------------|-----------------|
| [cognition-devin.md](./cognition-devin.md) | Cognition Devin | Closed | PR (+ stacked) |
| [cursor-cloud-agents.md](./cursor-cloud-agents.md) | Cursor Cloud Agents | Closed | PR + artifacts |
| [openai-codex.md](./openai-codex.md) | OpenAI Codex Cloud/CLI | Closed (+ partial OSS CLI) | Diff/PR |
| [google-jules.md](./google-jules.md) | Google Jules | Closed | Plan→PR |
| [anthropic-claude-code.md](./anthropic-claude-code.md) | Anthropic Claude Code loops | Closed | Local/cloud routine→PR |
| [claude-code-action.md](./claude-code-action.md) | Claude Code Action + Routines | Action OSS | Event→PR w Actions |
| [factory-ai.md](./factory-ai.md) | Factory.ai Droids/Missions | Closed | Mission→validate→PR |
| [github-copilot-coding-agent.md](./github-copilot-coding-agent.md) | GitHub Copilot Coding/Cloud Agent | Closed | Branch→PR (≤59m) |
| [amazon-q-developer.md](./amazon-q-developer.md) | Amazon Q Developer (GitHub) | Closed | Issue→PR + review agent |
| [sweep-ai.md](./sweep-ai.md) | Sweep AI | **OSS** (+ App) | Issue→sandbox→PR |
| [mentatbot-and-others.md](./mentatbot-and-others.md) | MentatBot, OpenHands, Aider… | Mixed | Issue/@bot→PR / self-host |

## Top 10 patterns (konkretne mechanizmy, nie marketing)

1. **PR jest granicą autonomii, nie merge**  
   Prawie wszyscy (Devin, Cursor, Jules, Copilot, Q, Codex, Sweep, Mentat) kończą na branch/PR. Lights-out = „do reviewable PR”, nie „do produkcji”. Merge zostaje human/policy gate.

2. **Environment quality ≫ model brand**  
   Cursor: „development environment is the product”; Devin Devbox; Jules Environment Snapshot; Copilot `copilot-setup-steps.yml`; Codex cloud environments. Brak test runtime = cicha degradacja jakości.

3. **Durable orchestration poza VM**  
   Cursor: Temporal (agent loop ≠ machine ≠ conversation). Devin/Claude: deterministyczne skrypty workflow (Python/JS) z resume/hash checkpoint. Nie trzymaj długiego loopu tylko w RAM kontenera.

4. **Fresh context workers + shared artifacts**  
   Factory Missions / Devin child agents / Claude workflow subagents: wąski cel per agent, stan w contract/feature list/git branch — nie jeden 1M-token monolit.

5. **Validation contract zanim kod**  
   Factory: behavioral assertions first + TDD workers + adversarial validators. Claude: `/goal` + osobny evaluator model. Sweep/Cursor: sandbox tests przed/w trakcie PR.

6. **CI jako zewnętrzna pętla, nie tylko pre-PR**  
   Sweep CI fix loop; Cursor CI Autofix via `gh`; Codex babysit-pr; Claude `/loop` na PR; Devin stacked PR CI monitoring. Fabryka = code loop **i** checks loop.

7. **Human gates przesuwają się w lewo (plan) i w prawo (merge)**  
   Jules `requirePlanApproval`; Factory mission plan approve; Devin workflow script approve; Copilot research/plan before PR. Środkowy coding stretch = maksymalna autonomia.

8. **Repo-native steering files**  
   `AGENTS.md` (Codex), `.cursor/rules` + hooks, `.amazonq/rules/`, Copilot custom instructions/skills, Claude `SKILL.md`, Sweep `sweep.yaml`. Feedback z review → codify (nie tylko chat).

9. **Trigger surface = queue fabryki**  
   Issue assign/label (Copilot, Q, Sweep), `@agent` comments (Cursor, Codex, Mentat, Copilot), Slack/Linear, schedules (`/schedule`, Copilot automations, Codex automations). Fabryka potrzebuje **kolejki sygnałów**, nie tylko IDE.

10. **Isolation + policy = enterprise IT for agents**  
    Network egress allowlists, secrets injection, sandbox (OpenHands boundary, Codex sandbox modes, Cursor Tailscale), Droid Shield, branch protection bypass actors. Autonomia bez guardrails = compliance blocker.

## Porównanie szybkie: multi-agent shape

| System | Shape |
|--------|--------|
| Factory Missions | Orchestrator → workers → scrutiny/user-test validators |
| Devin Dynamic Workflows | Python script → N VM sessions + structured I/O |
| Claude dynamic workflows | JS script → do ~1000 subagents, 16 concurrent |
| Cursor | Single agent + async subagents + computer-use subagent; N parallel cloud agents |
| Jules | Session-centric; parallel = many sessions |
| Copilot / Q / Sweep / Mentat | Mostly single agent per ticket (+ specialized review agent u Q) |

## Co zwykle NIE jest zautomatyzowane

- Merge do protected main bez człowieka  
- Produktowe „co budować” (ambiguous scope)  
- Cross-repo (wyjątki: Cursor multi-repo; Copilot hard-no)  
- Secrets discovery / prod access bez policy  
- Długie sesje bez budżetu (Copilot 59m hard cap; token bombs w pętlach Claude)  
- Deploy/prod incident ownership

## Rekomendowany stacking do własnej „dark factory”

```
Queue (Issues/Linear/Slack)
  → Cloud/SWE agent (Cursor|Devin|Jules|Copilot|Codex) w pełnym env
  → Self-test w VM + artifacts
  → PR
  → Review agent (Q review | Codex @codex review | Claude /code-review | Copilot review)
  → CI Autofix loop (Cursor|Sweep|babysit-pr|/loop)
  → Human merge
  → Codify failure → AGENTS.md / skills / rules
```

Dla air-gap: OpenHands (lub self-host Sweep) zamiast SaaS runtime.

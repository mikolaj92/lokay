# GitHub Copilot Coding Agent / Cloud Agent (ex-Workspace lineage)

**Typ:** zamknięty (GitHub/Microsoft) — runtime na GitHub Actions  
**Producent:** GitHub  
**Uwaga nazewnictwa:** Copilot Workspace (technical preview) → lekcje wchłonięte w **Copilot coding / cloud agent** (GA paid plans ~2025+). „Workspace” jako osobny produkt nie jest już główną powierzchnią.

## Architektura

```
Trigger (assign Issue to Copilot / Agents panel / VS Code Chat /
         @copilot on PR / Slack|Teams / automations / security campaign)
    → Ephemeral GitHub Actions-powered dev environment
    → [opcjonalnie] research → plan → iterate on branch (before PR)
    → commits + logs visible on GitHub
    → draft/final Pull Request
    → człowiek: review comments → agent iterate → APPROVE/MERGE
```

### Setup env
- `.github/workflows/copilot-setup-steps.yml` z jobem `copilot-setup-steps` — deps, custom runners, MCP.
- Custom instructions, Copilot Memory (preview), Skills, Hooks, Custom agents (frontend/docs/testing specjalizacje).
- MCP: GitHub MCP + Playwright domyślnie; repo JSON settings.

Źródło: [About Copilot cloud agent](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent.md), [Coding agent 101](https://github.blog/ai-and-ml/github-copilot/github-copilot-coding-agent-101-getting-started-with-agentic-workflows-on-github/)

### Hard limits (mechaniczne)
- Max session **59 minutes** (hard) — dziel duże taski.
- **Jedno repo** na run; **jeden branch / jeden PR** na task.
- Tylko repo hostowane na GitHub.
- Branch protection / rulesets mogą blokować agenta (bypass actor = Copilot).

## Human gates
| Gate | Opis |
|------|------|
| Policy enable (Biz/Ent) | Admin musi włączyć |
| Repo opt-out | Owner może wyłączyć |
| Create PR timing | Można iterować na branch **zanim** otworzysz PR |
| Review + merge | Agent **nie merge’uje**; draft PR + human approval |
| Rulesets | Niekompatybilne reguły blokują dostęp |

## Eval / CI
- W Actions env: explore, testy, linters.
- Hooks: `preToolUse` deny dangerous; `postToolUse` format; `agentStop` final checks.
- Copilot code review (osobna powierzchnia) też zużywa Actions minutes.
- Metrics API: PRs created/merged by agent, median time-to-merge.

## Multi-agent vs single
- Domyślnie **jeden agent per task**.
- **Custom agents** = wyspecjalizowane warianty (nie swarm w jednym runie).
- Mission Control (marketing/third-party) = parallelizacja wielu tasków z backlogu.
- IDE **agent mode** ≠ cloud agent (lokalne sync vs Actions async).

## Failure / retry
- Timeout 59m → stop; rozbij task.
- Komentarz `@copilot` na PR → kolejna iteracja.
- Brak dostępu do resource → agent raportuje kroki dla człowieka.
- Automations: schedule / on issue opened.

## Czego NIE automatyzuje
- Cross-repo changes w jednym runie
- Merge / deploy
- Sesje >59 minut
- Non-GitHub hosts

## Open-source vs closed
**Closed** agent. GitHub Actions ekosystem OSS; docs publiczne.

## Kluczowe URL-e
- https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent.md
- https://github.blog/ai-and-ml/github-copilot/github-copilot-coding-agent-101-getting-started-with-agentic-workflows-on-github/
- https://docs.github.com/en/copilot/responsible-use/copilot-coding-agent (responsible use)

# Continue.dev (agent mode)

**Nazwa EN:** Continue  
**Rola w dark factory:** IDE coding agent + **CI-enforceable review rules**; po przejęciu przez Cursor — repo **read-only / archived maintenance**.

## Streszczenie (PL)

Continue to open-source coding agent (VS Code, JetBrains, CLI): Chat / Edit / **Agent mode** (tool_use), Plan mode, MCP servers, reguły w repo. Agent mode: multi-step (czytaj, edytuj, testuj) z HITL. Wyróżnik: **PR review automation** — reguły jako Markdown w VCS, egzekwowalne w CI (nie tylko sugestie). W 2026 **Continue acquired by Cursor**; codebase Apache-2.0 pozostaje publiczny (final 2.0.0), ale aktywny rozwój produktu przeniesiony. Nadal wartościowy jako wzorzec **rules-as-code** i self-hosted IDE agent.

## Pipeline (kształt)

1. Konfiguracja `config.yaml` (models, rules, mcpServers).  
2. Agent mode: zadanie → tool calls (files, terminal, MCP).  
3. Opcjonalnie CI: Continue CLI review na PR.  
4. Human accept diffs w IDE.

To **nie** pełny unattended dark factory out-of-the-box — bliżej assisted + automated review gate.

## Narzędzia

- IDE context providers, MCP.  
- CLI do CI.  
- Model-agnostic (cloud + Ollama).

## Testy

- Agent może odpalać testy przez terminal tool.  
- CI: review, niekoniecznie auto-fix + merge.

## Multi-agent

- Konfigurowalne „agents” jako zestawy model+rules+tools; nie company-SOP jak MetaGPT.

## Limity

- **Repo nieaktywne** (post-acquisition) — ryzyko stagnacji.  
- Agent mode wymaga modeli z `tool_use`.  
- Słabsza autonomia długich issue niż OpenHands/Devin.  
- Zależność od utrzymania forków społeczności.

## Repozytoria i paper’y

| Zasób | URL |
|-------|-----|
| Site (acquired notice) | https://continue.dev/ |
| GitHub (read-only) | https://github.com/continuedev/continue |
| Docs / config.yaml | https://docs.continue.dev/reference |
| Brak klasycznego academic paper „Continue” — produkt OSS | — |

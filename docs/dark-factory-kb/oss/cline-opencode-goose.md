# Cline, OpenCode, Goose (dodatkowe silne OSS)

**Nazwy EN:** Cline, OpenCode, Goose (Block / Linux Foundation AAIF)  
**Rola w dark factory:** praktyczne IDE/CLI agenty do autonomicznych edycji; bliżej developera niż akademickiego harnessu, ale da się spiąć w pętle CI/issue.

## Streszczenie (PL)

Poza „klasycznymi” SWE-bench scaffoldami ekosystem 2025–2026 ma trzy bardzo popularne OSS coding agents:

- **Cline** — agent w VS Code / JetBrains / CLI / SDK; tool use z human-in-the-loop approval diffów; Kanban multi-agent; MCP; BYOK. Dobry do interactive autonomy + headless CLI.  
- **OpenCode** — terminal-native, ogromna społeczność (setki k gwiazdek wg zestawień 2026), multi-provider routing, headless automation (CI-friendly).  
- **Goose** — Rust, Apache-2.0, pierwotnie Block, teraz **Linux Foundation AAIF**; CLI + desktop; rozszerzenia (70+); generalist (kod + infra + research), nie tylko SE.

Nie zastępują OpenHands jako platformy sandbox-PR, ale są **najczęściej wdrażanymi** OSS agentami „na co dzień”.

## Pipeline (kształt)

Wspólny wzorzec: **zadanie → plan → tools (read/edit/shell/browser/MCP) → diff → (opcjonalnie) test → commit**.  
Dark factory: owinięcie headless CLI (Cline CLI / OpenCode / Goose) wokół issue queue + CI gate.

## Narzędzia

| | Cline | OpenCode | Goose |
|--|-------|----------|-------|
| Powierzchnia | IDE + CLI + SDK | Terminal (+ desktop w zestawieniach) | CLI + desktop + API |
| MCP / extensions | Tak | Provider/tools bogate | 70+ extensions |
| HITL diffs | Silne (IDE) | Terminalowy review | Zależnie od trybu |
| Sandbox | Zależnie od hosta | Zależnie od hosta | Zależnie od hosta |

## Testy

- Shell/tool: agent odpala testy projektu.  
- Brak jednego wspólnego SWE-harness; ewaluacje społecznościowe / blogowe (ostrożnie z liczbami).

## Multi-agent

- **Cline:** Kanban / teams / SDK multi-agent.  
- **Goose:** recipes / extensions orchestration.  
- **OpenCode:** raczej single powerful CLI agent (+ routing modeli).

## Limity

- Bezpieczeństwo: często działają na żywym workspace (nie Docker-first jak OpenHands).  
- Gwiazdki ≠ jakość na SWE-bench.  
- OpenCode: weryfikuj aktualny org/URL (migracje społeczności).  
- Goose: szerszy scope = mniej „pure SE repair” out-of-box.

## Repozytoria i paper’y

| Zasób | URL |
|-------|-----|
| Cline | https://github.com/cline/cline |
| Cline Kanban | https://github.com/cline/kanban |
| Goose (Block) | https://github.com/block/goose |
| AAIF / Goose (społeczność) | szukaj `aaif-goose/goose` / Linux Foundation AAIF |
| OpenCode | https://github.com/anomalyco/opencode (potwierdź aktualny canonical org) |
| Porównania (wtórne) | https://www.morphllm.com/best-ai-coding-agents-2026 |

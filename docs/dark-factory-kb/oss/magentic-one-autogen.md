# Magentic-One / AutoGen (wzorce)

**Nazwa EN:** Magentic-One, AutoGen (Microsoft)  
**Rola w dark factory:** **ogólny** multi-agent (Orchestrator + Coder + Surferzy); wzorzec orkiestracji, nie specjalistyczny SWE-bench factory.

## Streszczenie (PL)

**AutoGen** to framework multi-agent (konwersacje, teams, tools). **Magentic-One** (listopad 2024, raport tech.) to generalist team: **Orchestrator** utrzymuje Task Ledger + Progress Ledger, planuje, deleguje, re-planuje przy stallu. Specjaliści: **WebSurfer** (Chromium), **FileSurfer**, **Coder**, **Computer Terminal / Executor**. Wyniki konkurencyjne na GAIA, AssistantBench, WebArena — nie jest to primarily SWE-bench harness, ale **Coder+Terminal** pozwalają budować pętle issue→code→run. Wzorzec: wydziel skill’e w agentów (OOP agentów), plug-and-play vs monolit.

## Pipeline (kształt)

1. Task NL.  
2. Orchestrator → Task Ledger (fakty, plan).  
3. Loop: Progress Ledger → assign subtask → agent → update.  
4. Stall → replan.  
5. Complete gdy Orchestrator uzna done.

Dla SE: Coder pisze patch; Terminal uruchamia testy; FileSurfer czyta repo; WebSurfer docs/StackOverflow.

## Narzędzia

- MultimodalWebSurfer, FileSurfer, code executor.  
- `MagenticOneGroupChat` w `autogen-agentchat`.  
- AutoGenBench do ewaluacji.

## Testy

- Przez **Executor / Terminal** — agent odpala komendy testowe.  
- Brak wbudowanego SWE-bench protocol; użytkownik definiuje.

## Multi-agent

- **Tak — referencyjny wzorzec.** Orchestrator vs workers.  
- Łatwo dodać/usuwać agentów bez przepisywania całości.

## Limity

- Nie zoptymalizowany pod GitHub issue resolution leaderboard.  
- Bezpieczeństwo: web + code execution = konieczny sandbox.  
- Overhead koordynacji vs mini-SWE single loop.  
- Wersjonowanie AutoGen (0.2 vs 0.4 AgentChat) — sprawdzać docs.

## Repozytoria i paper’y

| Zasób | URL |
|-------|-----|
| Magentic-One docs | https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/magentic-one.html |
| MSR article | https://www.microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks/ |
| Tech report PDF | https://www.microsoft.com/en-us/research/wp-content/uploads/2024/11/MagenticOne.pdf |
| arXiv | https://arxiv.org/abs/2411.04468 |
| AutoGen GitHub | https://github.com/microsoft/autogen |
| Package README (legacy path) | https://github.com/microsoft/autogen/blob/main/python/packages/autogen-magentic-one/README.md |

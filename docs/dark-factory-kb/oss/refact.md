# Refact

**Nazwa EN:** Refact / Refact.ai  
**Rola w dark factory:** **local-first** agentic engine (daemon + worktree fleets + tools) — najbliższy self-hosted „fabryce” bez oddawania repo chmurze.

## Streszczenie (PL)

Refact to open-source (BSD-3-Clause) silnik: resident **daemon**, LSP/HTTP dla IDE, TUI, browser GUI, autonomiczny agent z 50+ tools, planowanie tasków, izolacja w **git worktrees**, MCP, subagents, BYOK. Cloud Refact wyłączony (~kwiecień 2026); oryginalne `smallcloudai/refact` **zarchiwizowane**; rozwój w forku społeczności **JegernOUTT/refact**. Agent: plan → tool loop (shell, AST search, patches, browser, GitHub/Docker/DB…) → verify → iterate. Fleety agentów na kartach zadań = mini dark factory na laptopie/serwerze.

## Pipeline (kształt)

1. `refact` daemon + project worker.  
2. Task / chat → planner rozbija na cards.  
3. Agent(y) w worktree → edycje + shell + integracje.  
4. Checkpoint / diff preview; permission gates.  
5. Buddy/memory warstwa (diagnostics, docs).  
6. Merge/PR przez git/GitHub tool — lokalna kontrola.

## Narzędzia

- shell, process_*, file patches, AST/VecDB retrieval.  
- Browser automation, GitHub/GitLab, Docker, DB, MCP.  
- IDE plugins (VS Code, JetBrains) jako klienci daemona.

## Testy

- Runtime tools zamykają pętlę: agent odpala testy/lintery w shellu i iteruje.  
- Brak jednego „SWE-bench official harness” w produkcie — self-verify.

## Multi-agent

- Tak: **subagents**, fleety worktree, role planera.  
- Nie SOP „CEO/PM”, raczej task parallelism.

## Limity

- Migracja cloud→fork: dokumentacja i plugin paths mogą być w flux.  
- Użytkownik utrzymuje modele/klucze i bezpieczeństwo tooli.  
- Enterprise features cloud zniknęły — self-host only.  
- Krzywa nauki daemona vs prosty CLI (Aider).

## Repozytoria i paper’y

| Zasób | URL |
|-------|-----|
| Active fork | https://github.com/JegernOUTT/refact |
| Legacy archive | https://github.com/smallcloudai/refact |
| Site | https://refact.ai/ |
| Cloud shutdown blog | https://refact.ai/blog/2026/refact-cloud-is-shutting-down/ |
| Academic paper: brak flagowego „Refact paper”; produkt OSS | — |

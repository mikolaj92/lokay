# SWE-agent / mini-SWE-agent

**Nazwa EN:** SWE-agent, mini-SWE-agent (Princeton NLP / Stanford)  
**Rola w dark factory:** kanoniczny scaffold **issue → bash/ACI → patch** na SWE-bench.

## Streszczenie (PL)

SWE-agent (NeurIPS 2024) wprowadził **Agent-Computer Interface (ACI)** — zestaw komend zoptymalizowanych pod LLM (czytanie/edycja plików, bash), żeby agent mógł samodzielnie naprawiać prawdziwe GitHub issues. W 2025–2026 zespół **zaleca mini-SWE-agent** (~100 linii Pythona): ten sam poziom skuteczności przy prostym flow (model + shell w sandboxie), bez ciężkiego scaffoldingu. Klasyczny SWE-agent jest w trybie maintenance (EnIGMA/CTF nadal tam). mini-SWE-agent raportuje **>74%** na SWE-bench Verified (zależnie od modelu, m.in. Gemini 3 Pro).

## Pipeline (kształt)

1. **Wejście:** opis issue / zadanie SWE-bench / prompt lokalny.
2. **Pętla agenta:** LLM wybiera akcję (bash / narzędzia ACI) → środowisko wykonuje → obserwacja wraca do kontekstu.
3. **Edycja kodu** w checkoutowanym repo (sandbox: Docker/podman/singularity/bwrap…).
4. **Weryfikacja:** agent sam uruchamia testy / skrypty w shellu.
5. **Wyjście:** patch / diff; w benchmarku — submission do ewaluatora SWE-bench.
6. mini-SWE-agent: maksymalnie prosty control flow (bez rozbudowanego tool registry).

## Narzędzia

- **SWE-agent 1.x:** ACI (viewer, editor, search), bash, konfiguracja YAML, Docker.
- **mini-SWE-agent:** głównie **bash w izolowanym env**; litellm / OpenRouter / Portkey; lokalnie lub kontener.
- Brak natywnego „produktowego” PR UI — integracja z GitHubem to skrypt / CI użytkownika.

## Testy

- Agent **sam** uruchamia suite projektu przez shell.
- Na SWE-bench: acceptance testy są **ukryte** (nie wolno ich używać przy generacji); agent może używać testów istniejących w repo / własnych reproduktorów.
- Sandbox izoluje side-effecty.

## Multi-agent

- Domyślnie **single-agent**.
- Brak wbudowanego zespołu ról; rozszerzenia to osobne projekty (np. Live-SWE-agent na bazie mini).

## Limity

- Klasyczny SWE-agent: złożoność, wolniejszy start vs mini.
- Długi horyzont: context window i koszt tokenów.
- Brak org-level memory, ticket queue, RBAC.
- EnIGMA (cyber/CTF) nie w pełni przeniesione do mini.
- Skuteczność mocno zależy od **jakości modelu bazowego**.

## Repozytoria i paper’y

| Zasób | URL |
|-------|-----|
| Docs SWE-agent | https://swe-agent.com/latest/ |
| GitHub SWE-agent | https://github.com/SWE-agent/SWE-agent |
| mini-SWE-agent docs | https://mini-swe-agent.com/ |
| GitHub mini-SWE-agent | https://github.com/SWE-agent/mini-swe-agent |
| Paper SWE-agent (arXiv) | https://arxiv.org/abs/2405.15793 |
| SWE-bench | https://www.swebench.com/ · https://github.com/swe-bench/SWE-bench |
| BibTeX | Yang et al., *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering*, NeurIPS 2024 |

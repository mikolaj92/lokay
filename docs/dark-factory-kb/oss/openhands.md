# OpenHands (dawniej OpenDevin)

**Nazwa EN:** OpenHands / OpenDevin, CodeAct  
**Rola w dark factory:** najpełniejsza OSS **platforma** autonomicznego SE (GUI + CLI + SDK + cloud/enterprise).

## Streszczenie (PL)

Projekt startował jako **OpenDevin** (odpowiedź społeczności na Devin), przeszedł pod All Hands AI / organizację OpenHands. Agent działa w **izolowanym sandboxie** (Docker): edytuje kod, odpala terminal, przegląda web. Domyślny silny agent: **CodeAct** (akcje = kod Python/bash + function calling). Oferuje GUI, CLI, SDK i opcje enterprise (kontrola modeli, audyt). Model-agnostic; własny **OpenHands Index** porównuje modele na issue resolution, greenfield, frontend, testing, info-gathering. Historycznie CodeAct 2.1 ~53% SWE-bench Verified; nowsze harness + frontier modele raportowane w okolicy **~70%+**.

## Pipeline (kształt)

1. **Wejście:** prompt / GitHub issue / zadanie w GUI lub API.
2. **Sandbox runtime** z workspace repo (Action→Observation event stream).
3. **Pętla CodeAct:** plan → tool/code act → obserwacja → iterate.
4. Opcjonalnie **delegacja** do sub-agentów (np. browsing expert).
5. Testy / build w sandboxie.
6. Commit / patch; w cloud/SDK — ścieżka do PR w workflow użytkownika.

## Narzędzia

- Terminal (bash), edytor plików, przeglądarka (BrowserGym-like).
- Integracja VS Code w sesji (GUI).
- SDK do embedowania w produktach; Workspace factory (local vs remote container).
- Benchmarki: https://github.com/OpenHands/benchmarks

## Testy

- Agent uruchamia testy projektu w sandboxie i iteruje po failach.
- Ewaluacja SWE-bench przez oficjalny harness OpenHands.
- Osobne zadania OpenHands Index: software testing jako kategoria.

## Multi-agent

- Wspiera **delegację** i współpracę agentów (nie tylko monolityczny CodeAct).
- Framework produkcyjny Software Agent SDK.

## Limity

- Cięższy setup niż Aider/mini-SWE (Docker, koszt API).
- Self-host wymaga utrzymania runtime.
- Trajektorie długie = koszt; potrzeba limitów kroków.
- Fundament agenta produkcyjnego — pełny mill issue→merge wymaga kolejki, merge policy, multi-repo catalog (patrz też godark orkiestratory w tym folderze).

## Repozytoria i paper’y

| Zasób | URL |
|-------|-----|
| Strona | https://www.openhands.dev/ |
| Docs | https://docs.openhands.dev |
| GitHub | https://github.com/OpenHands/OpenHands |
| Cloud | https://app.openhands.dev |
| Paper OpenHands / CodeAct (arXiv) | https://arxiv.org/abs/2407.16741 |
| Blog CodeAct 2.1 | https://www.openhands.dev/blog/openhands-codeact-21-an-open-state-of-the-art-software-development-agent |
| OpenHands Index | https://www.openhands.dev/blog/introducing-the-openhands-index |

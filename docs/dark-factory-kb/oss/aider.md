# Aider (+ pętle CI)

**Nazwa EN:** Aider  
**Rola w dark factory:** **git-native** pair programmer; z CI staje się pętlą **fail → fix → commit → PR**.

## Streszczenie (PL)

Aider to terminalowy AI pair programmer: mapa repo (statyczna + call graph), edycje w prostym formacie diff, **automatyczne commity** z sensownymi message’ami, lint i test po każdej zmianie. Sam w sobie jest HITL/pair; **wzorzec dark-factory** powstaje przez owinięcie w GitHub Actions / skrypt: issue z labelką → branch → `aider --yes` → test → PR. Popularne też: auto-fix lintów po czerwonym CI (`--yes`, `--no-auto-commits`, marker `[skip ci-autofix]`). Sam Aider nie jest orkiestratorem katalogu multi-repo.

## Pipeline (kształt)

**Interaktywny:** prompt użytkownika → mapa kontekstowa → edit → lint/test → commit.

**CI / autonomous:**
1. Trigger (issue `ai-ready`, workflow_dispatch, CI failure).
2. Checkout + branch.
3. Aider z promptem = treść issue / log lint.
4. `--auto-test` / zewnętrzny `pytest` itp.
5. Jeśli OK → push + `gh pr create`.
6. Guardy anty-pętli w commit message.

## Narzędzia

- Repo map, git integration, watch mode (komentarze w IDE).
- 100+ języków, multi-LLM.
- `/test`, `/run`, `--lint-cmd`, `--test-cmd`, `--auto-test`.
- Images/URLs, voice.

## Testy

- Natywne: po edycji lint; opcjonalnie pełny test suite i auto-naprawa faili.
- W CI: verify-before-commit (nie pushuj, jeśli lint nadal czerwony).

## Multi-agent

- Single-agent. Orkiestracja = zewnętrzny skrypt / Actions.

## Limity

- Bez sandboxa produktowego (działa na workspace hosta — ostrożnie w CI).
- Słabszy na bardzo długich, wieloetapowych misjach vs OpenHands/Devin.
- Jakość PR zależy od owijki (policy, reviewers) — Aider tego nie daje.

## Repozytoria i paper’y

| Zasób | URL |
|-------|-----|
| Site | https://aider.chat/ |
| GitHub | https://github.com/Aider-AI/aider |
| Lint & test docs | https://aider.chat/docs/usage/lint-test.html |
| Leaderboards | https://aider.chat/docs/leaderboards/ |
| Przykład CI auto-fix (społeczność) | https://www.iamraghuveer.com/posts/aider-ci-auto-fix/ |

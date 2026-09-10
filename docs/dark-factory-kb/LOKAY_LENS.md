# Lokay lens (obserwacyjnie)

Bez recepty „przepisz lokaja”. Tylko mapowanie.

## Już blisko wzorców z KB

- Cel: issue → ai/fix PR → merge (dark factory)
- Graf / mikroprogramy zamiast monolitu
- LLM przy triage / wysokiej entropii; reszta deterministyczna
- Lokalne testy; brak GitHub Actions jako prawdy corp
- Multi-repo katalog
- Self-repair fabryki jako osobny temat

## Różnice względem liderów KB

| Temat | godark / gp-foundry | Lokay (stan badań napraw) |
|-------|---------------------|---------------------------|
| Reviewer bez write | Osobny agent | Zależnie od slotu / PR triage |
| Executor | Docker CLI lub Actions | Daemon + LaunchAgent na mini-m4-0 |
| Escape limbo | Label po N retry | Walka z park labels / stuck.json |
| Spec scenarios | Human scenario → ephemeral tests | Issue text + Done means |
| Single-repo focus | Często 1 repo | Świadomy multi-repo mill |

## Wnioski miękkie

1. Najbliższe open-source „dosłownie dark factory”: **godark** i **gp-foundry**.
2. Wartość nie w kolejnym tool-calling agencie, tylko w **harness + bounded gates + escape**.
3. Host (mini) i tip `main` są częścią definicji naprawy — gp-foundry tego unika, bo executor = GitHub.

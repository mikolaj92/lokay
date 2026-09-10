# Cursor: Towards self-driving codebases (Feb 2026)

Źródło: https://cursor.com/blog/self-driving-codebases (Wilson Lin)

## Co Cursor **odrzucił**

| Iteracja | Co było | Czemu padło |
|----------|---------|-------------|
| 1. Self-coordination | Równi agenci + shared lock file | Lock hell, contention, nikt nie bierze dużych zadań |
| 2. Planner → Executor → Workers + Judge | Sztywny plan z góry | Bottleneck najwolniejszego workera; plan się starzeje |
| 3. Continuous executor (bez osobnego plannera) | Jeden agent planuje i spawnuje | Pathologie: sleep, robi robotę sam, premature done — **za dużo ról naraz** |

## Co wygrało: **rekurencyjni plannerzy + izolowani workerzy**

To NIE jest „zero plannera”. To jest **self-similar hierarchy**:

1. **Root planner** — posiada cały cel użytkownika. **Nie koduje.** Nie wie kto bierze taski.
2. **Subplanners** — gdy scope da się podzielić, spawnują się rekurencyjnie; każdy **w pełni posiada** swój wycinek.
3. **Workers** — nie znają większego systemu; własna kopia repo; jeden **handoff** z powrotem (done + concerns + deviations).

Handoff wraca do plannera jako follow-up → system zostaje w ruchu (self-converging), bez global sync i bez cross-talk.

Integrator (centralny merge gate) został **usunięty** jako red-tape bottleneck.

## Tradeoffs świadome

- Nie 100% green na każdy commit — stały mały error rate + okresowy green-branch fixup.
- Turbulencja (kolizje plików) OK; system ma konwergować, nie być lock-perfect.
- Intent/spec ważniejsze niż harness przy skali (złe instrukcje × 1000 agentów).

## Mapowanie na intuicję „jak autonom Mazura”

Nie jest to cytat Cursora. Analogia robocza:

| Mazur (autonom) | Cursor harness |
|-----------------|----------------|
| Układ steruje sobą | Root planner posiada cel i dalej planuje po handoffach |
| Zachowuje zdolność sterowania (homeostat) | Freshness, anti-fragile, recovery innych agentów |
| Korelator + sprzężenie zwrotne | Handoff → planner → nowe taski (pętla informacji w górę) |
| Nie jest „jednym grubym pudełkiem ról” | Continuous executor padł właśnie od przeładowania ról |

Wniosek dla Lokaya: pattern który „się pojawia” to **rekurencyjne posiadanie celu + wąscy workerzy**, nie flat swarm i nie continuous executor z dziesięcioma kapeluszami.

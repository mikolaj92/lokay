# Marian Mazur — autonom (cybernetyka) a dark factory

## Definicja

Mazur: **układ autonomiczny** = (1) potrafi sobą sterować, (2) potrafi **zachować** tę zdolność sterowania.
Źródła: *Cybernetyczna teoria układów samodzielnych* (1966); *Cybernetyka i charakter*; http://autonom.edu.pl

Organy w modelu: receptory, efektory, korelator, **homeostat**, akumulator.
Homeostat utrzymuje równowagę procesów energetycznych i informacyjnych — bez niego układ „steruje raz” i pada.

## Czemu to wraca przy AI factories

Współczesne harnessy (Cursor self-driving, godark, gp-foundry supervisor, Lokay self_repair) nieświadomie szukają tego samego:

- nie wystarczy „agent robi kod” (efektor),
- trzeba **utrzymać zdolność dalszej pracy**: freshness kontekstu, bounded retry, re-drive stranded, anti-fragile przy padzie workera,
- sprzężenie: wynik/handoff wraca do właściciela celu (korelator), nie ginie w czacie.

## Co to NIE jest

- Nie jest to przepis na LangGraph.
- Nie zastępuje SDLC (PR, testy, merge policy).
- Nie mówi „wyrzuć graf” — mówi: graf/harness musi **zachowywać autonomię**, nie tylko odpalać kroki.

## Most do strategii agent-first

Mazur budował autonomy jako całość. Cursor doszedł empirycznie do rekurencyjnego self-similar ownership.
Praktyczna ścieżka inżynierska (patrz [STRATEGY_AGENT_FIRST.md](./STRATEGY_AGENT_FIRST.md)):
najpierw **działający** pętlowy autonom (nawet 100% agentów), potem wycinanie organów w deterministyczne klocki — bez utraty homeostatu (ciągłość issue→efekt).

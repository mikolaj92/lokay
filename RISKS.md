# Rejestr ryzyk R1–R25

Analizowany SHA: **`594334bd391da5958153d864b972a869cdecf565`**.
Historia: **`f343c0845efe7bdc2a34a0b3df6ab0fe8cc93b33`**.
Przejścia i granice ticka: [STATE_MACHINE.md](STATE_MACHINE.md).
Incydenty nie są dowiedzione przez samo występowanie ryzyka: [INCIDENTS.md](INCIDENTS.md).

## Pochodzenie identyfikatorów

Przekazana treść [#1816](https://github.com/mikolaj92/lokay/issues/1816) wymienia zakresy R1–R25 przy propozycjach #1806–#1815.
Nie zawiera pełnego dawnego RISKS.md ani indywidualnych definicji większości R.
Nie znaleziono tych trzech dokumentów w analizowanym drzewie.
**Zachowujemy identyfikatory i powiązania, ale poniższe tematy są roboczym indeksowaniem grup z issue.**
Nie twierdzimy, że odtworzono dokładne dawne tytuły lub rozdział tematów wewnątrz każdej grupy.
Dowody w tabeli opisują mechanizmy obecnego kodu. Skutki oznaczają możliwości, nie potwierdzone incydenty.
„Ograniczone” oznacza zmianę mechanizmu, nie dowód skuteczności na produkcji.

## Rejestr

| ID | Powiązanie z materiału | Temat roboczy / granica identyfikacji | Dowód aktualnego mechanizmu | Możliwy skutek | Status w analizowanym SHA |
| --- | --- | --- | --- | --- | --- |
| R1 | #1806 | długi tick | deadline przed pick; pętle sprawdzają deadline [start][run][config] | inne repo czeka podczas pracy | ograniczone budżetem 2700 s; brak twardej granicy I/O |
| R2 | #1807 | zastępcza miara postępu | diff, hunk bez nagłówków linii, findings, trzy counts w Fix [start] | zmiana tekstu może udawać naprawę | ograniczone; nadal heurystyka, nie dowód semantyczny |
| R3 | #1809 | konkret przy wielu opcjach | follow-up p(file) ≥ 2 × p(none), wybrany plik musi mieć maksimum [check] | błędne wskazanie lub brak konkretu | próg względny wdrożony; model nie gwarantuje trafności |
| R4 | #1808 | deterministyczny błąd i backoff | needs_help: transient regex; powtórka nietransientna lub fix_code → Plan [start] | regex może źle sklasyfikować błąd | ograniczone; backoff 60–3600 s tylko dla transient |
| R5 | #1807 | re-Plan bez pamięci | replan_prompt dodaje plan_history, fix_history, stan, końcówkę rounds i logi CI [start] | model może powtórzyć nieskuteczną propozycję | historia przekazywana; jej wykorzystanie niepotwierdzone |
| R6 | #1807 | Build bez nowego postępu | previous_head i log commitów; wyjątek dla nieopublikowanych commitów / istniejącego PR [build][start] | ponowne sprawdzanie starego rozwiązania | ograniczone, jawne ścieżki odzyskania; commit nie dowodzi naprawy |
| R7 | #1807 | ponawianie Fix | stalled po identycznym diff albo findings+hunk albo niemalejących counts; dispute może zmienić ścieżkę [start] | pętla zmieniających się, nietrafnych uwag | ograniczone; brak limitu rund, jest deadline |
| R8 | #1809 | wspólne zapytanie lensów | osobne decide_batches dla każdego check_*.json [start][check] | podobne odpowiedzi nie są niezależnym dowodem | rozdzielone lensy; liczba wywołań zależy od partii/follow-up |
| R9 | #1809 | review bez treści / bez konkretu | body hunków do 1500 znaków; trim wire; issue bez konkretu tworzy replan [check][start] | obcięta treść ukrywa błąd | częściowo ograniczone; identyczne uwagi ≥5 kategorii mogą trafić tylko do notes |
| R10 | #1810 | scope z tytułu | code_scope_issue czyta ## Pliki [scope] | błędny plan daje błędny zakres | regex tytułu zastąpiony; poprawność planu nadal warunkiem |
| R11 | #1810 | zakres diffu | porównanie listy ścieżek, wyjątki test/lockfile, scope disputable [scope][start] | niepożądana zmiana w dozwolonym pliku przejdzie kontrolę ścieżek | nadal otwarte na poziomie semantyki |
| R12 | #1814 | opis PR nie opisuje zmiany | pr_body używa stat, plików, subjectów i końcówki pi_response [build][start] | odpowiedź pi może być niedokładna | ograniczone; opis nie dowodzi wdrożenia |
| R13 | #1812 | commit zastanych zmian | snapshot worktree_status przed pi; commit wybranych zmienionych ścieżek [build] | pi modyfikując zastany plik może włączyć wcześniejsze zmiany | ograniczone per ścieżka, nie per hunk |
| R14 | #1812 | artefakty i lockfile | generated_cleanup przy setup/CI; tidy usuwa artefakty i niespójne lockfile [build][guard] | potrzebny artefakt może być źle rozpoznany | ograniczone heurystyką nazw; nie uniwersalna klasyfikacja |
| R15 | #1806 | długie oczekiwania (dokładny dawny opis nieznany) | retry_sleep respektuje wspólny deadline [run][start] | repo czeka do końca budżetu | ograniczone; sleep usługi jest poza tickiem |
| R16 | #1812 | outside_worktree | host guard i lista zmienionych ścieżek; macOS sandbox; Build/Fix wracają do Plan [host][run][start] | zapis poza dozwolonym zakresem lub zły branch | ograniczone; sandbox nie jest stosowany poza macOS |
| R17 | #1811 | testy nie obejmują pakietu | Check chodzi do nadrzędnego pyproject i porównuje tested_cwds, gdy tests skonfigurowane [start][check] | nieobjęty pakiet lub zły marker może dać fałszywe pokrycie | ograniczone do rozpoznanych pakietów i markerów, nie pokrycia linii |
| R18 | #1811 | no checks / did_run | no_ci osobno; summary/markery w local_ci; test=[] daje tested=false [gh][check] | Merge bez wykonanych testów pozostaje możliwy | jawna granica; no_ci dopuszczone wraz z local green |
| R19 | #1813 | heartbeat jako „zdrowie” | osobny pulse, failures i last_error, node_since [observe][state] | świeży heartbeat bez postępu | ograniczone; heartbeat to żywotność, nie poprawność |
| R20 | #1813 | idle bez powodu | pick zapisuje host_down/idle_backoff/no_work; monitor alarmuje pierwsze dwa [start][observe] | busy/filtr PR może wyglądać jak no_work | częściowo ograniczone; brak osobnego idle_reason=lock_busy |
| R21 | #1813 | wiek pętli issue | issue_since przy pierwszym pick, reset przy merged; monitor issue/queue age [state][observe] | alarm mimo aktywnej pracy albo brak pełnej informacji | pomiar wdrożony, skuteczność alarmu na hostach niepotwierdzona |
| R22 | #1806 | czas operacji (dokładny dawny opis nieznany) | pi bez limitu ciszy i czasu; pozostałe procesy timeout do 3600 s; cleanup 5 s [run] | proces/plikowa operacja może zużyć czas kolejki | pi i I/O bez twardej granicy |
| R23 | #1806 | blokowanie floty (dokładny dawny opis nieznany) | repo_attempt porządkuje repo; otwarte PR globalnie blokują wybór nowych issue [start][state] | issue bez PR może głodować nawet w innym repo | nadal możliwe; brak gwarancji czasu dla dowolnej floty |
| R24 | #1815 | skip/epic | load_skips nie istnieje; is_task odrzuca nowe epic/tracker/alarm; otwarte PR wybierane bez is_task [start] | nowe grupujące issue nie jest wykonywane | skip-file usunięty; filtrowanie nowych issue pozostaje |
| R25 | #1814 | cleanup po merge | merge_sha zapisuje merged przed cleanup; wyjątek cleanup to warning [merge] | worktree pozostaje; błąd zapisu po zdalnym merge nadal może dać failed | cleanup ograniczone; atomowość z GitHub nie jest zapewniona |

## Historia zmian, nie dowód wdrożenia

Lokalny `git log --all --grep` zawiera następujące commity powiązane z propozycjami:

| Materiał | Commit zmiany | Znaczenie dowodu |
| --- | --- | --- |
| #1806 | [3a6d4a8c94f2bb81b23d66b93845fe943796d58c](https://github.com/mikolaj92/lokay/commit/3a6d4a8c94f2bb81b23d66b93845fe943796d58c) | implementacja budżetu; sam tytuł nie ustala zamknięcia issue |
| #1807 | [ce6d19c1](https://github.com/mikolaj92/lokay/commit/ce6d19c1) | diff/postęp i historia |
| #1808 | [724bd51f](https://github.com/mikolaj92/lokay/commit/724bd51f) | deterministyczne błędy |
| #1809 | [dcce3d58](https://github.com/mikolaj92/lokay/commit/dcce3d58) | lensy, hunki, konkret |
| #1810 | [f448b39f](https://github.com/mikolaj92/lokay/commit/f448b39f) | zakres z planu |
| #1811 | [659b3c9d](https://github.com/mikolaj92/lokay/commit/659b3c9d) | CI, did_run |
| #1812 | [3d88968b](https://github.com/mikolaj92/lokay/commit/3d88968b) | higiena worktree |
| #1813 | [92c0b4d9](https://github.com/mikolaj92/lokay/commit/92c0b4d9) | obserwacja |
| #1814 | [ce51ba55](https://github.com/mikolaj92/lokay/commit/ce51ba55) | opis PR i cleanup |
| #1815 | [c4bd8c55](https://github.com/mikolaj92/lokay/commit/c4bd8c55) | skip/epic; później dodano tracker i ochronę otwartych PR |

Stan ryzyka wynika z odczytanego kodu przypiętego poniżej, nie z tytułu commita ani samego zamknięcia issue.
Nie wdrażamy zbiorczo kolejnych napraw i nie zmieniamy polityki grafu w tej zmianie dokumentacyjnej.

## Źródła kodu

[start]: https://github.com/mikolaj92/lokay/blob/594334bd391da5958153d864b972a869cdecf565/src/lokay/start.py
[run]: https://github.com/mikolaj92/lokay/blob/594334bd391da5958153d864b972a869cdecf565/src/lokay/run.py
[config]: https://github.com/mikolaj92/lokay/blob/594334bd391da5958153d864b972a869cdecf565/src/lokay/config.py
[build]: https://github.com/mikolaj92/lokay/blob/594334bd391da5958153d864b972a869cdecf565/src/lokay/build.py
[check]: https://github.com/mikolaj92/lokay/blob/594334bd391da5958153d864b972a869cdecf565/src/lokay/check.py
[scope]: https://github.com/mikolaj92/lokay/blob/594334bd391da5958153d864b972a869cdecf565/src/lokay/scope.py
[gh]: https://github.com/mikolaj92/lokay/blob/594334bd391da5958153d864b972a869cdecf565/src/lokay/gh.py
[observe]: https://github.com/mikolaj92/lokay/blob/594334bd391da5958153d864b972a869cdecf565/src/lokay/observe.py
[state]: https://github.com/mikolaj92/lokay/blob/594334bd391da5958153d864b972a869cdecf565/src/lokay/state.py
[host]: https://github.com/mikolaj92/lokay/blob/594334bd391da5958153d864b972a869cdecf565/src/lokay/host_guard.py
[merge]: https://github.com/mikolaj92/lokay/blob/594334bd391da5958153d864b972a869cdecf565/src/lokay/merge.py

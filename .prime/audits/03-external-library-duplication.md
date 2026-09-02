# Audyt duplikacji bibliotek zewnętrznych — Lokay

**Zakres:** tylko odczyt kodu produktu i zależności; stan `main` przy `e307e34` wraz z niezacommitowanymi zmianami.  
**Źródła przeczytane:** `AGENTS.md`, `README.md`, `docs/PROCESS.md`, `docs/GRAPH.md`, `docs/UNIX.md`, `docs/AUTONOMY.md`, `docs/NO_STUBS.md`, `pyproject.toml`, `uv.lock`; jawne repo siostrzane `../Fala`, `../app-factory`, `../Kofte`, `../sqlite.fire`; lokalny kontrakt CLI `gh`.

## Stan working tree

Na początku audytu `git status --short` wskazywał:

```text
 M src/lokay/preflight.py
 M src/lokay/proc/read_status_lease.py
 M tests/test_preflight.py
 M tests/test_status.py
 M uv.lock
```

`uv.lock` zmienia Fala z `0.7.26` na `0.7.28` (`uv.lock:81-83` w bieżącym drzewie). Zmiany w `read_status_lease.py` także przejrzano. Raport nie zmienia kodu produktu ani testów.

## Wiążące granice

- `AGENTS.md:6-9`: procesy wieloetapowe składa Fala, silniki domenowe pozostają osobno, Fala orkiestruje.
- `AGENTS.md:21-27`: produktem są grafy Fala; nowa kolejność należy do pakietu Fala.
- `docs/PROCESS.md:7-18,44-50`: Fala jest procesem, a atomy i adaptery są wymienne.
- `docs/UNIX.md:7-13`: wyższe przepływy mają wywoływać atomy/grafy, a nie wchłaniać cudze silniki; kolejność należy do Fali.
- Zależność jest jawna: `pyproject.toml:10,20`, `uv.lock:81-83` wskazują `../Fala`, obecnie `0.7.28`.

# Potwierdzone problemy

## P1. Lokay ręcznie rozwija globalny input na input każdego efektora

**Severity: MEDIUM**

**Pliki/linie:**
- Lokay: `src/lokay/graph_run.py:255-272,301-309`.
- Odpowiednik Fala: `../Fala/python/fala/host.py:395-405,440-446`; `../Fala/mojo/fala/correlation.mojo:390-407,491-492`.

**Dowód:** `run_path` ponownie parsuje TOML, odnajduje `path_id`, pobiera wszystkie efektory i tworzy `effector_inputs = {id: dict(base_input) ...}`. Publiczne `host_run_package` ma już osobny parametr `inputs`, a runtime Fali scala globalne pola wejściowe z ewentualnymi polami per-effector przed instancjacją każdego efektora. To jest ten sam fan-out danych, wykonany drugi raz po stronie konsumenta.

**Naruszony kontrakt/granica:** Fala ma orkiestrację i instancjację grafu; Lokay powinien dostarczyć zewnętrzną kopertę, nie odtwarzać listę węzłów (`AGENTS.md:6-9,21-27`; `docs/UNIX.md:7-13`).

**Konsekwencja:** Lokay zależy od wewnętrznego kształtu manifestu i może rozjechać się z semantyką wejść Fali. Każdy efektor dostaje niepotrzebną kopię słownika, a kod konsumenta musi znać wszystkie węzły ścieżki.

**Najmniejsza poprawka:** usunąć odczyt ścieżki i budowę `effector_inputs`; wywołać `host_run_package(..., inputs=base_input)`. `effector_inputs` zostawić tylko dla rzeczywistych nadpisań jednego efektora, jeśli takie powstaną.

## P2. Tekstowy slicer pakietu powtarza wybór `path_id` należący do Fali

**Severity: MEDIUM**

**Pliki/linie:**
- Lokay: `src/lokay/graph_run.py:51,136-170,220-229`.
- Odpowiednik Fala: `../Fala/python/fala/host.py:395-408,417-435`; `../Fala/python/fala/_native.mojo:252-267`.

**Dowód:** Lokay rozcina surowy TOML po literalnym `[[correlation_paths]]`, regexem wybiera `id`, zapisuje nowy manifest zawierający jedną ścieżkę, po czym nadal przekazuje `path_id`. Host Fali ładuje pełny manifest i w natywnym runtime sam wyszukuje dokładnie żądane `path_id`; brak ścieżki kończy błędem. Podmiana `PLACEHOLDER_PROJECT` jest osobną potrzebą Lokaya, lecz wycinanie ścieżki nią nie jest.

**Naruszony kontrakt/granica:** wybór i ładowanie ścieżki to część graph runtime Fali, nie adapter Lokaya (`AGENTS.md:6-9`; `docs/PROCESS.md:7-18`).

**Konsekwencja:** powstaje drugi, kruchy parser formatu pakietu. Komentarze, przyszła składnia lub tablice TOML mogą być poprawne dla Fali, a błędne dla slicera. Lokay utrzymuje też testy i izolowane kopie manifestów tylko dla obejścia funkcji już obecnej w host API.

**Najmniejsza poprawka:** materializować pełny manifest wyłącznie z podmianą `PLACEHOLDER_PROJECT`, a wybór pozostawić `host_run_package(path_id=...)`. Jeśli pełny manifest ma zmierzony koszt, najmniejsza poprawka biblioteczna to dodać oficjalne `materialize_path`/cache w Fali i użyć tego API zamiast parsowania tekstu w Lokayu.

## P3. Lokay ponownie dekoduje standardowy `effector_results` Fali

**Severity: MEDIUM**

**Pliki/linie:**
- Lokay: `src/lokay/graph_run.py:335-350,373-445,446-483`.
- Odpowiednik Fala: `../Fala/python/fala/host.py:408-413`; dodatkowe potwierdzenie wersji: `../Fala/CHANGELOG.md:68-79`.

**Dowód:** kontrakt Fali 0.7.28 mówi, że `effector_results` jest mapą po ID i zawiera zdekodowane `output` oraz `error`. Lokay mimo to obsługuje `output_json`, ponownie wykonuje `json.loads`, rekonstruuje ID przez `rsplit(':', 1)` i akceptuje alternatywną listę `processes`. Reguły produktowe Lokaya z `graph_run.py:455-489` (cleanup i `host_updated`) nie są duplikacją i powinny pozostać.

**Naruszony kontrakt/granica:** adapter konsumenta powiela normalizację gwarantowaną przez przypiętą bibliotekę; Fala ma być jedynym runtime i źródłem formatu wyników (`AGENTS.md:6-9`; `docs/PROCESS.md:7-18`).

**Konsekwencja:** niepoprawne lub historyczne formaty mogą zostać cicho zaakceptowane, zamiast zawieść na granicy Fali. Powstają dwa miejsca definiujące statusy i dekodowanie błędów.

**Najmniejsza poprawka:** dla przypiętej Fali czytać wyłącznie `effector_results[id].output/error/status`; usunąć dekodowanie `output_json` i fallback `processes`. Zachować cienką, domenową projekcję wyników i wyjątki tras Lokaya. Jeżeli downgrade jest świadomie wspierany, przypiąć adapter wersją, a nie autodetekcją kształtu.

## P4. Lokay utrzymuje journal Fali przez obrót całych plików obok publicznego API maintenance Fali

**Severity: MEDIUM**

**Pliki/linie:**
- Lokay: `src/lokay/fala_journal.py:19-42,45-62,65-112`; wywołanie `src/lokay/compose/daemon_cycle.py:75-84`.
- Odpowiednik Fala: `../Fala/python/fala/__init__.py:5-8,17-31,63`; `../Fala/python/fala/host.py:525-578`.

**Dowód:** Lokay skanuje wszystkie `state.sqlite`, po limicie bajtowym przemianowuje cały plik, usuwa `-wal`/`-shm` i przycina archiwa. Fala eksportuje `maintain_journal`, które w natywnej transakcji wybiera i usuwa terminalne runy, chroni nieterminalne, wykonuje reaction GC i opcjonalny `VACUUM`; cel „retencja/utrzymanie journalu” jest więc obsługiwany przez właściciela bazy.

**Naruszony kontrakt/granica:** trwały journal i jego spójność należą do silnika Fali. Lokay manipuluje plikami bazy i sidecarami na zewnątrz silnika (`AGENTS.md:6-9`; `docs/PROCESS.md:7-18`).

**Konsekwencja:** polityka retencji rozchodzi się z modelem Fali. Obrót całej bazy traci także nieterminalne dane i omija natywne reguły/GC; ręczne usuwanie sidecarów wiąże Lokaya z implementacją SQLite.

**Najmniejsza poprawka:** zastąpić ręczne kasowanie/rename wywołaniem `fala.maintain_journal(..., vacuum=True)` pod istniejącą blokadą młyna. Ponieważ API Fali jest czasowo/liczbowo, a Lokay ma twardy limit bajtowy, najpierw dodać do Fali najmniejszy parametr/politykę limitu rozmiaru albo po maintenance sprawdzać rozmiar i fail-closed zgłaszać brak zejścia poniżej limitu; nie przenosić logiki SQLite z powrotem do Lokaya.

## P5. `repo_mutex` odtwarza mutual exclusion przez heurystyczne skanowanie procesów zamiast atomowego `flock`

**Severity: HIGH**

**Pliki/linie:**
- Lokay: `src/lokay/proc/repo_mutex.py:20-26,56-67,85-109,112-160,179-224`.
- Gotowy kontrakt obecny już w tym repo/stdlib: `src/lokay/state.py:10-22`; `src/lokay/pass_history.py:18-32` (`fcntl.flock(..., LOCK_EX)`; do próby służy `LOCK_NB`).

**Dowód:** narzędzie parsuje tekst `ps`, rozpoznaje argv własnych poleceń, szuka repo regexami, a nawet odpytuje `gh issue view`, aby zdecydować, czy PID „trzyma mutex”. Nie ma atomowego acquire. Między inspekcją a uruchomieniem kodera drugi proces może przejść ten sam test. POSIX `flock`, już użyty przez Lokaya, daje atomowe `LOCK_EX | LOCK_NB` na repo-scoped pliku.

**Naruszony kontrakt/granica:** locking/lease powinien mieć jeden wydzielony, atomowy mechanizm. Obecny atom nazywa heurystyczną obserwację procesów „Mutex: one live coder per repo” (`repo_mutex.py:1-7`), choć nie spełnia kontraktu mutexu. Narusza to także obietnicę serialności z `AGENTS.md:35-38`.

**Konsekwencja:** wyścig może uruchomić dwóch koderów/worktree dla jednego repo; zmiana nazwy procesu/argv może dać false negative, a obcy prompt pasujący regexem false positive. Wywołanie GitHub w ścieżce blokady dodaje awarie sieciowe do lokalnego mutual exclusion.

**Najmniejsza poprawka:** utworzyć repo-scoped lockfile, atomowo nabyć `fcntl.flock(fd, LOCK_EX | LOCK_NB)` w procesie, który żyje przez cały slot kodera, i zwolnić przy wyjściu. Kontrolę zamkniętego issue zostawić jako osobną higienę/reconciliation, nie jako implementację blokady. Nie jest potrzebna nowa zależność.

# Hipotezy / wymagają decyzji produktu lub pomiaru

## H1. Slicer może być obejściem kosztu alokacji pełnego manifestu

**Severity: LOW (hipoteza)**  
**Pliki/linie:** `src/lokay/graph_run.py:159-163`; `../Fala/python/fala/_native.mojo:252-267`.

Komentarz mówi o unikaniu alokacji całego katalogu, ale brak profilu lub benchmarku. **Konsekwencja potencjalna:** usunięcie slicera może zwiększyć czas/RSS przy manifeście ok. 6859 linii. **Najmniejszy następny krok:** zmierzyć pełny manifest kontra slice. Jeśli koszt jest realny, naprawić selektywne ładowanie/cache w Fali, nie utrzymywać parsera w Lokayu.

## H2. Retencja Fali może nie realizować twardego limitu 64 MiB

**Severity: MEDIUM (hipoteza)**  
**Pliki/linie:** polityka Lokaya `src/lokay/fala_journal.py:14-29`; API Fali `../Fala/python/fala/host.py:532-578`.

`maintain_journal` ma wiek, `keep_last` i `vacuum`, ale nie jawny limit bajtowy. Nie potwierdzono, że daje ten sam rezultat operacyjny. **Najmniejszy następny krok:** rehearsal na kopii dużego journalu; jeśli nie wystarcza, dodać byte-budget po stronie Fali.

## H3. Publikacja „review” jako komentarza może omijać właściwy obiekt GitHub Review

**Severity: MEDIUM (hipoteza semantyczna)**  
**Pliki/linie:** `src/lokay/pr_review_io.py:70-82,99-125`; `src/lokay/gh_prs.py:58-65`; werdykty `src/lokay/pr_review.py:15-21,129-137`.  
**Dokładny odpowiednik:** `gh pr review <number> --approve|--request-changes|--comment --body ...`; obecne `gh pr comment` tworzy tylko komentarz.

Jeżeli kontrakt „review” ma wpływać na branch protection, komentarz + etykieta odtwarza osobny ledger zamiast użyć natywnego review. Jeśli natomiast celowo nie wolno self-approve, obecne zachowanie jest poprawnym adapterem. **Konsekwencja potencjalna:** GitHub nie widzi approval/request-changes jako review. **Najmniejsza poprawka po decyzji:** mapować werdykt na `gh pr review`, a etykiety zostawić wyłącznie jako ledger.

## H4. JSONL persistence powtarza bazowe mechanizmy SQLite, ale brak drop-in biblioteki Python w zależnościach

**Severity: LOW (hipoteza architektoniczna)**  
**Pliki/linie:** `src/lokay/state.py:10-22`; `src/lokay/pass_history.py:18-32`; `src/lokay/state_compact.py:64-91`; odpowiednik sąsiedni `../sqlite.fire/README.md:42-52,79-86,113-122`.

Jest tu ręczne blokowanie, serializacja, retencja i atomowy replace. `sqlite.fire` jest jednak API Mojo i nie jest zależnością Lokaya, więc nie jest potwierdzonym drop-in replacement. **Najmniejszy następny krok:** dopiero po wykazaniu potrzeby transakcyjnych zapytań rozważyć stdlib `sqlite3` albo wydzielony atom Mojo korzystający z `sqlite.fire`; nie migrować dla samej unifikacji.

# Sprawdzone obszary bez potwierdzonej duplikacji

- **HTML/platform:** `src/lokay/proc/status_server.py:9,21-54` używa `app_factory.platform`; odpowiednik jest w `../app-factory/app_factory/platform.py:158-193,269-297`. Lokalny template jest treścią produktu, nie kopią platformy.
- **Review style:** `src/lokay/review_style.py:12-19` używa `Kofte.Translator`; lokalne markery są kontraktem domenowym, nie drugim translatorem.
- **GitHub list/view/checks/labels:** adaptery wywołują `gh` z jego natywnymi flagami. Nie znaleziono drugiego klienta HTTP ani własnej implementacji protokołu GitHub.
- **Fala locking/lease w niezacommitowanym `read_status_lease.py`:** nowy kod `src/lokay/proc/read_status_lease.py:7-58` odczytuje lease zdrowia młyna, nie lease procesów z journalu Fali. `fala.inspect_leases` (`../Fala/python/fala/__init__.py:8,31,58`) dotyczy schema-v6 process claims, więc nie uznano tego za ten sam kontrakt.

## Priorytet minimalizacji

1. Naprawić `repo_mutex` atomowym repo-scoped `flock`.
2. Użyć `inputs=` Fali i usunąć fan-out po efektorach.
3. Oprzeć normalizację na gwarantowanym `effector_results` 0.7.28.
4. Przenieść maintenance journalu do Fali, uzupełniając tam byte-budget.
5. Po benchmarku usunąć slicer albo dodać oficjalne selektywne materializowanie w Fali.

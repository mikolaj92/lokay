# Audyt granic Python/Unix i spaghetti

**Tryb:** tylko odczyt. **Repo:** `/Users/mini-m4-0/Developer/OSS/lokay`.
**Zakres:** `src/lokay/proc`, `compose`, `organ`, `graph_run`, `passkit`, `scripts`, `[project.scripts]`; w tym bieżąca naprawa health lease.
**Stan drzewa:** niezacommitowane zmiany w `src/lokay/preflight.py`, `src/lokay/proc/read_status_lease.py`, `tests/test_preflight.py`, `tests/test_status.py`, `uv.lock`.

## Podsumowanie

Znalazłem **8 potwierdzonych problemów**: 3 wysokie, 4 średnie i 1 niski. Najpilniejszy jest regres w niezacommitowanej naprawie lease: pojedynczy osierocony plik/symlink może wywrócić read-only `lokay status`. Nie znalazłem bezpośredniej logiki GitHub/git/agent w `compose/*`; w tym zakresie granica jest zachowana. Wszystkie 108 wpisów `[project.scripts]` wskazują na istniejące moduły i `main`.

## Mapa odpowiedzialności

- `fala/lokay.fala-package.toml`: kolejność produktu i recovery.
- `src/lokay/compose/*`: wejścia ścieżek/top-level lokay; zasadniczo walidacja CLI i uruchomienie Fala/subflow.
- `src/lokay/graph_run.py`: wybór/materializacja pakietu, izolacja journalu, uruchomienie hosta i normalizacja wyników.
- `src/lokay/fala_organ.py` + `src/lokay/organ/*`: dispatcher/binding effectorów do atomów.
- `src/lokay/proc/*`: atomy Unix i część domenowych reduktorów.
- `src/lokay/passkit/*`: współdzielone IO/working/health/support passu.
- `scripts/lokay-service.sh`: OS caretaker LaunchAgent.
- `[project.scripts]`: 108 publicznych CLI, głównie bezpośrednio do `proc`, wybrane wejścia do `compose`.

# Potwierdzone problemy

## P1 — HIGH — read-only status może się wywrócić na osieroconym/równolegle usuniętym lease

- **Pliki/linie:** `src/lokay/proc/read_status_lease.py:27-46`, w szczególności `30-34`; integracja: `src/lokay/organ/status_boundary.py:29-32,49-60`.
- **Dowód:** nowy kod sortuje kandydatów przez `key=lambda path: path.stat().st_mtime` (`30-34`). To dzieje się przed `try` z linii `35`; `OSError` jest łapany dopiero w `35-46`. Reprodukcja w środowisku repo: dangling symlink `health-lease-x-y` powoduje `FileNotFoundError`, zamiast envelope statusu. To bezpośrednio dotyczy niezacommitowanej naprawy health lease.
- **Naruszony kontrakt/granica:** read-only status ma obserwować stan i zwracać JSON, nie być kruchy na śmieci/race w katalogu stanu (`README.md:1451`; `docs/UNIX.md:12-18`, zasady jednego procesu i JSON envelope).
- **Konsekwencja:** jeden osierocony symlink albo unlink między `glob()` a `stat()` może przerwać `status_snapshot`, więc operator traci odczyt właśnie podczas awarii/cleanup.
- **Najmniejsza poprawka:** sortować po nazwie bez `stat()`, albo zebrać `(mtime, path)` w osobnej pętli z `try/except OSError` i pominąć znikające wpisy. Dodać test dangling symlink i race/unlink.


## P2 — HIGH — status miesza „aktywnego właściciela runu” ze zweryfikowaną capability

- **Pliki/linie:** `src/lokay/proc/read_status_lease.py:27-46,53-64`; `src/lokay/proc/reduce_status_snapshot.py:45-55`; test utrwalający semantykę: `tests/test_status.py:194-214`.
- **Dowód:** pełna walidacja tokenu działa tylko, gdy status odziedziczył `LOKAY_HEALTH_LEASE` (`53-55`). Bez tokenu `_active_run_lease()` sprawdza zgodny tekst `lock_path`, niewygasły timestamp, żyjący dowolny PID i zajęty lock (`27-46`), po czym publikuje identyczne `lease_ok=True` (`58-62`). Nie sprawdza token hash, `issued_at`, owner/mode ani symlinka. Reducer nie odróżnia obu faktów (`reduce_status_snapshot.py:54-55`).
- **Naruszony kontrakt/granica:** capability do mutacji i obserwacja aktywnego runu to osobne domeny. Status ma składać read-only fakty (`README.md:448-452`); health lease jest bramą mutacji.
- **Konsekwencja:** CLI/dashboard może uznać `lease_ok=true` za zdrową capability/preflight, chociaż status potwierdził tylko korelację rekordu i zajętego locka. Żyjący PID z rekordu i lock trzymany przez inny proces wystarczą.
- **Najmniejsza poprawka:** bez odziedziczonego tokenu pozostawić `lease_ok=None`; dodać osobne `run_active`, `run_lease_path` i `run_observation_reason`.

## P3 — HIGH — capability może być mintowana w product delivery poza właścicielem daemon locka

- **Pliki/linie:** `src/lokay/proc/issue_delivery_launch.py:35-55`; `src/lokay/preflight.py:257-340,364-410`; `src/lokay/proc/restore_factory_lease.py:1-11`.
- **Dowód:** przy braku tokenu launcher produktu sam wywołuje `issue_health_lease()` (`issue_delivery_launch.py:47-53`). Issuer zapisuje lease bez uprzedniego dowodu, że caller posiada dokładny configured lock (`preflight.py:257-340`). Validator dodatkowo uznaje lock za held, gdy `owner_pid == os.getpid()` (`407-410`). Restore ponownie wywołuje ten sam ogólny issuer (`restore_factory_lease.py:6-10`).
- **Naruszony kontrakt/granica:** daemon ma posiadać singleton lock, health lease i initial carrier preflight (`docs/GRAPH.md:25-27`); product delivery ma konsumować delegowaną capability, nie wydawać ją sobie.
- **Konsekwencja:** standalone/fallback product process może stworzyć własny lease; owner-is-self osłabia dowód fizycznego locka. Granica „live mutation tylko po healthy preflight” jest słabsza niż opisany model.
- **Najmniejsza poprawka:** mintowanie dopuścić tylko w wrapperze, który udowodni posiadanie dokładnego configured locka (`lokay-daemon`/direct lokay). `issue_delivery_launch` ma fail-closed bez poprawnej odziedziczonej capability. Restore tylko dla tego samego tokenu i przy jawnym dowodzie delegacji; usunąć ogólne owner-is-self obejście.

## P4 — MEDIUM — atom nazwany read-only może utworzyć `lokay.lock` i duplikuje walidację lease

- **Pliki/linie:** `src/lokay/proc/read_status_lease.py:14-24,27-46`; istniejący validator: `src/lokay/preflight.py:360-434`; kontrakt statusu: `README.md:448-452`.
- **Dowód:** `_lock_is_held()` otwiera `path.open("a+")` (`14-15`), co tworzy brakujący plik. Nowy kod powtarza część flock/liveness/schema z `health_lease_status`, ale z innymi kontrolami.
- **Naruszony kontrakt/granica:** README stwierdza, że żaden node statusu nie zapisuje stanu (`448-452`); `docs/UNIX.md:15-18` zabrania ukrytych side-effectów.
- **Konsekwencja:** samo `lokay status` może zmienić filesystem. Dwie implementacje walidacji już mają różne reguły i będą dryfować.
- **Najmniejsza poprawka:** brak pliku traktować jako inactive; otwierać probe bez `O_CREAT`. Wydzielić wspólną czystą obserwację rekordu/locka, a walidację capability z tokenem pozostawić osobno.

## P5 — MEDIUM — cykl zależności `fala_organ ↔ organ.*`

- **Pliki/linie:** `src/lokay/fala_organ.py:15-18,29-31,45,54,59,63,67`; odwrotne importy m.in. `src/lokay/organ/common.py:350-368`, `src/lokay/organ/factory.py:99-102`, `src/lokay/organ/lanes.py:33`, `src/lokay/organ/implement.py:30`, `src/lokay/organ/publication.py:44`, `src/lokay/organ/agent.py:61`, `src/lokay/organ/recovery.py:98-103`, `src/lokay/organ/self_repair.py:33`.
- **Dowód:** dispatcher importuje handlery organów, po czym organy lokalnie importują dispatcher i pobierają jego prywatne/testowalne hooki, np. `common.py:366-368` bierze `_run_atom_main`. Analiza AST/Tarjana wykryła jeden SCC obejmujący `lokay.fala_organ` i 11 modułów `lokay.organ.*`. Lokalne importy maskują, lecz nie usuwają cyklu.
- **Naruszony kontrakt/granica:** małe, wymienne bloki i oddzielne silniki domenowe (`AGENTS.md:5-9`; `docs/PROCESS.md:33-43`; `docs/UNIX.md:7-17`). Organ jest zależnością dispatchera; nie powinien zależeć zwrotnie od dispatchera.
- **Konsekwencja:** poprawność inicjalizacji zależy od kolejności importu; organy są sprzężone z prywatnymi detalami i patchowaniem `fala_organ`, trudniej je testować/wymieniać samodzielnie.
- **Najmniejsza poprawka:** przenieść `_run_atom_main` i potrzebne hooki do neutralnego modułu runtime/port; najlepiej przekazać callable przez `ctx`. `fala_organ` i organy powinny zależeć jednostronnie od portu.

## P6 — MEDIUM — produktowy caretaker uruchamia bare `python3`

- **Pliki/linie:** `scripts/lokay-service.sh:35-47`, `108-130`, `133-196`, dokładnie wywołania w `38`, `111`, `137`.
- **Dowód:** trzy heredoc-y używają `python3 -`. Skrypt jest produktowym wrapperem LaunchAgent (`README.md:1459`).
- **Naruszony kontrakt/granica:** jawny hard ban: „No bare `python3` for product CLI — use `uv run`” (`AGENTS.md:59`); `docs/UNIX.md:20-21`.
- **Konsekwencja:** caretaker omija przypięte środowisko. Brak/inny systemowy Python może błędnie rozpoznać lock (`38 ... || return 1`), cicho nie zapisać receipt (`111 ... || true`) albo nie zatrzymać ownera (`137 ... || true`).
- **Najmniejsza poprawka:** zamienić na `uv run python -`; jeszcze czyściej wydzielić te trzy operacje jako małe atomy z `[project.scripts]` i wywoływać `uv run`.


## P7 — MEDIUM — wybór ścieżki per-run lease jest potrojony, a ogólny preflight może zostawić env po wyjątku

- **Pliki/linie:** `src/lokay/proc/daemon.py:32-35,51-52`; `src/lokay/compose/run.py:28-46,71-77`; niezacommitowane `src/lokay/preflight.py:1171-1177`.
- **Dowód:** ścieżkę `LOKAY_HEALTH_LEASE_PATH` wybierają daemon, direct lokay i teraz także ogólne `run_preflight`. Nowa gałąź ustawia env przed `issue_health_lease()` i nie cofa go, jeśli issuer rzuci; cleanup mają wrappery, nie funkcja ogólna.
- **Naruszony kontrakt/granica:** lifecycle capability powinien mieć jednego właściciela; preflight nie powinien przejmować części ownership daemon/lokay (`docs/GRAPH.md:25-27`).
- **Konsekwencja:** po błędzie proces bibliotecznego callera może odziedziczyć martwą lokalizację lease; kolejne próby użyją złej ścieżki. Ownership preflight/lease jest niejawny.
- **Najmniejsza poprawka:** ścieżkę wybiera wyłącznie wrapper lifecycle; przekazać ją jawnie do preflight/issuer. Alternatywnie atomowo ustawiać env i cofać je przy każdym nieudanym issue.

## P8 — LOW — atom `proc` zależy od warstwy wiązania `organ`

- **Pliki/linie:** `src/lokay/proc/advance_implementation_selection.py:12-18,29`; `src/lokay/organ/implementation_selection_boundary.py:1-18`; wywołanie zwrotne `src/lokay/organ/queue_conflict_boundary.py:102-107`.
- **Dowód:** atom importuje `SLOT_COUNT` z `lokay.organ.implementation_selection_boundary` (`advance...:13`), po czym boundary wywołuje ten atom. Stała `SLOT_COUNT = 30` żyje w adapterze (`implementation...:5`).
- **Naruszony kontrakt/granica:** `src/lokay/proc/` to wymienne atomy (`README.md:1456`); organ wiąże je do Fala. Zależność powinna iść od adaptera do atomu, nie odwrotnie (`docs/PROCESS.md:13-27`).
- **Konsekwencja:** bezpośrednie użycie atomu ładuje warstwę organ; semantyka limitu jest ukryta w adapterze i może rozjechać reuse/testy.
- **Najmniejsza poprawka:** przenieść `SLOT_COUNT` do neutralnego kontraktu/passkit albo przekazać `slot_count` jawnie z boundary do `run()`.

# Hipotezy / obserwacje wymagające dalszego dowodu

1. **Duże pliki nie są same w sobie potwierdzonymi god-files.** `graph_run.py` ma 528 linii, `fala_organ.py` 285, `passkit/health.py` 209, a kilka atomów przekracza zalecane ~100 linii (`survey_ttl.py` 331, `issue_delivery_occupancy.py` 305, `reap_stale_worktrees.py` 286). Ich funkcje grupują spójne odpowiedzialności; bez wykazania mieszania przepływów nie klasyfikuję samego rozmiaru jako defektu.
2. **`graph_run.py` ma dwa duże skupiska**: runtime/materializacja (`173-332`) i normalizacja (`373-505`). To kandydat do rozdzielenia, lecz nie wykryłem błędu ani drugiej implementacji odpowiedzialności.
3. **Health/preflight/lease mają szeroką powierzchnię**, lecz bieżący kierunek per-run lease jest spójny: daemon wybiera ścieżkę (`proc/daemon.py:32-43`), preflight mintuje (`preflight.py:1171-1177`), `graph_run` propaguje (`graph_run.py:190-207`), daemon odwołuje (`proc/daemon.py:51-52`). Potwierdzonym problemem tej naprawy jest P1, nie sam podział przepływu.
4. **Nie potwierdzono logiki GitHub/git/agent/fleet w `compose/*`.** Skan i inspekcja pokazują głównie CLI, preflight/lease ownership oraz delegowanie do `run_path`/subflow. Nie raportuję naruszenia zakazu z `AGENTS.md:51-52`.

# Weryfikacja

- Przeczytano: `AGENTS.md`, `README.md`, `docs/PROCESS.md`, `docs/GRAPH.md`, `docs/UNIX.md`, `docs/AUTONOMY.md`, `docs/NO_STUBS.md`.
- Sprawdzono `git status --short` i pełny diff niezacommitowanej naprawy lease.
- Uruchomiono: `uv run pytest -q tests/test_status.py tests/test_preflight.py tests/test_passkit_io.py` → **99 passed**.
- Osobna reprodukcja dangling lease → **potwierdzony `FileNotFoundError`**.
- Audyt nie zmienił kodu produktu. Jedynym utworzonym plikiem jest ten raport.

# Audyt izolacji runtime/testów i kontraktów flow

Data audytu: 2026-08-31  
Zakres: health lease, `mill.lock`, dziedziczenie env, detached `issue_to_pr`, read-only status, preflight, daemon, fixtures testowe i artefakty `~/.lokay`.  
Tryb: tylko odczyt kodu; jedynym utworzonym plikiem jest ten raport.

## Podstawa kontraktowa

Przeczytano: `AGENTS.md`, `README.md`, `docs/PROCESS.md`, `docs/GRAPH.md`, `docs/UNIX.md`, `docs/AUTONOMY.md`, `docs/NO_STUBS.md`.

Najważniejsze granice:

- `README.md:318-320`: daemon ma posiadać jedną nierozdzielną capability: singleton lock, unikalną ścieżkę lease i jeden preflight.
- `README.md:448-450`: status składa fakty read-only i nie uruchamia produktu.
- `docs/GRAPH.md:47-54`: caretaker ma zwolnić właściwy `mill.lock` przy ceiling, nie sygnalizując detached `issue_to_pr`.
- `docs/GRAPH.md:289-290`: detached launch publikuje trwałe `starting` przed `Popen` i używa bariery aktywacji.
- `AGENTS.md:13-15`: maszyna stanów ma jawne skutki uboczne.
- `docs/UNIX.md:14`: produkt nie powinien używać bare `python3`.

## Working tree

Audyt objął niezacommitowane zmiany:

- `src/lokay/preflight.py`
- `src/lokay/proc/read_status_lease.py`
- `tests/test_preflight.py`
- `tests/test_status.py`
- `uv.lock`

Zmiana w `preflight.py` poprawnie kieruje nowo wystawiany lease obok skonfigurowanego `state.path`, zamiast do wspólnego `~/.lokay/health-lease`. Nie jest jednak kompletna jako naprawa całej granicy; nowe problemy są opisane niżej.

## Potwierdzone problemy

### P1 — HIGH — read-only status może utworzyć `mill.lock`

**Pliki/linie:**

- `src/lokay/proc/read_status_lease.py:14-23`, szczególnie `path.open("a+")` w linii 15.
- Kontrakt: `README.md:448-450`; diagram `README.md:425-445`.

**Dowód:** nowa funkcja `_lock_is_held()` otwiera ścieżkę w trybie `a+`. Ten tryb tworzy plik, gdy go nie ma. Funkcja jest wywoływana przez read-only atom statusu (`read_status_lease.py:43,56`). Zatem obserwacja lease może zmienić system plików. Test `tests/test_status.py:177-215` przygotowuje istniejący lock i nie sprawdza wariantu bez pliku ani nie porównuje drzewa przed/po.

**Naruszona granica:** status ma tylko odczytywać fakty. Nie może tworzyć singleton lock ani zmieniać stanu runtime.

**Konsekwencja:** `lokay status` może pozostawić artefakt sugerujący istnienie runtime, zmienić diagnostykę i złamać narzędzia, które rozróżniają brak locka od wolnego locka.

**Najmniejsza poprawka:** jeżeli lock nie istnieje, zwrócić `False`; jeśli istnieje, otworzyć go read-only (`os.open(..., O_RDONLY | O_NOFOLLOW)`), bez `O_CREAT`. Dodać test: aktywny-looking lease + brak `mill.lock` => status jest inactive i plik nadal nie istnieje.

### P2 — HIGH — shell caretaker i daemon mogą używać różnych locków oraz różnych receiptów

**Pliki/linie:**

- `scripts/lokay-mill-daemon.sh:20-26` ustala `LOKAY_MILL_LOCK=~/.lokay/mill.lock` niezależnie od configu.
- `scripts/lokay-mill-daemon.sh:35-47,93-97` robi early-return na tym locku.
- `src/lokay/proc/daemon.py:16-23,32-36` wylicza właściwy lock z `cfg.state_path.parent`.
- `scripts/lokay-mill-daemon.sh:108-130` zapisuje ceiling receipt zawsze do `~/.lokay/last-pass.json`.
- `src/lokay/proc/daemon.py:72-75` czyta receipt obok skonfigurowanego locka.
- Kontrakt: `README.md:53-60,318-320`, `docs/GRAPH.md:47-54`.

**Dowód:** dla legalnego configu ze `state.path=/tmp/x/state.jsonl` shell bada `~/.lokay/mill.lock`, a daemon blokuje `/tmp/x/mill.lock`. Jeśli pierwszy jest zajęty przez inny runtime, shell fałszywie kończy bez uruchomienia poprawnej instancji. Jeśli zadziała ceiling, receipt trafia do `~/.lokay`, podczas gdy status/daemon oczekują `/tmp/x/last-pass.json`.

**Naruszona granica:** jedna fizyczna capability i jedno źródło prawdy wyprowadzone ze skonfigurowanego state dir.

**Konsekwencja:** fałszywy overlap, pominięte ticki, niewidoczny `pass_ceiling`, rozjazd status/lease/receipt oraz możliwość równoległych runtime'ów przy ręcznie rozbieżnym `LOKAY_MILL_LOCK`.

**Najmniejsza poprawka:** usunąć shellowy pre-lock (daemon już atomowo blokuje właściwą ścieżkę) albo wyliczyć state dir jednym produkcyjnym CLI opartym o `load_config`. Ceiling receipt zapisywać do tej samej ścieżki. Nie utrzymywać niezależnego override locka.

### P3 — MEDIUM — per-run lease files nie są sprzątane po wymuszonym pass ceiling

**Pliki/linie:**

- `src/lokay/proc/daemon.py:33-35` tworzy unikalną nazwę per run.
- `src/lokay/proc/daemon.py:51-52` sprząta tylko w Python `finally`.
- `scripts/lokay-mill-daemon.sh:133-196,202-220` wysyła `SIGTERM`/`SIGKILL`; nie usuwa lease.
- `src/lokay/proc/read_status_lease.py:30-45` skanuje wszystkie `health-lease-*-*`.

**Dowód runtime (tylko odczyt):** w `~/.lokay` znaleziono 967 ścieżek pasujących do `health-lease*`, w tym setki wygasłych rekordów. Wiele nazw ma PID różny od `owner_pid`, co jest śladem historycznego przepisywania lease przez detached child. Shell po zabiciu procesu usuwa tylko `.pass-ceiling.<pid>` (`scripts/...:217-220`), nie lease. Standardowy `SIGTERM` nie gwarantuje wykonania Python `finally`.

**Naruszona granica:** lease ma być run-scoped i jawnie revoke; stale artifact nie powinien być trwałą częścią indeksu statusu.

**Konsekwencja:** bezgraniczny wzrost katalogu, coraz droższy status (`glob` + sort + parse), szum operacyjny i większa powierzchnia dla fałszywych dopasowań PID.

**Najmniejsza poprawka:** po zakończeniu lock-ownera wykonać bezpieczny GC rekordów wygasłych lub o martwym ownerze, z kontrolą właściciela/typu pliku. Alternatywnie daemon powinien obsłużyć `SIGTERM`, revoke lease i dopiero wyjść; caretaker nadal musi mieć fallback po `SIGKILL`. Dodać test ceiling sprawdzający brak osieroconego lease.

### P4 — MEDIUM — nowy status uznaje lease za aktywny bez walidacji bezpieczeństwa rekordu

**Pliki/linie:**

- `src/lokay/proc/read_status_lease.py:27-45`.
- Pełna walidacja, której tu brakuje: `src/lokay/preflight.py:383-431`.
- Test: `tests/test_status.py:177-215`.

**Dowód:** `_active_run_lease` sprawdza tylko JSON, tekstowy `lock_path`, czas, żywy PID oraz fakt, że *ktoś* trzyma lock. Nie sprawdza: symlinka, regular-file, UID, mode `0600`, spójności tożsamości właściciela locka ani struktury/hash tokena. `os.kill(pid, 0)` wraz z osobnym `_lock_is_held(lock)` nie dowodzi, że podany PID jest właścicielem locka. Reuse PID lub spreparowany/stary rekord może dać `lease_ok=True` podczas dowolnego aktualnie trzymanego locka.

**Naruszona granica:** status lease ma raportować prawdziwy stan tej samej capability, nie korelację dwóch niezależnych faktów.

**Konsekwencja:** fałszywe `active_run`; operator może uznać martwy/obcy runtime za zdrowy. Jest to lokalny problem integralności (ten sam użytkownik), nie zdalna eskalacja.

**Najmniejsza poprawka:** wydzielić wspólny, read-only validator metadanych lease używany przez preflight i status. Status bez tokena może raportować `active_run` tylko po walidacji typu, UID, mode, expiry i lock binding; nie powinien nazywać tego `lease_ok`, jeśli nie potrafi dowieść token capability. Lepsza nazwa: `run_lock_active` + osobne `lease_record_valid`.

### P5 — MEDIUM — test naprawy izolacji nie dowodzi sprzątania ani pełnej izolacji HOME

**Pliki/linie:**

- `tests/conftest.py:16-24` izoluje tylko trzy zmienne env.
- `tests/conftest.py:28-38` mockuje tylko dwa konsumenty receiptów.
- `tests/test_preflight.py:14-29` ma drugi autouse fixture ingerujący bezpośrednio w globalne `os.environ`.
- Nowy test `tests/test_preflight.py:932-947` porównuje wyłącznie jeden legacy plik.
- Produkcyjne ścieżki poza configiem: `src/lokay/proc/issue_delivery_receipts.py:21-29` (`~/.lokay/logs`, `~/.lokay/cycle`).

**Dowód:** suite nie ustawia globalnie testowego `HOME`/runtime root. Nowy test dowodzi tylko, że bajty `~/.lokay/health-lease` nie zmieniły się podczas jednego wywołania. Nie sprawdza, czy per-run lease został usunięty po teardown, czy nie powstały `cycle/`, logi, `mill.lock`, incydenty lub receipts. Lokalny dowód historycznego przecieku: obecny `~/.lokay/health-lease` zawiera `lock_path` wskazujący na `/private/.../pytest-.../test_preflight_test_config_kee0/runtime/state/mill.lock`. Traktuję go jako dowód, że testowy stan trafił do produkcyjnego HOME; nie przypisuję bez dodatkowego śladu konkretnego uruchomienia bieżącej wersji.

**Naruszona granica:** testy nie mogą czytać ani mutować aktywnego `~/.lokay`; fixture ma chronić całą granicę runtime, nie dwa wybrane call-site'y.

**Konsekwencja:** testy zależą od stanu działającego młyna, mogą maskować occupancy, zostawiać stale artifacts lub wpływać na produkcyjny status.

**Najmniejsza poprawka:** session-level test sandbox dla `HOME` oraz wszystkich jawnych runtime env (`LOKAY_LOG_DIR`, config/state/worktrees), z opt-in markerem dla testów naprawdę badających login HOME. Po każdym teście sprawdzić brak zapisu poza sandboxem. Zastąpić wybiórcze monkeypatche API repozytorium receiptów wstrzykiwanym runtime rootem.

### P6 — LOW — daemon shell łamie własny kontrakt „always uv”

**Pliki/linie:** `scripts/lokay-mill-daemon.sh:38,111,137`; kontrakt `docs/UNIX.md:14` oraz `AGENTS.md:59`.

**Dowód:** trzy produkcyjne fragmenty caretakingu uruchamiają bare `python3`, mimo twardej reguły użycia `uv run` dla product CLI.

**Naruszona granica:** jedno kontrolowane środowisko uruchomieniowe produktu.

**Konsekwencja:** launchd może znaleźć inny interpreter lub nie znaleźć go wcale; lock probe, receipt albo termination logic zachowają się inaczej niż zweryfikowane środowisko projektu.

**Najmniejsza poprawka:** przenieść te trzy małe operacje do atomów `src/lokay/proc/` i uruchamiać przez istniejące `uv run` entrypoints; nie dodawać logiki do composera.

## Hipotezy / luki dowodowe

### H1 — detached `issue_to_pr` nie ma testu pełnego kontraktu capability po revoke daemona

**Pliki/linie:** `src/lokay/proc/issue_delivery_launch.py:38-55,121-130,173-207`; `src/lokay/preflight.py:263-307,407-410,1207-1225`; `tests/test_issue_to_pr_activation.py:10-66`.

Launcher kopiuje cały env i przekazuje lease/path detached childowi. Po zniknięciu lock-ownera child może przepisać rekord tym samym tokenem, a `health_lease_status` uznaje owner-is-self za wystarczające (`preflight.py:407-410`). To wygląda na intencjonalny kontrakt przeżycia detached work, ale istniejące testy sprawdzają tylko pipe activation, nie sekwencję: lock held → spawn → publish → revoke/release lock → child mutation. Bez testu procesowego nie ma dowodu, że fail-close i przeżycie nie ścigają się przy ceiling.

**Ryzyko:** sporadyczne zatrzymanie legalnego detached work albo zbyt szerokie przedłużenie capability.

**Najmniejszy test:** prawdziwy subprocess w sandbox HOME/state, krótki atom mutujący po zwolnieniu parent locka, kontrolowane revoke i asercje: tylko właściwy launch/token działa, drugi child jest odrzucony, brak artefaktów po końcu.

### H2 — pełne kopiowanie env do detached workera może przenosić testowe/operatorowe flagi

**Pliki/linie:** `src/lokay/proc/issue_delivery_launch.py:39-55,122-129`; przykład semantycznej flagi testowej `src/lokay/preflight.py:658-659` (`PYTEST_CURRENT_TEST`).

Nie potwierdzono produkcyjnego incydentu. Jednak allow-all `os.environ.copy()` oznacza, że detached worker dziedziczy także flagi niesłużące capability. Minimalnie warto jawnie sklasyfikować env: obowiązkowe runtime/capability przekazać, test-only usunąć. Nie należy usuwać `LOKAY_HEALTH_LEASE*`, `LOKAY_DISABLE_HEALTH_LEASE_ISSUE`, `LOKAY_PROCESS_HEAD`, PATH/HOME i konfiguracji bez osobnego testu kontraktu.

## Ocena niezacommitowanej naprawy

**Co jest poprawne:**

- `src/lokay/preflight.py:1171-1177` wiąże domyślną unikalną ścieżkę lease ze skonfigurowanym state dir. To naprawia konkretny test→host write dla `run_preflight(..., issue_lease=True)`.
- Test `tests/test_preflight.py:932-947` wykrywa regresję zapisu do legacy `~/.lokay/health-lease` w tym jednym scenariuszu.
- Status bez odziedziczonego tokena może teraz zobaczyć per-run lease, co odpowiada potrzebie obserwacyjnej.

**Co blokuje uznanie naprawy za bezpieczną:** P1 (status mutuje lock), P4 (fałszywe `lease_ok`), P3 (brak GC), P5 (test zbyt wąski). `uv.lock` aktualizuje Fala `0.7.26 → 0.7.28`, ale diff nie dokumentuje, jaka granica wymaga tej zmiany; nie stwierdzono z samego lockfile błędu runtime.

## Weryfikacja

Uruchomiono z sandboxowym `HOME`:

```text
uv run pytest -q tests/test_status.py \
  tests/test_preflight.py::test_preflight_test_config_keeps_health_lease_out_of_host_home \
  tests/test_preflight_daemon.py::test_busy_lock_skips_daemon
12 passed in 0.79s
```

Zielone testy nie wykrywają P1-P5, ponieważ przygotowują istniejący lock, używają domyślnego state dir albo nie asertywują pełnego drzewa skutków ubocznych.

## Priorytet minimalnych działań

1. Naprawić P1 przed mergem niezacommitowanej zmiany.
2. Ujednolicić lock i receipt shell/daemon (P2).
3. Dodać bezpieczny GC/cleanup lease i test ceiling (P3).
4. Rozdzielić `run_lock_active` od dowiedzionego `lease_ok` oraz współdzielić walidator (P4).
5. Wprowadzić globalny runtime sandbox suite i test prawdziwego detached lifecycle (P5/H1).

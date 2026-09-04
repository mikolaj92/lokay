# Audyt grafu i granic flow Fala

Data: 2026-08-22  
Tryb: tylko odczyt kodu; jedynym zapisanym artefaktem jest ten raport.

## Zakres i stan drzewa

Przeczytano `AGENTS.md`, `README.md`, `docs/PROCESS.md`, `docs/GRAPH.md`, `docs/UNIX.md`, `docs/AUTONOMY.md`, `docs/NO_STUBS.md`, cały authored manifest `fala/lokay.fala-package.toml`, jego kopię w `src/lokay/data`, powiązane entrypointy, atomy i testy kontraktowe.

Working tree w chwili audytu miał niezacommitowane zmiany:

- `src/lokay/preflight.py`
- `src/lokay/proc/read_status_lease.py`
- `tests/test_preflight.py`
- `tests/test_status.py`
- `uv.lock`

Zmiany dotyczą lease/status i nie zmieniają grafu, conduction ani badanych flow. Zostały uwzględnione w odczycie.

## Potwierdzone problemy

### 1. HIGH — działy issue i executor ukrywają sterującą pętlę dzieci Fala w Pythonie

**Pliki/linie**

- `src/lokay/proc/run_issue_sieve_rows.py:34-57`
- `src/lokay/proc/run_executor_rows.py:30-56`
- węzły, które chowają te pętle: `fala/lokay.fala-package.toml:6661-6679` oraz `fala/lokay.fala-package.toml:6744-6762`
- deklarowany kontrakt: `README.md:10`, `docs/GRAPH.md:77-79`, `docs/PROCESS.md:8-16`, `AGENTS.md:26-34`

**Dowód**

Oba atomy wykonują `while True`, wielokrotnie wywołują `run_path(...)` dla `issue_sieve_row` albo `executor_row`, następnie w Pythonie wywołują `classify(...)`, liczą wykorzystany budżet, wybierają `continue`/terminal i aktualizują `last`. W parent Fala cały ten stan jest jednym efektorem `run_issue_sieve_rows` lub `run_executor_rows`. Powrót „czy jest następny wiersz?” nie jest więc widoczną krawędzią authored graph.

**Naruszona granica/kontrakt**

Kolejność, retry/powrót i wybór następnego kroku mają należeć do Fala. README dodatkowo obiecuje widoczny powrót do „is there a row?” i że parent nie unrolluje dzieci.

**Konsekwencja**

Dziennik parent Fala nie pokazuje poszczególnych przejść ani punktu decyzji o następnym ticketcie. Semantyka budżetu i terminala może zmienić się w Pythonie bez zmiany Mermaid/manifestu. Resume/retry obejmuje gruby atom zamiast konkretnego wiersza.

**Najmniejsza poprawka**

Przenieść bounded iterację i klasyfikację następnego wiersza do osobnych węzłów/path Fala. Pythonowy atom powinien uruchomić najwyżej jedno dziecko i zwrócić zamknięty wynik. Nie trzeba unrollować parent `factory_pass`; można dodać małą authored pod-Falę działu z jawną krawędzią powrotu i limitem.

---

### 2. MEDIUM — trzy nagłówki diagramów podają nieistniejące identyfikatory ścieżek

**Pliki/linie**

- `README.md:167`: `dispatch_triage`; authored ID to `triage_dispatch` (`README.md:1380`, `fala/lokay.fala-package.toml:1784-1788`)
- `README.md:188`: `dispatch_implement`; authored ID to `implementation_dispatch` (`README.md:1381`, `fala/lokay.fala-package.toml:1635-1639`)
- `README.md:980`: `reap_stale_worktrees`; authored ID to `stale_worktree_reap` (`README.md:1411`, `fala/lokay.fala-package.toml:1609-1613`)
- kontrakt: `README.md:74-77`, `AGENTS.md:14-16`

**Dowód**

Tabela ścieżek i manifest są zgodne, lecz nazwy w nagłówkach odpowiadają nazwom komend/efektorów, nie istniejącym `correlation_paths.id`. `lokay path --path <nazwa-z-nagłówka>` nie znajdzie tych ścieżek.

**Naruszona granica/kontrakt**

Mermaid jest zadeklarowanym kontraktem projektowym, a README, tabela i authored paths mają pozostać zsynchronizowane.

**Konsekwencja**

Czytelnik wdrażający lub diagnozujący flow dostaje dwie różne nazwy tego samego procesu i może wywołać nieistniejący path.

**Najmniejsza poprawka**

Zmienić tylko trzy nagłówki na `triage_dispatch`, `implementation_dispatch` i `stale_worktree_reap`. Nazwy węzłów wewnątrz Mermaid mogą pozostać domenowe.

---

### 3. MEDIUM — test deklarowanej zgodności Mermaid nie czyta diagramów

**Pliki/linie**

- deklaracja: `README.md:74-77`
- implementacja testu: `tests/test_readme_state_machine.py:21-28`

**Dowód**

Test regexem `| ... | path |` zbiera wyłącznie drugą kolumnę tabeli README i porównuje ją z `correlation_paths`. Nie parsuje nagłówków sekcji ani bloków Mermaid. Dlatego trzy rozjazdy z punktu 2 przechodzą przy zielonym teście.

**Naruszona granica/kontrakt**

README mówi wprost, że test sprawdza diagram oraz manifest. Obecny test sprawdza jedynie tabelę oraz manifest.

**Konsekwencja**

Zielony test daje fałszywą gwarancję. Drift diagramu może wejść bez sygnału.

**Najmniejsza poprawka**

Zachować obecny test kompletności tabeli i dodać osobny test mapujący nagłówki diagramów na authored path IDs, z jawną allowlistą dla diagramów przekrojowych, które opisują więcej niż jedną ścieżkę.

## Hipotezy / ryzyka wymagające decyzji projektowej

### H1. Pythonowy `closeout_catalog` unrolluje do 30 pod-Fal

- `src/lokay/proc/closeout_catalog.py:5,20-39` wybiera kolejno sloty, uruchamia `closeout_pr_subflow`, short-circuituje błąd i redukuje stan w Pythonie.
- `fala/lokay.fala-package.toml:3549-3567` widzi to jako jeden `closeout_catalog` atom.

To przypomina ten sam ukryty workflow co punkt 1. Nie kwalifikuję tego jako potwierdzone naruszenie, bo aktualny binding opisuje dokładnie ten wyjątek: `README.md:738-742` świadomie wymaga jednego atomu katalogu bez 30-slotowego unrollu Fala. Potrzebna jest decyzja: czy „atom katalogu” może sterować wieloma pod-Falami, czy może tylko przetwarzać dane/efekty jednego katalogu. Jeśli obowiązuje ścisłe „jeden proces = jeden job”, najmniejszą poprawką jest mała pod-Fala katalogowa z jawnym select/run/record/reduce.

### H2. Publiczny legacy `lokay-dispatch-closeout` zachowuje alternatywną kolejność

- `pyproject.toml:92`
- `src/lokay/proc/dispatch_closeout.py:18-36`

CLI ręcznie wykonuje `resolve_conflicts`, potem `closeout_prs`, z Pythonowym short-circuit. Jest jawnie opisany jako legacy CLI/test bridge. Nie ma dowodu, że produkcyjny `factory_pass` go używa. Ryzyko polega na utrzymywaniu drugiego publicznego flow, które może zdryfować od parent Fala. Najmniejsza redukcja ryzyka: usunąć publiczny script, jeśli brak konsumentów, albo zastąpić go jednym authored path i `run_path`.

### H3. `recovery_factory` opakowuje wiele passów w jeden atom

- `src/lokay/proc/recovery_factory.py:17-24`

Atom uruchamia `compose_run(max_passes=...)` i celowo podnosi domenowy błąd jako dane przy `ok=True`. Sam lokay przechodzi przez authored `product_entry`, więc nie omija Fala, ale parent recovery widzi wielopassowy produkt jako jeden atom. Należy potwierdzić, czy to zamierzona granica procesu nadrzędnego, czy historyczny bridge.

## Kontrole pozytywne

- `fala/lokay.fala-package.toml` i `src/lokay/data/lokay.fala-package.toml` są identyczne (6859 linii; identyczna treść). Brak driftu generated package.
- Tabela README zawiera dokładnie 52 unikalne ścieżki i manifest zawiera dokładnie te same 52 ID.
- Główny `factory_pass` ma poprawnie wydzielone pięć par select/run: `fala/lokay.fala-package.toml:111-193`.
- `reap_stale_worktrees` jest siblingiem od `factory_begin` (`:103-108`) i nie przewodzi działów ani `record_pass`.
- `record_pass` nie zależy od cleanup (`:196-208`).
- `compose/factory.py:25-63` jest cienkim bridge i zawsze prowadzi przez `run_path(path_id="factory_pass")`, poza jawnym offline dry-run.
- `compose/run.py:80-96` nie ma Pythonowej pętli passów; deleguje do authored `product_entry`. Sloty budżetu są jawne w `product_pass_budget` od `fala/lokay.fala-package.toml:4637`.
- Przejście repair → ponowna review w następnym passie jest jawnie udokumentowane (`README.md:1355-1356`, `docs/PROCESS.md:25-39`).
- Nie znaleziono parentowego unrollu 1..8 w Pythonie.

## Weryfikacja

Uruchomiono:

```text
uv run pytest -q tests/test_graph.py tests/test_readme_state_machine.py \
  tests/test_departments_fala.py tests/test_factory_begin_fala.py \
  tests/test_fala_package_lock.py
```

Wynik: **60 passed**. Wynik potwierdza obecne kontrakty testowe, ale nie obala punktów 1-3; luka testowa jest opisana w punkcie 3.

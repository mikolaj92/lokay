# Lokay — synteza audytu i plan porządkowania

Data: 2026-08-31. Źródła: cztery niezależne raporty `01`–`04`, inspekcja produkcyjnego runtime oraz walidacja zmian.

## Stan po natychmiastowym sprzątaniu

- Testy preflight używają sandboxowego `HOME`; nie zapisują hostowego `~/.lokay/health-lease`.
- Status nie tworzy `mill.lock`, toleruje dangling/race, odrzuca symlink, obcy UID i mode inne niż `0600`.
- Status rozdziela zweryfikowaną capability (`lease_ok`) od obserwacji runu (`run_active`).
- Daemon usuwa bezpiecznie per-run lease wygasłe lub należące do martwego PID.
- Stare per-run lease zostały zredukowane z około 969 do aktywnego rekordu; obcy `health-lease.token` pozostawiono nietknięty.
- Caretaker nie utrzymuje drugiej, niezależnej polityki locka; overlap należy do config-aware `lokay-daemon`.
- Caretaker nie używa bare `python3`.
- Trzy błędne nagłówki path w README poprawiono i objęto testem.
- Daemon nie wchodzi już do grafu produktu po nieudanym preflight; zwraca zamknięty wynik bramki zamiast wtórnego, mylącego błędu brakującego lease.
- GC lease nie usuwa rekordu, gdy jego dokładny config-aware lock jest nadal zajęty, nawet jeśli zapisany PID umarł albo rekord przekroczył TTL.
- Bezpośredni `lokay status` zawsze dostarcza `LOKAY_ROOT` wymagany przez whitelistę `inherit_env` Fala.
- Produkcyjny preflight ujawnił niezależny blocker `disk_headroom` (1,9 GiB < 2 GiB). `uv cache prune --force` usunął 5,3 GiB bez kasowania danych produktu; po odzyskaniu 6,9 GiB runtime wystawił aktywny per-run lease i wszedł do grafu.

## Potwierdzone problemy — priorytet

### P0: granice wykonania

1. `repo_mutex` nie jest mutexem: heurystyczny `ps` ma TOCTOU. Zastąpić repo-scoped `flock` utrzymywanym przez cały slot kodera.
2. `issue_delivery_launch` potrafi mintować capability poza właścicielem daemon locka. Najpierw opisać i przetestować pełny detached lifecycle; potem fail-closed bez delegowanego tokena.
3. Shell ceiling receipt nadal domyślnie używa `~/.lokay/last-pass.json`; dla custom `state.path` potrzebuje jednego config-aware atomu/path resolvera.

### P1: ordering musi wrócić do Fala

4. `run_issue_sieve_rows.py` oraz `run_executor_rows.py` chowają Pythonowe `while`, budżet i wybór następnego child path. Przed implementacją zaktualizować Mermaid, potem zrobić authored pod-Fale z jedną iteracją na atom i jawną krawędzią powrotu.
5. Do decyzji: podobny ukryty unroll w `closeout_catalog`; legacy `lokay-dispatch-closeout`; wielopassowy `recovery_mill` jako jeden atom.

### P1: usunąć duplikację Fala

6. `graph_run.py` powinien przekazywać `inputs=base_input`, nie rozwijać inputs na każdy effector.
7. Tekstowy slicer TOML powiela wybór `path_id`; usunąć po benchmarku albo przenieść oficjalne selective materialization/cache do Fala.
8. Czytać gwarantowane `effector_results` Fala 0.7.28; usunąć historyczne `output_json`/`processes` fallbacki, chyba że adapter zostanie jawnie wersjonowany.
9. `fala_journal.py` powinien używać `fala.maintain_journal`. Jeśli konieczny jest byte-budget, dodać go w Fala, nie manipulować SQLite sidecarami w Lokayu.

### P2: moduły i dokumentacja

10. Usunąć cykl `fala_organ ↔ organ.*` przez neutralny runtime port dla `_run_atom_main`/hooków.
11. Przenieść `SLOT_COUNT` z `organ` do neutralnego kontraktu albo jawnego argumentu atomu.
12. Rozszerzyć test README z trzech naprawionych headingów na pełny jawny mapping Mermaid/path, z allowlistą diagramów przekrojowych.

## Pozytywne ustalenia

- Authored i packaged Fala są identyczne; tabela README ma dokładnie te same 52 paths.
- `factory_pass` zachowuje pięć działów, cleanup jako sibling i receipt niezależny od cleanup.
- `compose/*` nie zawiera bezpośredniej logiki GitHub/git/agent/fleet.
- Wszystkie 108 `project.scripts` wskazują na istniejące moduły/main.
- app-factory platform i Kofte są używane zamiast lokalnych kopii; brak potwierdzonej duplikacji UI/style engine.

## Kolejność dalszych zmian

Każdy punkt jako osobna mała zmiana. Dla zmian routingu obowiązuje: README Mermaid → authored Fala → atomy → testy → pełna walidacja. Nie łączyć przebudowy grafu z lease/runtime ani z adapterem Fala.

## Walidacja końcowa

- Pełny suite przechodzi hermetycznie: `1814 passed`.
- `uv run lokay validate --config config.yaml`, `uv run lokay-repos --config config.yaml` oraz read-only `uv run lokay status --config config.yaml --local` przechodzą.
- Naprawiono źródło masowych, kolejnościowych failure’ów: natywne ładowanie Fala zmieniało `DYLD_LIBRARY_PATH` procesu pytest, przez co późniejsze child Python nie mogły importować wbudowanych rozszerzeń `math`/`fcntl`. Adapter `graph_run` i autouse fixture przywracają środowisko.
- Zaktualizowano rzeczywiście stare kontrakty testowe: katalog 30→31 bez sztywnej liczby, mały receipt `factory_begin`, ghost receipts bez worktree, klasyfikowany `worktree_add` (`ok=true`, `route=missing`), nowe wymagane `localize.route=ready`, oraz brak założenia o kolejności kluczy mapy `effector_results`.
- `organ/common.py` ma ponownie mniej niż 400 linii bez zmiany logiki.
- Usunięto osierocony ręczny wrapper młyna i jego rekurencyjne dzieci Fala. Produkcja działa teraz jako pojedynczy LaunchAgent `user/501/ai.mikolaj.lokay-mill` i raportuje aktywny config-aware lease.
- `git diff --check` przechodzi.

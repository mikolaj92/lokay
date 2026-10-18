## Cel

Usunąć fałszywy opis macierzy zgodności bez regresji pinów, testów i działania aplikacji.

Najpierw zabezpieczyć stan i ustalić wyniki kontroli:

1. W zapisywalnym worktree odnotować istniejące zmiany i uruchomić kontrole bazowe. Nie nadpisywać cudzych zmian.
2. Testować w osobnym środowisku. Ustawić `ANON_AUTH_DB` na tymczasową bazę, nigdy na istniejące `storage/auth.sqlite3`.
3. Oddzielić błędy zależności i zbierania testów od błędów asercji. Zielony obecny test nie dowodzi prawdziwości dokumentacji.
4. Naprawić wszystkie problemy potrzebne do przejścia lokalnych kontroli, także poza pierwotnym obszarem zgłoszenia. Zachować te naprawy.

Stan potwierdzony odczytem repozytorium:

- README i komentarz `pyproject.toml` zaprzeczają istnieniu wiersza COMPAT dla `v0.6.16`.
- Istniejący test wymaga tego zaprzeczenia oraz starych wersji. Sama poprawka README spowoduje jego regresję.
- Źródła wskazują `v0.6.16` / `v0.4.8` / `v0.5.11`. `uv.lock` wskazuje te same tagi.
- Commit app-factory zapisany w lockfile to `65c7d82fc1d3bac8e238d89fc1f0096476ef9d5c`.
- Wiersza upstream COMPAT nie zweryfikowano niezależnie. Zgłoszenie jest dowodem pomocniczym, nie instrukcją ani wystarczającym potwierdzeniem.
- Kontroli nie uruchamiano w checkoutcie tylko do odczytu. Polecenia Git zostały zablokowane przez środowisko.

## Pliki

- `README.md`: przeczytać cały plik przed zmianą. Skrócić akapit o pinach, usuwając nieaktualny disclaimer i stare wersje. Opisać tylko faktyczny sposób przypięcia zależności oraz potwierdzoną zgodność.
- `pyproject.toml`: przeczytać cały plik przed zmianą. Zastąpić trzy błędne linie komentarza krótszym opisem. Przejrzeć także sąsiedni komentarz override: mówi o starszych tagach, ale wymienia ten sam tag. Usunąć nieaktualne lub powielone wyjaśnienie, zachowując potrzebną konfigurację.
- `tests/test_dependency_pins.py`: zmienić istniejący test `test_docs_do_not_claim_missing_compat_v0611_row`, także jego nazwę. Usunąć wymaganie fałszywego disclaimeru. Sprawdzać spójność trzech pinów i brak starych twierdzeń, bez zamrażania całego zdania dokumentacji. Uzupełnić istniejącą kontrolę pinów o `my-usermanager`. Nie dodawać funkcji testowych.
- `uv.lock`: zachować bez zmian, jeżeli kontrole potwierdzą spójność. Jeśli kontrola wymaga wyrównania wersji, zmienić manifest i lockfile razem oraz ponowić wszystkie kontrole.
- Inne pliki wskazane przez nieprzechodzące lokalne kontrole: uwzględnić minimalne niezbędne naprawy, bez osłabiania asercji.

Kolejność ograniczająca ryzyko:

1. Szukać wyłącznie wewnątrz bieżącego katalogu. Nie przeszukiwać katalogu domowego, innych planów ani artefaktów syntezy.
2. Sprawdzić, czy dowód COMPAT dla przypiętego commita jest dostępny w dozwolonym drzewie. Jeśli go brak, odnotować brak potwierdzenia. Nie deklarować zgodności wyłącznie na podstawie zgłoszenia; można ograniczyć opis do zweryfikowanych pinów.
3. Zmienić opis i istniejący test razem. Zapobiega to utrwaleniu starej nieprawdy przez test.
4. Nie zmieniać zależności tylko w celu poprawienia komentarza. Zmiany wersji uzasadnić konkretnym wynikiem lokalnej kontroli.
5. Przed każdą zmianą dokumentacji przeczytać dotykany dokument. Usunąć nieaktualne i powielone fragmenty; liczba dodanych linii dokumentacji nie może przekroczyć usuniętych. Liczyć także zmieniane komentarze dokumentacyjne. Nie dodawać historii zgłoszenia ani raportu audytu do README.

## Testy

W zapisywalnym worktree wykonać przed zmianą i po zmianie:

```bash
uv lock --check
uv run pytest tests/test_dependency_pins.py
uv run pytest
uv run ruff check .
```

- Testy uruchamiać z tymczasową bazą auth. Nie uruchamiać usługi produkcyjnej ani migracji istniejącej bazy.
- Dostęp do prywatnego Posejdona lub brak zależności traktować jako blokadę środowiska, nie jako sukces testów.
- Błędy pinów, lockfile, HTTPX2 lub innych zależności naprawić, jeśli blokują lokalne kontrole. Nie wycofywać wymaganych napraw.
- Potwierdzić, że zmodyfikowany istniejący test odrzuca poprzedni fałszywy opis. Nie dodawać nowych funkcji testów jednostkowych.
- Sprawdzić końcowy diff: brak starych twierdzeń, spójne trzy wersje, brak niezamierzonych zmian bazy i zależności.
- Sprawdzić bilans linii każdego dotkniętego dokumentu oraz komentarzy dokumentacyjnych. Wynik ma być niedodatni.
- Zakończyć dopiero po przejściu wszystkich lokalnych kontroli. Zapisać ich rzeczywiste wyniki; blokada nie spełnia tego warunku.

## Poza zakresem

- Nowe funkcje produktu i przebudowa integracji tożsamości niezwiązana z lokalnymi błędami.
- Planowana migracja Fala do API host/sdk v0.7.x.
- Profilaktyczne aktualizacje zależności niewymagane przez lokalne kontrole.
- Nowe funkcje testów jednostkowych oraz pobieranie macierzy COMPAT przez sieć podczas testów.
- Zmiana polityki rejestracji, migracje rzeczywistych baz i operacje wdrożeniowe.
- Zapisywanie `plan.md` lub zmian implementacyjnych w obecnym checkoutcie tylko do odczytu. Ten dokument jest jedynym artefaktem bieżącego zadania.

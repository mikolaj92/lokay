# Incydenty przywołane w #1816

Analizowany kod lokay: **`594334bd391da5958153d864b972a869cdecf565`**.
Historyczny kod lokay: **`f343c0845efe7bdc2a34a0b3df6ab0fe8cc93b33`**.
To nie są SHA Temidy ani SHA kandydatów PR.

## Relacja a dowód

Przekazana treść [lokay #1816](https://github.com/mikolaj92/lokay/issues/1816) twierdzi:

1. PR Temida #7347 przeszedł 22 rundy Fix i merge bez wdrożenia celu issue #6961.
2. Siedem kategorii wskazywało ten sam plik.
3. PR Temida #7343–#7348 scalono bez testów zmienionego kodu.

Są to **niepotwierdzone relacje**. Sam kod lokay może wyjaśnić możliwy mechanizm,
ale nie dowodzi liczby rund, zawartości diffu, wykonania testów ani wdrożenia Temidy.
Przejścia: [STATE_MACHINE.md](STATE_MACHINE.md). Powiązane możliwości: [RISKS.md](RISKS.md),
zwłaszcza R2–R9, R12, R17–R18 i R25. To nie jest przypisanie potwierdzonej przyczyny.

## Dostępne materiały

- Odczytano kod lokay i porównano lokalne rewizje przez `git diff f343c08 HEAD`.
  Historia lokay zawiera poprawki mechanizmów wymienionych w rejestrze ryzyk.
- W tym checkoutcie nie znaleziono plików o nazwach zawierających `734*` ani `6961` do głębokości trzech katalogów.
  Nie jest to dowód braku materiałów na hostach lub w innych repozytoriach.
- Publiczne, nieuwierzytelnione GET do `https://api.github.com/repos/mikolaj92/Temida/pulls/<numer>`
  dla każdego z #7343–#7348 zwróciło **HTTP 404**.
- GET do `https://api.github.com/repos/mikolaj92/Temida/issues/6961` także zwróciło **HTTP 404**.
  HTTP 404 nie dowodzi nieistnienia prywatnego lub niedostępnego zasobu.
- Nie odczytano credentiali, tokenów, produkcyjnych logów ani innych checkoutów.
  Nie wykonano merge, wdrożenia, restartu ani realnego canary.

## Rejestr weryfikacji

| Obiekt | Relacja z issue | Potwierdzone w tej analizie | Status | Brakujące dowody |
| --- | --- | --- | --- | --- |
| [Temida PR #7343](https://github.com/mikolaj92/Temida/pull/7343) | merge bez testów zmienionego kodu | tylko próba publicznego GET: 404 | niepotwierdzony | diff i head SHA, mergedAt/merge SHA, Check logs i argv, wymagane checks dla SHA |
| [Temida PR #7344](https://github.com/mikolaj92/Temida/pull/7344) | jak wyżej | GET: 404 | niepotwierdzony | ten sam komplet dowodów osobno dla tego PR |
| [Temida PR #7345](https://github.com/mikolaj92/Temida/pull/7345) | jak wyżej | GET: 404 | niepotwierdzony | ten sam komplet dowodów osobno dla tego PR |
| [Temida PR #7346](https://github.com/mikolaj92/Temida/pull/7346) | jak wyżej | GET: 404 | niepotwierdzony | ten sam komplet dowodów osobno dla tego PR |
| [Temida PR #7347](https://github.com/mikolaj92/Temida/pull/7347) | 22 rundy Fix, merge bez realizacji/wdrożenia; brak testów kodu | GET: 404 | niepotwierdzony | rounds z SHA każdej rundy, diff celu, końcowe kontrole, dowód wdrożenia i zachowania funkcji |
| [Temida PR #7348](https://github.com/mikolaj92/Temida/pull/7348) | merge bez testów zmienionego kodu | GET: 404 | niepotwierdzony | ten sam komplet dowodów osobno dla tego PR |
| [Temida issue #6961](https://github.com/mikolaj92/Temida/issues/6961) | cel rzekomo nie został wdrożony przez #7347 | GET: 404 | niepotwierdzony | treść i kryterium celu, powiązanie PR, dowód zachowania na wdrożonym SHA |
| siedem kategorii / ten sam plik | wspólna odpowiedź review | brak oryginalnych odpowiedzi Decision | niepotwierdzony | pytania, wire odpowiedzi i probabilities, hunki, SHA oraz przypisanie do rundy i PR |

Nie znamy indywidualnych zmian #7343–#7348. Nie przypisujemy im wymyślonych plików ani wyników.
„Bez testów zmienionego kodu” nie jest równoważne „zero testów w ogóle”.
Rozstrzygnięcie wymaga logów, zakresu komend i mapowania zmienionych pakietów.
„Merge” nie jest równoważne „wdrożenie”. Wymaga osobnego dowodu uruchomionego SHA.

## Jak uzupełnić dowód bez zmiany produkcyjnego stanu

Dla każdego PR zachować tożsamość `(repo, PR, head SHA)`.
Zebrać diff, historię Fix, konfigurację runnera i pełny wynik kontroli z tego SHA.
Oddzielić historyczny wynik od powtórki wykonanej na nowym kodzie.
Dla #6961 porównać wymagane zachowanie z kodem oraz dowodem wdrożenia.
Do czasu otrzymania materiałów wynik rejestru pozostaje:
**PR potwierdzone=0/6; issue potwierdzone=0/1; relacja review potwierdzona=0/1**.

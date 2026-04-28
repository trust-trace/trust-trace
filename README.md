# trust-trace

Trust Trace to repozytorium z pipeline'em do zbierania artykulow, ekstrakcji encji, liczenia scoringu AML i prezentacji wynikow w interfejsie webowym.

## Moduly

- `frontend/` - aplikacja Next.js. Wyswietla liste firm, artykuly, graf powiazan i status uruchomionego pipeline'u.
- `backend/tarkov/` - glowny backend Stage 2. Przyjmuje artykuly ze `scuttle_crab`, wyciaga firmy, zdarzenia, osoby i zapisuje dane do bazy.
- `backend/pipeline/` - orkiestrator calego flow end-to-end. Spina scraping, ingest do Tarkova, zbieranie danych i laczenie wynikow scoringu.
- `backend/eem/` - Event Enrichment Module. Wzbogaca zdarzenia i wylicza trust score firmy.
- `backend/nsa/` - News Sentiment Analysis. Ocenia sentyment artykulow, wiarygodnosc zrodel i potencjalny impact.
- `backend/rkr/` - modul klasyfikacji i filtrowania ryzyka na podstawie slow kluczowych oraz tresci artykulow.
- `backend/trust_web/` - logika grafowa i scoring powiazan miedzy podmiotami.
- `backend/reasoning/` - zapis i formatowanie reasoning traces do audytu i wyjasnien decyzji modelu.
- `backend/timeline/` - logika bucketowania czasu do scoringu i wizualizacji historii.
- `rust/scuttle_crab/` - crawler w Rust. Zbiera artykuly, deduplikuje URL-e, buduje payload i wysyla dane do Tarkova.
- `db/` - konfiguracja warstwy bazodanowej, w tym Neo4j oraz obrazy pomocnicze do lokalnego srodowiska.
- `test_crawler/` - dane i materialy pomocnicze do testowania crawlera.

## Jak to sie laczy

1. `rust/scuttle_crab` zbiera i normalizuje artykuly.
2. `backend/tarkov` przetwarza artykuly i zapisuje encje oraz zdarzenia.
3. `backend/pipeline` uruchamia kolejne etapy scoringu.
4. Moduly `eem`, `nsa`, `rkr` i `trust_web` dostarczaja sygnaly ryzyka.
5. `frontend` pokazuje wynik koncowy, artykuly i graf relacji.

## Najwazniejsze katalogi pomocnicze

- `AML_SCORING_PIPELINE.md` - opis pipeline'u AML.
- `HANDOFF.md` - notatki projektowe i przekazanie kontekstu.

# MOST IMPORTANT DO NOT DELETE BISMILLAH
- Jakub Mazurek
- Wiktor Sekreta
- Szymon Sidor
- Tymoteusz Mosiołek
- Marcel Geba

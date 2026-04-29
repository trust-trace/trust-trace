# Jak uruchomic Trust Trace

Instrukcja krok po kroku -- od klonowania repo do dzialajacego systemu.

---

## Spis tresci

- [Wymagania](#wymagania)
- [Szybki start (Docker)](#szybki-start-docker)
- [Uruchamianie bez Dockera (dev mode)](#uruchamianie-bez-dockera-dev-mode)
  - [Bazy danych](#1-bazy-danych)
  - [Backend (Tarkov API)](#2-backend-tarkov-api)
  - [Crawler (Scuttle Crab)](#3-crawler-scuttle-crab)
  - [Frontend](#4-frontend)
- [Zmienne srodowiskowe](#zmienne-srodowiskowe)
- [Przydatne komendy](#przydatne-komendy)
- [Rozwiazywanie problemow](#rozwiazywanie-problemow)

---

## Wymagania

| Narzedzie | Wersja | Do czego |
|-----------|--------|----------|
| **Docker** + Docker Compose | 20+ / v2+ | Uruchomienie calego stacku jednym poleceniem |
| **Node.js** | 20+ | Frontend (tryb dev) |
| **Python** | 3.11+ | Backend (tryb dev) |
| **Rust** | 1.75+ | Crawler (tryb dev) |
| **PostgreSQL** | 15 | Baza danych strukturalnych |
| **Neo4j** | 5.x | Graf relacji |

> Docker Compose jest wystarczajacy do uruchomienia calego projektu. Node/Python/Rust sa potrzebne tylko jesli chcesz rozwijac poszczegolne moduly lokalnie.

---

## Szybki start (Docker)

Najprostsza metoda -- uruchamia wszystkie serwisy w kontenerach.

### 1. Sklonuj repozytorium

```bash
git clone https://github.com/your-org/trust-trace.git
cd trust-trace
```

### 2. Skonfiguruj zmienne srodowiskowe

```bash
cp backend/.env.example .env
```

Otworz plik `.env` i ustaw co najmniej:

```env
LLM_API_KEY=sk-...          # klucz API do OpenAI / OpenRouter
LLM_PROVIDER=openrouter     # lub "openai"
LLM_MODEL=gpt-4o-mini       # model do ekstrakcji
```

### 3. Uruchom Docker Compose

```bash
docker compose up --build
```

Pierwsze uruchomienie moze potrwac kilka minut (budowanie obrazow Rust i Python).

### 4. Sprawdz czy dziala

| Serwis | URL | Opis |
|--------|-----|------|
| Frontend | http://localhost:3000 | Dashboard webowy |
| Tarkov API | http://localhost:8081 | Backend REST API |
| Tarkov Health | http://localhost:8081/health | Healthcheck |
| Neo4j Browser | http://localhost:7474 | Interfejs grafowy Neo4j |
| Scuttle Crab | http://localhost:3000 | Crawler HTTP API |

### 5. Zatrzymanie

```bash
docker compose down          # zatrzymaj serwisy
docker compose down -v       # zatrzymaj + usun dane (volumes)
```

---

## Uruchamianie bez Dockera (dev mode)

Dla aktywnego developmentu, gdzie potrzebujesz hot-reload i szybkich iteracji.

### 1. Bazy danych

Najlatwiej uruchomic bazy przez Docker nawet w trybie dev:

```bash
# Samo Postgres + Neo4j
docker compose up postgres neo4j -d
```

Lub zainstaluj lokalnie:
- **PostgreSQL 15**: utwroz baze `trusttrace_db` z userem `trusttrace:trusttrace`
- **Neo4j**: uruchom z haslem `trusttrace`

### 2. Backend (Tarkov API)

```bash
cd backend

# Utwroz venv
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# Zainstaluj zaleznosci
pip install -r requirements.txt

# Skopiuj i dostosuj env
cp .env.example .env
# edytuj .env -- ustaw LLM_API_KEY, DATABASE_URL etc.

# Uruchom migracje
alembic upgrade head

# Uruchom serwer
python -m tarkov.main serve --host 0.0.0.0 --port 8081
```

Backend dostepny na: http://localhost:8081

### 3. Crawler (Scuttle Crab)

```bash
cd rust/scuttle_crab

# Skopiuj env
cp example.env .env
# edytuj .env -- ustaw TARKOV_BASE_URL=http://127.0.0.1:8081

# Zbuduj i uruchom
cargo build --release
cargo run -- serve
```

Crawler dostepny na: http://localhost:3000

**Przydatne komendy CLI:**

```bash
# Scrapuj konkretny URL
cargo run -- fetch-url "https://example.com/article"

# Szukaj artykulow o firmie
cargo run -- search-company "Company Name"

# Crawluj feedy RSS
cargo run -- crawl
```

### 4. Frontend

```bash
cd frontend

# Zainstaluj zaleznosci
npm install

# Ustaw backend URL (opcjonalnie -- domyslnie http://127.0.0.1:8081)
export TRUST_TRACE_BACKEND_URL=http://127.0.0.1:8081

# Uruchom dev server
npm run dev
```

Frontend dostepny na: http://localhost:3000

> **Uwaga:** Jesli Scuttle Crab tez dziala na porcie 3000, zmien port frontendu:
> ```bash
> npm run dev -- -p 3001
> ```

**Inne komendy:**

```bash
npm run build    # zbuduj wersje produkcyjna
npm run lint     # sprawdz lintera
npm run test     # uruchom testy (Vitest)
```

---

## Zmienne srodowiskowe

### Backend (`backend/.env`)

| Zmienna | Wymagana | Domyslna | Opis |
|---------|----------|----------|------|
| `DATABASE_URL` | tak | -- | URL do PostgreSQL |
| `LLM_API_KEY` | tak | -- | Klucz API do LLM (OpenAI/OpenRouter) |
| `LLM_PROVIDER` | nie | `openai` | Provider LLM: `openai`, `openrouter`, `anthropic` |
| `LLM_MODEL` | nie | `gpt-4o-mini` | Model do ekstrakcji encji |
| `LOG_LEVEL` | nie | `INFO` | Poziom logow |
| `NEO4J_URI` | nie | `bolt://localhost:7687` | URI do Neo4j |
| `NEO4J_USER` | nie | `neo4j` | User Neo4j |
| `NEO4J_PASSWORD` | nie | `trusttrace` | Haslo Neo4j |
| `SCUTTLE_CRAB_URL` | nie | `http://localhost:3000` | URL crawlera |
| `ENABLE_STAGE3_DISPATCH` | nie | `false` | Wlacz dispatch do modulow Stage 3 |
| `EEM_API_KEY` | nie | -- | Klucz API dla Event Enrichment Module |
| `TRUSTWEB_LLM_API_KEY` | nie | -- | Klucz API dla TrustWeb (scoring grafowy) |

### Crawler (`rust/scuttle_crab/.env`)

| Zmienna | Wymagana | Domyslna | Opis |
|---------|----------|----------|------|
| `TARKOV_BASE_URL` | tak | -- | URL backendu Tarkov |
| `SCUTTLE_BIND_ADDR` | nie | `127.0.0.1:3000` | Adres HTTP serwera crawlera |
| `TARKOV_INGEST_PATH` | nie | `/v1/articles` | Sciezka ingest w Tarkov API |
| `TARKOV_TIMEOUT_SECS` | nie | `15` | Timeout requestow do Tarkova |
| `SCUTTLE_COMPANY_ARTICLE_LIMIT` | nie | `10` | Max artykulow na firme |

### Frontend

| Zmienna | Wymagana | Domyslna | Opis |
|---------|----------|----------|------|
| `TRUST_TRACE_BACKEND_URL` | nie | `http://127.0.0.1:8081` | URL backendu |
| `NEXT_PUBLIC_ENABLE_MSW` | nie | -- | Wlacz mockowanie (dev) |

---

## Przydatne komendy

### Docker

```bash
# Uruchom calosc
docker compose up --build

# Uruchom w tle
docker compose up -d

# Logi konkretnego serwisu
docker compose logs -f tarkov-api
docker compose logs -f scuttle-crab

# Restart jednego serwisu
docker compose restart tarkov-api

# Wyczysc wszystko (dane + kontenery)
docker compose down -v
```

### Backend

```bash
# Uruchom testy
cd backend && pytest tarkov/tests -q

# Przetworzenie artykulow z pliku
python -m tarkov.main process-articles --input-source jsonl --input-path articles.jsonl

# Migracje bazy
alembic upgrade head       # zastosuj migracje
alembic downgrade -1       # cofnij ostatnia migracje
```

### Crawler

```bash
cd rust/scuttle_crab

cargo test                            # testy
cargo run -- serve                    # serwer HTTP
cargo run -- crawl                    # crawl RSS
cargo run -- fetch-url "URL"          # fetch konkretny URL
cargo run -- search-company "Firma"   # szukaj artykulow
```

### Frontend

```bash
cd frontend

npm run dev        # dev server z hot-reload
npm run build      # build produkcyjny
npm run test       # testy Vitest
npm run lint       # ESLint
```

---

## Rozwiazywanie problemow

### Docker Compose nie startuje

```bash
# Sprawdz logi
docker compose logs

# Sprawdz healthchecki
docker compose ps
```

Najczestsze przyczyny:
- **Brak `LLM_API_KEY`** w `.env` -- Docker Compose wymaga tej zmiennej
- **Port zajety** -- sprawdz czy porty 3000, 5432, 7474, 7687, 8081 sa wolne

### Backend nie laczy sie z baza

- Sprawdz czy PostgreSQL dziala: `docker compose ps postgres`
- Sprawdz `DATABASE_URL` w `.env`
- Uruchom migracje: `alembic upgrade head`

### Frontend nie laczy sie z backendem

- Sprawdz czy Tarkov API dziala: `curl http://localhost:8081/health`
- Sprawdz `TRUST_TRACE_BACKEND_URL`

### Crawler nie wysyla artykulow

- Sprawdz `TARKOV_BASE_URL` w `.env` crawlera
- Sprawdz czy Tarkov API jest dostepny z perspektywy crawlera

---

<p align="center">
  <a href="./README.md">Powrot do README</a>
</p>

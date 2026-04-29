<p align="center">
  <img src="docs/assets/logo-placeholder.png" alt="Trust Trace Logo" width="200"/>
</p>

<h1 align="center">Trust Trace</h1>

<p align="center">
  <strong>Inteligentny pipeline do analizy ryzyka AML oparty o artykuly prasowe, scoring i wizualizacje grafowe</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Next.js-16-black?logo=next.js" alt="Next.js"/>
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Rust-2024-orange?logo=rust" alt="Rust"/>
  <img src="https://img.shields.io/badge/Neo4j-Graph-008CC1?logo=neo4j" alt="Neo4j"/>
  <img src="https://img.shields.io/badge/PostgreSQL-15-336791?logo=postgresql" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker" alt="Docker"/>
</p>

---

## Spis tresci

- [O projekcie](#o-projekcie)
- [Demo](#demo)
- [Zrzuty ekranu](#zrzuty-ekranu)
- [Architektura](#architektura)
- [Moduly](#moduly)
- [Tech Stack](#tech-stack)
- [Szybki start](#szybki-start)
- [Zespol](#zespol)

---

## O projekcie

Trust Trace to kompleksowy system do automatycznej analizy ryzyka AML (Anti-Money Laundering) oparty na artykach prasowych. System:

1. **Zbiera artykuly** z roznych zrodel internetowych (RSS, scraping, wyszukiwanie)
2. **Ekstrahuje encje** -- firmy, osoby, zdarzenia -- z tresci artykulow za pomoca LLM
3. **Analizuje ryzyko** wieloma modulami: sentyment, klasyfikacja zdarzen, scoring grafowy
4. **Wizualizuje wyniki** w interaktywnym dashboardzie z grafem relacji, timeline i reasoning traces

Kazda decyzja systemu jest transparentna dzieki mechanizmowi **reasoning traces** -- pelny audit trail wyjasniajacy dlaczego dana firma otrzymala dany scoring.

---

## Demo

<p align="center">
  <em>Pipeline w akcji -- od scrapowania do wynikow</em>
</p>

<p align="center">
  <img src="docs/assets/demo-pipeline.gif" alt="Demo pipeline" width="800"/>
</p>

<p align="center">
  <em>Interaktywny graf relacji miedzy firmami</em>
</p>

<p align="center">
  <img src="docs/assets/demo-graph.gif" alt="Demo grafu" width="800"/>
</p>

---

## Zrzuty ekranu

<details>
<summary><strong>Dashboard -- lista firm z scoringiem</strong></summary>
<br/>
<p align="center">
  <img src="docs/assets/screenshot-dashboard.png" alt="Dashboard" width="800"/>
</p>
</details>

<details>
<summary><strong>Szczegoly firmy -- artykuly, zdarzenia, scoring</strong></summary>
<br/>
<p align="center">
  <img src="docs/assets/screenshot-company-detail.png" alt="Szczegoly firmy" width="800"/>
</p>
</details>

<details>
<summary><strong>Graf relacji (Graph View)</strong></summary>
<br/>
<p align="center">
  <img src="docs/assets/screenshot-graph.png" alt="Graf relacji" width="800"/>
</p>
</details>

<details>
<summary><strong>Reasoning Traces -- audit trail decyzji</strong></summary>
<br/>
<p align="center">
  <img src="docs/assets/screenshot-traces.png" alt="Reasoning traces" width="800"/>
</p>
</details>

<details>
<summary><strong>Panel uruchamiania pipeline</strong></summary>
<br/>
<p align="center">
  <img src="docs/assets/screenshot-pipeline.png" alt="Pipeline panel" width="800"/>
</p>
</details>

---

## Architektura

```
                         +-------------------+
                         |    Frontend        |
                         |    (Next.js)       |
                         |  localhost:3001    |
                         +---------+---------+
                                   |
                                   v
                         +---------+---------+
                         |   Tarkov API       |
                         |   (FastAPI)        |
                         |  localhost:8081    |
                         +-+-------+-------+-+
                           |       |       |
              +------------+   +---+---+   +------------+
              v                v       v                v
     +--------+------+   +----+--+ +--+----+   +-------+--------+
     | Scuttle Crab   |   | Neo4j | | Postgres|   | Scoring Modules |
     | (Rust Crawler) |   +-------+ +--------+   |  EEM / NSA /    |
     | localhost:3000 |                           |  RKR / TrustWeb |
     +----------------+                           +-----------------+
```

**Przeplyw danych:**

1. **Scuttle Crab** (Rust) -- crawluje artykuly z RSS, stron i wyszukiwarek
2. **Tarkov** (Python/FastAPI) -- przyjmuje artykuly, ekstrahuje encje (firmy, osoby, zdarzenia)
3. **Moduly scoringowe** -- wzbogacaja dane o sentyment, klasyfikacje ryzyka i scoring grafowy
4. **Neo4j + PostgreSQL** -- przechowuja graf relacji i dane strukturalne
5. **Frontend** (Next.js) -- wyswietla wyniki: dashboard, graf, traces

---

## Moduly

| Modul | Katalog | Opis |
|-------|---------|------|
| **Frontend** | `frontend/` | Aplikacja Next.js -- dashboard firm, graf relacji, reasoning traces, panel pipeline |
| **Tarkov** | `backend/tarkov/` | Glowny backend Stage 2 -- ingest artykulow, ekstrakcja encji, API |
| **Pipeline** | `backend/pipeline/` | Orkiestrator flow end-to-end -- spina scraping, ingest i scoring |
| **EEM** | `backend/eem/` | Event Enrichment Module -- wzbogaca zdarzenia, wylicza trust score |
| **NSA** | `backend/nsa/` | News Sentiment Analysis -- sentyment artykulow, wiarygodnosc zrodel |
| **RKR** | `backend/rkr/` | Risk Keyword Recognition -- klasyfikacja ryzyka na podstawie slow kluczowych |
| **TrustWeb** | `backend/trust_web/` | Scoring grafowy powiazan miedzy podmiotami (Neo4j) |
| **Reasoning** | `backend/reasoning/` | Zapis i formatowanie reasoning traces do audytu |
| **Timeline** | `backend/timeline/` | Bucketowanie czasu do scoringu i wizualizacji historii |
| **Scuttle Crab** | `rust/scuttle_crab/` | Crawler w Rust -- zbieranie, deduplikacja, normalizacja artykulow |
| **DB** | `db/` | Konfiguracja Neo4j i PostgreSQL, migracje |

---

## Tech Stack

### Frontend
- **Next.js 16** + React 19 + TypeScript 5
- **Tailwind CSS 4** + shadcn/ui
- **React Flow** (`@xyflow/react`) + D3 + Dagre -- wizualizacja grafow
- **Zustand** -- state management
- **Vitest** + MSW -- testy i mockowanie

### Backend
- **Python** + FastAPI 0.115 + Uvicorn
- **SQLAlchemy 2.0** + Alembic -- ORM i migracje
- **Neo4j Driver 5.10** -- graf relacji
- **OpenAI / Anthropic / OpenRouter** -- integracja z LLM
- **Pydantic 2.5** -- walidacja danych

### Crawler
- **Rust** (edition 2024) + Axum 0.8 + Tokio
- **Reqwest** + scraper + feed-rs -- HTTP, parsing HTML, RSS

### Infrastruktura
- **Docker Compose** -- orkiestracja serwisow
- **PostgreSQL 15** -- dane strukturalne
- **Neo4j** -- graf relacji

---

## Szybki start

Szczegolowa instrukcja uruchomienia (Docker + tryb deweloperski + konfiguracja env) znajduje sie w:

### **[SETUP.md -- Jak uruchomic projekt](./SETUP.md)**

Najszybsza sciezka (Docker):

```bash
# 1. Sklonuj repo
git clone https://github.com/your-org/trust-trace.git
cd trust-trace

# 2. Skopiuj i uzupelnij zmienne srodowiskowe
cp backend/.env.example .env
# edytuj .env -- ustaw LLM_API_KEY

# 3. Uruchom calosc
docker compose up --build
```

Po uruchomieniu:
- Frontend: http://localhost:3000
- Tarkov API: http://localhost:8081
- Neo4j Browser: http://localhost:7474

---

## Zespol

| Osoba | Rola |
|-------|------|
| **Jakub Mazurek** | Developer |
| **Wiktor Sekreta** | Developer |
| **Szymon Sidor** | Developer |
| **Tymoteusz Mosiolek** | Developer |
| **Marcel Geba** | Developer |

---

<p align="center">
  Projekt stworzony na <strong>CodeCamp 2026</strong>
</p>

# Tarkov Implementation Plan

**Goal:** Build a Python-based event extraction pipeline that receives raw articles from Scuttle Crab (Stage 1), extracts structured data about companies, events, and people, and persists them to PostgreSQL.

**Vision:** Tarkov is the bridge between raw article content and the AML scoring pipeline. It transforms unstructured text into structured database records that downstream scoring modules (Event Classifier, NSA, TrustWeb) can consume.

---

## High-Level Overview

### Purpose
Tarkov processes raw articles from Scuttle Crab and performs three main operations:
1. **Company Identification & Creation:** Find company references in articles; create new records if needed
2. **Event Extraction:** Identify money laundering and fraud-related events; persist to database
3. **Person Identification:** Extract and link people involved in events; persist to database

### Integration Points
- **Input:** Articles from Scuttle Crab (via JSONL or direct API call)
- **Database:** PostgreSQL (using SQLAlchemy ORM)
- **Output:** Populated firm, event, source, and person tables
- **Downstream:** Stage 3 (AML Scoring Pipeline) reads these records

### Architecture Pattern
```
[Scuttle Crab JSONL/API]
       ↓
[Tarkov Article Queue/Stream]
       ↓
[Company Matcher] → Identify or create firm records
       ↓
[Event Extractor] → Extract fraud/AML events from article
       ↓
[Person Extractor] → Extract people mentioned in event
       ↓
[Database Writer] → Persist: event, source, people records
       ↓
[PostgreSQL]
```

---

## Implementation Phases

### PHASE 1: Foundation & Architecture (Days 1-2)

#### 1.1 Project Structure & Dependencies

**Objective:** Set up Python project scaffold, install dependencies, and define core interfaces.

**Steps:**

1. Create Python project structure:
   ```
   backend/
   ├── tarkov/
   │   ├── __init__.py
   │   ├── main.py                      # Entry point
   │   ├── config.py                    # Configuration management
   │   ├── database/
   │   │   ├── __init__.py
   │   │   ├── models.py                # SQLAlchemy ORM models
   │   │   ├── session.py               # Database session management
   │   │   └── repositories/
   │   │       ├── __init__.py
   │   │       ├── firm_repo.py         # Firm CRUD operations
   │   │       ├── event_repo.py        # Event CRUD operations
   │   │       ├── person_repo.py       # Person CRUD operations
   │   │       └── source_repo.py       # Source CRUD operations
   │   ├── extraction/
   │   │   ├── __init__.py
   │   │   ├── company_matcher.py       # Company identification logic
   │   │   ├── event_extractor.py       # Event extraction logic (keyword + LLM)
   │   │   └── person_extractor.py      # Person extraction logic
   │   ├── llm/
   │   │   ├── __init__.py
   │   │   ├── client.py                # LLM API client wrapper
   │   │   └── prompts.py               # Prompt templates
   │   ├── schemas/
   │   │   ├── __init__.py
   │   │   ├── article.py               # Article input schema
   │   │   ├── event.py                 # Event output schema
   │   │   └── person.py                # Person output schema
   │   ├── pipeline/
   │   │   ├── __init__.py
   │   │   └── processor.py             # Main processing pipeline orchestrator
   │   ├── storage/
   │   │   ├── __init__.py
   │   │   └── article_reader.py        # Read articles from JSONL/API
   │   ├── keywords/
   │   │   ├── __init__.py
   │   │   └── aml_keywords.py          # AML/fraud keyword list
   │   ├── utils/
   │   │   ├── __init__.py
   │   │   ├── logger.py                # Logging configuration
   │   │   └── text_utils.py            # Text processing helpers
   │   └── tests/
   │       ├── __init__.py
   │       ├── test_company_matcher.py
   │       ├── test_event_extractor.py
   │       ├── test_person_extractor.py
   │       ├── test_pipeline.py
   │       ├── fixtures/
   │       │   ├── sample_articles.py
   │       │   └── sample_events.json
   │       └── integration/
   │           └── test_full_pipeline.py
   ├── requirements.txt
   ├── setup.py
   ├── .env.example
   ├── README.md
   └── Makefile
   ```

2. Create `requirements.txt` with core dependencies:
   ```
   # Core Database
   SQLAlchemy==2.0.23
   psycopg2-binary==2.9.9
   alembic==1.12.1
   
   # LLM Integration
   openai==1.3.0
   anthropic==0.7.0
   
   # Data Validation & Serialization
   pydantic==2.5.0
   marshmallow==3.20.0
   python-dateutil==2.8.2
   
   # CLI & Configuration
   click==8.1.7
   python-dotenv==1.0.0
   pyyaml==6.0.1
   
   # Logging & Observability
   python-logging-loki==0.3.2
   
   # Testing
   pytest==7.4.3
   pytest-asyncio==0.21.1
   pytest-cov==4.1.0
   factory-boy==3.3.0
   faker==20.1.0
   
   # Utilities
   requests==2.31.0
   click-log==0.4.0
   ```

3. Create `config.py` with environment-based configuration:
   ```python
   # Define config classes for: dev, test, prod
   # Include: DB URL, LLM API keys, logging, keywords file path, feature flags
   ```

4. Create `.env.example`:
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/trust_trace
   LLM_PROVIDER=openai  # or anthropic, or local
   LLM_API_KEY=sk-...
   LLM_MODEL=gpt-4
   LOG_LEVEL=INFO
   KEYWORDS_FILE_PATH=data/aml_keywords.json
   ARTICLE_INPUT_SOURCE=jsonl  # or api
   ARTICLE_INPUT_PATH=articles.jsonl
   ```

5. Create `setup.py` for package installation

6. Initialize Git and `.gitignore`:
   ```
   __pycache__/
   *.py[cod]
   .env
   .venv/
   .pytest_cache/
   .coverage
   htmlcov/
   dist/
   build/
   *.egg-info/
   ```

**Deliverables:**
- Project structure created
- `requirements.txt` finalized
- `config.py` implemented
- `.env.example` created
- Ready to install dependencies

---

#### 1.2 Database Models & ORM Setup

**Objective:** Define SQLAlchemy ORM models that map to the PostgreSQL schema from `001_initial_schema.sql`.

**Steps:**

1. Review existing schema in `db/migrations/001_initial_schema.sql`
   - Analyze tables: firm, firm_alias, event, source, sentiment, reputation_score, risk_keywords
   - Note relationships, constraints, and indexes

2. Create `database/models.py` with SQLAlchemy models:
   ```python
   # Model: Firm
   # - id (BIGINT PK AUTO_INCREMENT)
   # - full_name (TEXT)
   # - nip, regon, krs (unique identifiers)
   # - country (VARCHAR(3), default 'PL')
   # - created_at, updated_at (DATETIME)
   # - Relationship: firm_aliases (one-to-many), events (one-to-many)
   
   # Model: FirmAlias
   # - id (BIGINT PK AUTO_INCREMENT)
   # - firm_id (FK to Firm)
   # - alias (TEXT)
   # - alias_type (VARCHAR(50))
   
   # Model: Event
   # - unique_id (CHAR(36) UUID PK)
   # - firm_id (FK to Firm)
   # - title (TEXT)
   # - event_type (VARCHAR(100))
   # - risk_level (TINYINT 1-10)
   # - occurred_at (DATETIME)
   # - created_at (DATETIME)
   # - Relationships: source (one-to-many), people (many-to-many via association table)
   
   # Model: Source
   # - id (BIGINT PK AUTO_INCREMENT)
   # - event_id (FK to Event UUID)
   # - url (TEXT)
   # - title (TEXT)
   # - content (TEXT)
   # - language (VARCHAR(10))
   # - source_type (VARCHAR(50))
   # - published_at (DATETIME)
   # - created_at (DATETIME)
   # - credibility (DECIMAL(3,2) 0-1)
   
   # Model: Person
   # - id (BIGINT PK AUTO_INCREMENT)
   # - name (TEXT)
   # - role (VARCHAR(100))
   # - description (TEXT)
   # - Relationship: events (many-to-many via association table)
   
   # Association Table: PersonEvent
   # - person_id (FK)
   # - event_id (FK)
   ```

3. Create `database/session.py`:
   ```python
   # SessionLocal factory
   # get_db() context manager for dependency injection
   # Base declarative for all models
   ```

4. Create `database/repositories/` modules for CRUD operations:
   - `firm_repo.py`: get_or_create_firm(), find_by_alias(), list_firms()
   - `event_repo.py`: create_event(), get_event(), list_events_by_firm()
   - `person_repo.py`: create_person(), get_or_create_person(), link_person_to_event()
   - `source_repo.py`: create_source(), get_source()

**Deliverables:**
- `models.py` with all ORM models defined
- Repository modules for each entity
- Session factory and context managers
- Ready for database operations

---

#### 1.3 Schema for Tarkov-Specific Data

**Objective:** Define Pydantic schemas for input/output data validation.

**Steps:**

1. Create `schemas/article.py`:
   ```python
   # Schema: ArticleIn (from Scuttle Crab)
   # - source: { name, domain, url, credibility_score, credibility_label }
   # - article: { title, text, published_at, scraped_at, canonical_url, authors, language }
   # - metadata: { section, tags, tickers, companies, region, discovery_method, http_status }
   ```

2. Create `schemas/event.py`:
   ```python
   # Schema: EventOut
   # - event_type (fraud, money_laundering, regulatory_action, bankruptcy, etc.)
   # - risk_level (1-10)
   # - title (extracted event summary)
   # - occurred_at (event date)
   # - confidence (extraction confidence)
   # - description (detailed explanation)
   ```

3. Create `schemas/person.py`:
   ```python
   # Schema: PersonOut
   # - name
   # - role (CEO, Director, beneficial_owner, etc.)
   # - description
   # - confidence
   ```

**Deliverables:**
- Pydantic schemas for ArticleIn, EventOut, PersonOut
- Validation rules and type hints
- Ready for parsing and validation

---

### PHASE 2: Company Matching & Identification (Days 3-4)

#### 2.1 Company Matcher Implementation

**Objective:** Identify companies mentioned in articles and find or create firm records.

**Steps:**

1. Create `extraction/company_matcher.py`:
   ```python
   class CompanyMatcher:
       def __init__(self, db_session, company_reference_path: str):
           # Load company reference dictionary (from Scuttle Crab's data/companies.json)
           # Initialize database access
       
       def match_companies(self, article_text: str) -> List[MatchedCompany]:
           # Strategy 1: Keyword-based matching
           # - Exact ticker matches (e.g., "AAPL")
           # - Company name aliases from reference dictionary
           # - Case-insensitive substring matching
           # Return: [(company_name, ticker, confidence, matched_text), ...]
       
       def get_or_create_firm(self, company_name: str, ticker: str) -> Firm:
           # Check if firm exists by name or alias
           # If not found, create new firm record with alias
           # Return: Firm record
       
       def add_alias(self, firm: Firm, alias: str, alias_type: str):
           # Add new alias to firm (company name, ticker, abbreviation, etc.)
   ```

2. Create `keywords/aml_keywords.py`:
   ```python
   # Define company reference dictionary structure:
   # [
   #   { "name": "Apple", "ticker": "AAPL", "aliases": ["Apple", "Apple Inc."], "exchange": "NASDAQ" },
   #   ...
   # ]
   
   # For MVP: Load from data/companies.json (shared with Scuttle Crab)
   # For production: Load from Scuttle Crab's reference or external API
   ```

3. Create unit tests for company matching:
   - Test exact ticker match
   - Test company name alias match
   - Test case-insensitive matching
   - Test get_or_create_firm logic
   - Test alias addition

**Deliverables:**
- `company_matcher.py` fully implemented
- Company reference dictionary loaded and accessible
- Tests pass for all matching scenarios

---

#### 2.2 Integration with Database

**Objective:** Connect company matcher to database repositories.

**Steps:**

1. Update `firm_repo.py`:
   ```python
   def get_or_create_firm(self, name: str, ticker: str, country: str = 'PL') -> Firm:
       # Query existing firm by name or ticker
       # If found, return existing
       # If not found, create new firm with initial alias
       # Commit and return
   
   def add_alias(self, firm_id: int, alias: str, alias_type: str):
       # Create FirmAlias record linked to firm_id
   
   def find_by_alias(self, alias: str) -> Optional[Firm]:
       # Query FirmAlias table for match, return associated Firm
   ```

2. Update `company_matcher.py` to use repositories:
   ```python
   def get_or_create_firm(self, company_name: str, ticker: str) -> Firm:
       # Use firm_repo.get_or_create_firm()
       # Use firm_repo.add_alias() for new aliases
   ```

**Deliverables:**
- `firm_repo.py` fully implemented with all CRUD methods
- Company matcher uses repository pattern
- Database integration tested

---

### PHASE 3: Event Extraction (Days 5-7)

#### 3.1 Keyword-Based Event Detection

**Objective:** Detect fraud and AML-related events using keyword matching.

**Steps:**

1. Create `keywords/aml_keywords.py` with comprehensive keyword dictionary:
   ```python
   AML_KEYWORDS = {
       "money_laundering": [
           "money laundering",
           "suspicious transaction",
           "structuring",
           "smurfing",
           ...
       ],
       "fraud": [
           "fraud",
           "embezzlement",
           "ponzi",
           "pyramid scheme",
           ...
       ],
       "regulatory_action": [
           "regulatory action",
           "SEC investigation",
           "sanction",
           "fine",
           ...
       ],
       "bankruptcy": [
           "bankruptcy",
           "insolvency",
           "liquidation",
           ...
       ],
       ...
   }
   ```

2. Create `extraction/event_extractor.py`:
   ```python
   class EventExtractor:
       def __init__(self, llm_client=None):
           self.keywords = load_aml_keywords()
           self.llm_client = llm_client  # Optional LLM for enhanced extraction
       
       def extract_events_keyword_based(self, article_text: str) -> List[Event]:
           # Keyword-based approach:
           # 1. Split article into sentences
           # 2. For each sentence, check for keyword matches
           # 3. Group sentences by event type
           # 4. Generate event summary from grouped sentences
           # Return: List of Event objects with type, risk_level, description
       
       def extract_events_llm_based(self, article_text: str, firm_context: str) -> List[Event]:
           # LLM-based approach (optional, for MVP use keyword-based only):
           # 1. Prepare prompt with article and firm context
           # 2. Call LLM to extract events
           # 3. Parse LLM response into Event objects
           # 4. Return: List of Event objects
       
       def calculate_risk_level(self, event_type: str, keywords_found: List[str]) -> int:
           # Calculate risk level (1-10) based on event type and keywords
           # Higher risk for: fraud, money_laundering, regulatory_action
           # Lower risk for: news mentions, partnership updates
   ```

3. Create risk level calculation logic:
   ```python
   # Risk levels (1-10):
   # - 1-2: Low risk (news mentions, neutral)
   # - 3-4: Medium risk (business changes, structure updates)
   # - 5-6: Elevated risk (regulatory scrutiny, investigations)
   # - 7-8: High risk (fraud charges, money laundering suspicion)
   # - 9-10: Critical risk (convictions, active investigations)
   ```

**Deliverables:**
- `aml_keywords.py` with comprehensive keyword dictionary
- `event_extractor.py` with keyword-based extraction
- Risk level calculation logic
- Tests pass for event detection

---

#### 3.2 LLM-Based Event Extraction (Optional for MVP)

**Objective:** Enhance event extraction using LLM for complex event identification.

**Steps:**

1. Create `llm/client.py`:
   ```python
   class LLMClient:
       def __init__(self, provider: str, model: str, api_key: str):
           # Initialize LLM client (OpenAI, Anthropic, or local)
       
       def extract_events(self, article_text: str, firm_context: str) -> Dict:
           # Call LLM with extraction prompt
           # Return structured response
       
       def extract_people(self, article_text: str, event_context: str) -> List[Person]:
           # Call LLM to extract people
           # Return list of Person objects
   ```

2. Create `llm/prompts.py` with prompt templates:
   ```python
   EVENT_EXTRACTION_PROMPT = """
   You are an AML (Anti-Money Laundering) analyst. Extract fraud and AML-related events 
   from the article text.
   
   Article: {article_text}
   
   Firm Context: {firm_context}
   
   Extract events with: event_type, risk_level, title, description, people involved
   Response format: JSON
   """
   
   PERSON_EXTRACTION_PROMPT = """
   From the following text, extract all people mentioned and their roles:
   
   Text: {text}
   
   Response format: JSON with name, role, description
   """
   ```

3. Create `extraction/event_extractor.py` enhancement:
   ```python
   def extract_events_hybrid(self, article_text: str, firm_context: str, use_llm: bool = False) -> List[Event]:
       # First pass: Keyword-based extraction (fast, low-cost)
       keyword_events = self.extract_events_keyword_based(article_text)
       
       # Second pass: LLM-based extraction if confidence is low
       if use_llm and any(e.confidence < 0.7 for e in keyword_events):
           llm_events = self.extract_events_llm_based(article_text, firm_context)
           # Merge results, preferring higher confidence
       
       return keyword_events  # or merged results
   ```

**Note:** For MVP, keyword-based is sufficient. LLM-based extraction can be added in Phase 4.

**Deliverables:**
- `llm/client.py` implemented for chosen LLM provider
- `llm/prompts.py` with extraction prompts
- Hybrid extraction strategy (optional for MVP)

---

#### 3.3 Event Persistence

**Objective:** Save extracted events to database.

**Steps:**

1. Update `event_repo.py`:
   ```python
   def create_event(self, firm_id: int, event_data: EventOut) -> Event:
       # Create Event record with:
       # - firm_id
       # - title
       # - event_type
       # - risk_level
       # - occurred_at (or current timestamp)
       # - Return: Event record with unique_id
   
   def create_source(self, event_id: str, source_data: SourceIn) -> Source:
       # Create Source record linking article to event
       # - event_id (UUID from Event)
       # - url
       # - title
       # - content
       # - language
       # - published_at
       # - credibility
   ```

2. Update `pipeline/processor.py`:
   ```python
   def process_article(self, article: ArticleIn):
       # 1. Match companies in article
       firms = company_matcher.match_companies(article.article.text)
       
       # 2. For each firm, extract events
       for firm in firms:
           events = event_extractor.extract_events(article.article.text)
           
           # 3. For each event, create database records
           for event in events:
               db_event = event_repo.create_event(firm.id, event)
               source_repo.create_source(db_event.unique_id, {
                   "url": article.source.url,
                   "title": article.article.title,
                   "content": article.article.text,
                   "language": article.article.language,
                   "published_at": article.article.published_at,
                   "credibility": article.source.credibility_score
               })
   ```

**Deliverables:**
- `event_repo.py` with create_event() method
- `source_repo.py` fully implemented
- Event and source records persisted to database
- Tests pass for event/source creation

---

### PHASE 4: Person Extraction & Linking (Days 8-9)

#### 4.1 Person Extraction Logic

**Objective:** Extract people mentioned in events and link them to companies/events.

**Steps:**

1. Create `extraction/person_extractor.py`:
   ```python
   class PersonExtractor:
       def __init__(self, llm_client=None):
           self.llm_client = llm_client  # Optional LLM for person extraction
       
       def extract_people_keyword_based(self, text: str, event_context: str) -> List[Person]:
           # Keyword-based approach:
           # 1. Look for role keywords (CEO, Director, CFO, beneficial owner, etc.)
           # 2. Find adjacent names using simple patterns
           # 3. Extract person name and role
           # Return: List of Person objects
       
       def extract_people_llm_based(self, text: str, event_context: str) -> List[Person]:
           # LLM-based approach:
           # 1. Call LLM to extract people with roles
           # 2. Parse response into Person objects
           # Return: List of Person objects
       
       def match_name_patterns(self, text: str) -> List[NameMatch]:
           # Use regex patterns to find potential names
           # Pattern: Title + Capitalized Words (e.g., "Mr. John Smith", "Dr. Jane Doe")
           # Return: List of name candidates
   ```

2. Create role keywords dictionary:
   ```python
   ROLE_KEYWORDS = {
       "ceo": ["Chief Executive Officer", "CEO"],
       "cfo": ["Chief Financial Officer", "CFO"],
       "director": ["Director", "Board Member"],
       "owner": ["Owner", "Beneficial Owner", "Shareholder"],
       "founder": ["Founder", "Co-Founder"],
       ...
   }
   ```

3. Create `schemas/person.py`:
   ```python
   class Person(BaseModel):
       name: str
       role: str
       description: Optional[str]
       confidence: float  # 0.0-1.0
       mentioned_in_context: str  # Article/Event context
   ```

**Deliverables:**
- `person_extractor.py` implemented
- Role keywords dictionary created
- Person schema defined
- Tests pass for person extraction

---

#### 4.2 Person-Company-Event Linking

**Objective:** Link extracted people to companies and events in database.

**Steps:**

1. Update database models to add Person entity:
   ```python
   # Model: Person
   # - id (BIGINT PK AUTO_INCREMENT)
   # - name (TEXT)
   # - role (VARCHAR(100))
   # - description (TEXT)
   # - firm_id (FK to Firm, optional)
   # - created_at (DATETIME)
   
   # Association Table: PersonEvent
   # - person_id (FK to Person)
   # - event_id (FK to Event)
   # - role (VARCHAR(100), role in this specific event)
   # - confidence (DECIMAL(3,2))
   ```

2. Update `person_repo.py`:
   ```python
   def create_person(self, name: str, role: str, firm_id: Optional[int]) -> Person:
       # Create Person record
   
   def get_or_create_person(self, name: str, firm_id: Optional[int]) -> Person:
       # Get existing or create new person
   
   def link_person_to_event(self, person_id: int, event_id: str, role: str, confidence: float):
       # Create PersonEvent association
   ```

3. Update `pipeline/processor.py`:
   ```python
   def process_article(self, article: ArticleIn):
       ...
       for event in events:
           db_event = event_repo.create_event(firm.id, event)
           
           # Extract people from event context
           people = person_extractor.extract_people(article.article.text, event.description)
           
           # Link people to event and firm
           for person in people:
               db_person = person_repo.get_or_create_person(person.name, firm.id)
               person_repo.link_person_to_event(db_person.id, db_event.unique_id, person.role, person.confidence)
   ```

**Deliverables:**
- Person model and PersonEvent association table
- `person_repo.py` fully implemented
- People linked to events and firms
- Tests pass for person linking

---

### PHASE 5: Main Pipeline Orchestration (Days 10-11)

#### 5.1 Article Processing Pipeline

**Objective:** Create main processing pipeline that orchestrates all extraction steps.

**Steps:**

1. Update `storage/article_reader.py`:
   ```python
   class ArticleReader:
       def __init__(self, source: str, path: str):
           # source: 'jsonl' or 'api'
           # path: file path or API endpoint
       
       def read_articles(self) -> Iterator[ArticleIn]:
           # For JSONL: Read file line by line, parse JSON, yield ArticleIn objects
           # For API: Stream articles from API endpoint
       
       def read_article_batch(self, batch_size: int = 100) -> Iterator[List[ArticleIn]]:
           # Read articles in batches
   ```

2. Update `pipeline/processor.py`:
   ```python
   class ArticleProcessor:
       def __init__(self, db_session, config):
           self.company_matcher = CompanyMatcher(...)
           self.event_extractor = EventExtractor(...)
           self.person_extractor = PersonExtractor(...)
           self.db_session = db_session
       
       def process_article(self, article: ArticleIn):
           try:
               # 1. Match companies
               firms = self.company_matcher.match_companies(article.article.text)
               
               # 2. If no companies found, skip or flag
               if not firms:
                   logger.warning(f"No companies found in article: {article.article.title}")
                   return
               
               # 3. For each firm, extract events
               for firm in firms:
                   events = self.event_extractor.extract_events(article.article.text)
                   
                   for event in events:
                       # 4. Create event record
                       db_event = self.event_repo.create_event(firm.id, event)
                       
                       # 5. Create source record
                       self.source_repo.create_source(db_event.unique_id, ...)
                       
                       # 6. Extract and link people
                       people = self.person_extractor.extract_people(...)
                       for person in people:
                           db_person = self.person_repo.get_or_create_person(...)
                           self.person_repo.link_person_to_event(...)
               
               # 7. Commit transaction
               self.db_session.commit()
               logger.info(f"Processed article: {article.article.title}")
           
           except Exception as e:
               logger.error(f"Error processing article: {e}")
               self.db_session.rollback()
               raise
       
       def process_articles_batch(self, articles: List[ArticleIn]):
           for article in articles:
               self.process_article(article)
       
       def process_articles_stream(self, article_iterator: Iterator[ArticleIn]):
           for article in article_iterator:
               self.process_article(article)
   ```

3. Create `main.py`:
   ```python
   @click.group()
   def cli():
       pass
   
   @cli.command()
   @click.option('--input-source', default='jsonl')
   @click.option('--input-path', default='articles.jsonl')
   @click.option('--batch-size', default=100)
   def process_articles(input_source, input_path, batch_size):
       """Process articles from source and extract events."""
       config = Config.from_env()
       db_session = SessionLocal()
       
       reader = ArticleReader(input_source, input_path)
       processor = ArticleProcessor(db_session, config)
       
       for batch in reader.read_article_batch(batch_size):
           processor.process_articles_batch(batch)
       
       logger.info("All articles processed")
   
   @cli.command()
   @click.argument('article_path')
   def process_single(article_path):
       """Process a single article."""
       config = Config.from_env()
       db_session = SessionLocal()
       
       with open(article_path) as f:
           article_data = json.load(f)
       
       article = ArticleIn.parse_obj(article_data)
       processor = ArticleProcessor(db_session, config)
       processor.process_article(article)
   
   if __name__ == '__main__':
       cli()
   ```

**Deliverables:**
- `pipeline/processor.py` fully implemented
- `main.py` with CLI commands
- Article reader for JSONL/API
- End-to-end processing pipeline functional

---

#### 5.2 Error Handling & Resilience

**Objective:** Add robust error handling and recovery mechanisms.

**Steps:**

1. Create error handling in processor:
   ```python
   # Handle:
   # - Article parsing errors
   # - Company matching failures
   # - Event extraction failures
   # - Database constraint violations (duplicate event, foreign key errors)
   # - Transaction rollback and retry logic
   # - Dead letter queue for failed articles
   ```

2. Create dead letter queue:
   ```python
   # For failed articles:
   # - Log error with full context
   # - Write to dead_letters.jsonl for manual review
   # - Don't crash the pipeline
   ```

3. Create transaction handling:
   ```python
   # Use try/except/finally for each article
   # Rollback on error
   # Batch commits for performance
   ```

**Deliverables:**
- Error handling implemented
- Dead letter queue functional
- Transaction management in place
- Tests for error scenarios

---

### PHASE 6: Testing & Validation (Days 12-13)

#### 6.1 Unit Tests

**Objective:** Create comprehensive unit tests for all extraction modules.

**Steps:**

1. Create `tests/test_company_matcher.py`:
   ```python
   def test_exact_ticker_match():
       # Test matching "AAPL" to Apple
   
   def test_company_name_match():
       # Test matching "Apple Inc." to Apple
   
   def test_case_insensitive_match():
       # Test matching "apple" to Apple
   
   def test_multiple_companies_in_text():
       # Test extracting multiple companies
   
   def test_get_or_create_firm():
       # Test firm creation and retrieval
   ```

2. Create `tests/test_event_extractor.py`:
   ```python
   def test_money_laundering_detection():
       # Test detecting money laundering keywords
   
   def test_fraud_detection():
       # Test detecting fraud keywords
   
   def test_risk_level_calculation():
       # Test risk level assignment
   
   def test_event_extraction_from_article():
       # Test end-to-end event extraction
   ```

3. Create `tests/test_person_extractor.py`:
   ```python
   def test_role_keyword_detection():
       # Test detecting CEO, Director, etc.
   
   def test_name_pattern_matching():
       # Test extracting names
   
   def test_person_extraction_from_text():
       # Test end-to-end person extraction
   ```

4. Create `tests/test_pipeline.py`:
   ```python
   def test_process_article_full_flow():
       # Test complete article processing
   
   def test_process_article_no_companies():
       # Test handling articles with no companies
   
   def test_process_article_database_error():
       # Test error handling
   ```

5. Create test fixtures:
   ```python
   # tests/fixtures/sample_articles.py
   SAMPLE_ARTICLE_1 = {
       "source": { ... },
       "article": { ... },
       "metadata": { ... }
   }
   
   # tests/fixtures/sample_events.json
   [
       { "event_type": "fraud", "risk_level": 8, ... },
       ...
   ]
   ```

**Deliverables:**
- Unit tests pass (>80% coverage)
- Test fixtures created
- Mocking set up for LLM and database

---

#### 6.2 Integration Tests

**Objective:** Test end-to-end pipeline with real database.

**Steps:**

1. Create `tests/integration/test_full_pipeline.py`:
   ```python
   def test_full_pipeline_with_sample_article():
       # Create test database
       # Insert sample companies
       # Process sample article
       # Verify: Event created, linked to firm, source created, people extracted
   
   def test_multiple_articles_pipeline():
       # Process batch of articles
       # Verify all records created correctly
   
   def test_duplicate_article_handling():
       # Process same article twice
       # Verify deduplication works
   ```

2. Create test database setup:
   ```python
   # Use pytest fixtures to:
   # - Create temporary database
   # - Run migrations
   # - Seed initial data
   # - Cleanup after test
   ```

**Deliverables:**
- Integration tests pass
- Database setup/teardown working
- Full pipeline validated

---

### PHASE 7: CLI & Operations (Days 14-15)

#### 7.1 CLI Commands

**Objective:** Create user-friendly CLI for operations.

**Steps:**

1. Update `main.py` with commands:
   ```
   # Commands:
   # - process-articles: Process JSONL file
   # - process-api: Process articles from API stream
   # - import-companies: Load companies from reference file
   # - validate-schema: Validate article schema
   # - stats: Show processing statistics
   # - migrate: Run database migrations
   ```

2. Create `Makefile` for common tasks:
   ```makefile
   .PHONY: install test run docs clean
   
   install:
       pip install -r requirements.txt
   
   test:
       pytest tests/ -v --cov=tarkov
   
   run:
       python -m tarkov.main process-articles
   
   docs:
       pdoc --html tarkov
   
   clean:
       rm -rf build/ dist/ .pytest_cache/
   ```

3. Create comprehensive README:
   - Installation instructions
   - Configuration guide
   - CLI usage examples
   - Architecture overview
   - Contributing guidelines

**Deliverables:**
- CLI commands functional
- Makefile created
- README comprehensive
- Operations documented

---

#### 7.2 Monitoring & Logging

**Objective:** Add observability for production operation.

**Steps:**

1. Create `utils/logger.py`:
   ```python
   # Structured logging with:
   # - Log level: DEBUG, INFO, WARNING, ERROR
   # - Fields: timestamp, level, module, message, context
   # - Output: Console (dev), File (prod), Loki (optional)
   ```

2. Add metrics collection:
   ```python
   # Track:
   # - Articles processed
   # - Events created
   # - People extracted
   # - Errors by type
   # - Processing time
   # - Database operations
   ```

3. Create logging configuration in `config.py`:
   ```python
   LOG_LEVEL: str  # DEBUG, INFO, WARNING, ERROR
   LOG_OUTPUT: str  # console, file, loki
   LOG_FILE: str  # logs/tarkov.log
   LOKI_URL: str  # Optional Loki endpoint
   ```

**Deliverables:**
- Structured logging implemented
- Metrics collection in place
- Observability ready for production

---

### PHASE 8: Documentation & Deployment (Days 16-17)

#### 8.1 Documentation

**Objective:** Create comprehensive documentation.

**Steps:**

1. Create `docs/ARCHITECTURE.md`:
   - System design overview
   - Data flow diagram
   - Component interactions
   - Database schema explanation

2. Create `docs/EXTRACTION_STRATEGY.md`:
   - Keyword-based extraction details
   - LLM-based extraction (if implemented)
   - Confidence scoring
   - Edge cases and limitations

3. Create `docs/DATABASE.md`:
   - Schema documentation
   - Relationships and constraints
   - Indexing strategy
   - Query patterns

4. Create `docs/API_CONTRACT.md`:
   - Input article schema (from Scuttle Crab)
   - Output event schema
   - Person schema
   - Error responses

**Deliverables:**
- Architecture documentation
- API contract documented
- Database schema explained
- Extraction strategy documented

---

#### 8.2 Deployment

**Objective:** Prepare for deployment.

**Steps:**

1. Create `Dockerfile`:
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY tarkov/ ./tarkov/
   ENV PYTHONUNBUFFERED=1
   CMD ["python", "-m", "tarkov.main", "process-articles"]
   ```

2. Create `docker-compose.override.yml` (extends root docker-compose.yml):
   ```yaml
   services:
     tarkov:
       build:
         context: ./backend
       environment:
         DATABASE_URL: postgresql://user:password@postgres:5432/trust_trace
         LLM_PROVIDER: openai
         LOG_LEVEL: INFO
       depends_on:
         - postgres
       volumes:
         - ./articles.jsonl:/app/articles.jsonl
         - ./data:/app/data
   ```

3. Create deployment guide:
   - Environment setup
   - Configuration steps
   - Running with Docker
   - Monitoring in production

**Deliverables:**
- Dockerfile created
- Docker Compose configuration
- Deployment guide written
- Ready for container deployment

---

### PHASE 9: Performance & Optimization (Days 18-19)

#### 9.1 Performance Tuning

**Objective:** Optimize for throughput and scalability.

**Steps:**

1. Batch processing optimization:
   ```python
   # Batch size tuning:
   # - Memory usage: Limit number of articles in memory
   # - Database performance: Batch inserts via bulk_insert_mappings()
   # - Network: Reduce round trips
   ```

2. Database optimization:
   ```sql
   -- Add missing indexes for common queries:
   CREATE INDEX idx_event_firm_type ON event(firm_id, event_type);
   CREATE INDEX idx_source_event_url ON source(event_id, url);
   ```

3. Caching optimization:
   ```python
   # Cache:
   # - Company reference dictionary (loaded once at startup)
   # - LLM responses (if using LLM)
   # - Keyword match results
   ```

**Deliverables:**
- Performance benchmarks documented
- Batch processing optimized
- Database queries optimized
- Caching strategy in place

---

#### 9.2 Scalability Considerations

**Objective:** Design for scale.

**Steps:**

1. Horizontal scaling:
   ```python
   # Multi-worker architecture:
   # - Message queue (Kafka, RabbitMQ) for article distribution
   # - Multiple worker processes
   # - Idempotent processing for exactly-once semantics
   ```

2. Database connection pooling:
   ```python
   # SQLAlchemy pool configuration:
   # - pool_size: Number of connections
   # - max_overflow: Additional connections when needed
   # - pool_recycle: Recycle connections periodically
   ```

3. Monitoring & alerting:
   - CPU/memory usage
   - Database connection count
   - Processing latency
   - Error rates

**Deliverables:**
- Scalability architecture documented
- Connection pooling configured
- Monitoring setup documented
- Ready for scale testing

---

### PHASE 10: Final Review & Polish (Days 20)

#### 10.1 Code Review & Refactoring

**Objective:** Ensure code quality and consistency.

**Steps:**

1. Code style:
   - Black for formatting
   - flake8 for linting
   - mypy for type checking

2. Documentation:
   - Docstrings for all modules and functions
   - Type hints throughout
   - Comments for complex logic

3. Test coverage:
   - Aim for >80% coverage
   - Cover edge cases
   - Test error paths

**Deliverables:**
- Code passes linting
- Type hints complete
- Documentation comprehensive
- Test coverage >80%

---

#### 10.2 Acceptance Testing

**Objective:** Verify against requirements.

**Steps:**

1. Requirement verification checklist:
   - [ ] Company identification working
   - [ ] Event extraction working
   - [ ] Person extraction working
   - [ ] Database persistence working
   - [ ] Error handling robust
   - [ ] CLI functional
   - [ ] Documentation complete
   - [ ] Tests comprehensive
   - [ ] Performance acceptable

2. End-to-end scenario testing:
   - [ ] Process realistic article
   - [ ] Verify all records created
   - [ ] Verify relationships correct
   - [ ] Verify downstream integration ready

**Deliverables:**
- All requirements verified
- Acceptance testing passed
- Ready for production

---

## Technology Stack Summary

| Component | Technology | Justification |
|-----------|-----------|---------------|
| Language | Python 3.11+ | Data processing, LLM integration |
| ORM | SQLAlchemy 2.0 | Type-safe, flexible, PostgreSQL optimized |
| Database | PostgreSQL | ACID compliance, JSON support, proven reliability |
| LLM | OpenAI/Anthropic API | Advanced event extraction capability |
| CLI | Click | User-friendly, well-documented |
| Testing | pytest | Comprehensive, fixtures, parametrization |
| Logging | structlog + python-logging | Structured, machine-readable |
| Type Checking | mypy | Static type safety |
| Code Formatting | Black | Consistent, opinionated |
| Linting | flake8 | PEP8 compliance |

---

## Database Integration Points

### Input from Scuttle Crab
- **Format:** JSONL (newline-delimited JSON) or API stream
- **Fields:** source (name, domain, url, credibility), article (title, text, published_at, scraped_at, canonical_url, authors, language), metadata (section, tags, tickers, companies, region, discovery_method)

### Output to Database (PostgreSQL)
- **Tables:** firm, firm_alias, event, source, sentiment (optional), reputation_score (populated by Stage 3), person (new)
- **Relationships:**
  - firm 1 → many events
  - firm 1 → many firm_aliases
  - event 1 → many sources
  - event many → many people (via person_event association)

### Output to Stage 3 (AML Scoring Pipeline)
- **Upstream Data:** Populated firm, event, and person tables
- **Trigger:** When sufficient events collected for a company
- **Consumption:** Event Classifier reads events per firm; NSA reads person records per firm; TrustWeb reads firm relationships

---

## Configuration & Environment

### Required Environment Variables
```
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/trust_trace

# LLM (if using LLM-based extraction)
LLM_PROVIDER=openai  # or anthropic
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4

# File paths
ARTICLE_INPUT_SOURCE=jsonl
ARTICLE_INPUT_PATH=articles.jsonl
KEYWORDS_FILE_PATH=data/aml_keywords.json
COMPANY_REFERENCE_PATH=data/companies.json

# Logging
LOG_LEVEL=INFO
LOG_OUTPUT=console
```

---

## Data Contracts

### ArticleIn (from Scuttle Crab)
```json
{
  "source": {
    "name": "Reuters",
    "domain": "reuters.com",
    "url": "https://...",
    "credibility_score": 0.92,
    "credibility_label": "high"
  },
  "article": {
    "title": "...",
    "text": "...",
    "published_at": "2026-04-27T...",
    "scraped_at": "2026-04-27T...",
    "canonical_url": "https://...",
    "authors": ["..."],
    "language": "en"
  },
  "metadata": {
    "section": "...",
    "tags": [...],
    "tickers": [...],
    "companies": [...],
    "region": "..."
  }
}
```

### EventOut (to database)
```python
{
  "title": "...",
  "event_type": "fraud|money_laundering|regulatory_action|bankruptcy",
  "risk_level": 1-10,
  "occurred_at": "2026-04-27",
  "confidence": 0.0-1.0,
  "description": "..."
}
```

### PersonOut (to database)
```python
{
  "name": "...",
  "role": "CEO|Director|Owner|Founder|...",
  "description": "...",
  "confidence": 0.0-1.0
}
```

---

## Key Design Decisions

1. **Separation of Concerns:** Extraction logic separate from database logic
2. **Keyword-First Approach:** Start with keywords, enhance with LLM later
3. **Confidence Scoring:** Track confidence in extractions, allowing filtering
4. **Repository Pattern:** Abstract database access for testability
5. **Pydantic Schemas:** Type-safe data validation
6. **Batch Processing:** Process articles in batches for performance
7. **Error Resilience:** Dead letter queue for failed articles
8. **Logging-First:** Comprehensive logging for debugging and monitoring

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Company name ambiguity | Reference dictionary + exact matching first |
| Event extraction accuracy | Keyword + LLM hybrid, confidence scoring |
| Person extraction errors | Pattern-based extraction + validation |
| Database constraint errors | Try/catch with detailed logging |
| Performance degradation | Batch processing + indexing + connection pooling |
| Duplicate records | URL dedup from Scuttle Crab + database constraints |
| API rate limits (LLM) | Caching + local extraction fallback |

---

## Success Metrics

1. **Extraction Accuracy:** >85% precision on event extraction
2. **Company Matching:** >90% recall on companies in reference dictionary
3. **Processing Speed:** <1 second per article
4. **Data Quality:** <1% duplicate events
5. **System Reliability:** >99% uptime
6. **Test Coverage:** >80% code coverage

---

## Timeline Summary

| Phase | Days | Deliverable |
|-------|------|------------|
| 1. Foundation | 1-2 | Project structure, dependencies, models |
| 2. Company Matching | 3-4 | Company matcher, database integration |
| 3. Event Extraction | 5-7 | Keyword-based event extraction, LLM support |
| 4. Person Extraction | 8-9 | Person extraction, linking logic |
| 5. Pipeline | 10-11 | Main orchestration, error handling |
| 6. Testing | 12-13 | Unit + integration tests |
| 7. CLI & Ops | 14-15 | CLI commands, logging, monitoring |
| 8. Documentation | 16-17 | Docs, deployment, Docker |
| 9. Optimization | 18-19 | Performance tuning, scalability |
| 10. Polish | 20 | Code review, acceptance testing |

**Total Estimated Duration:** 20 work days (4 weeks)

---

## Next Steps

1. **Review & Approve:** Stakeholder review of plan
2. **Setup:** Create project structure, install dependencies
3. **Phase 1 Kickoff:** Begin foundation implementation
4. **Daily Standups:** Track progress, identify blockers
5. **Integration Testing:** Validate with Scuttle Crab output
6. **Deployment Prep:** Prepare for production deployment

---

## Appendix: File Structure

```
backend/
├── tarkov/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── session.py
│   │   └── repositories/
│   │       ├── __init__.py
│   │       ├── firm_repo.py
│   │       ├── event_repo.py
│   │       ├── person_repo.py
│   │       └── source_repo.py
│   ├── extraction/
│   │   ├── __init__.py
│   │   ├── company_matcher.py
│   │   ├── event_extractor.py
│   │   └── person_extractor.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   └── prompts.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── article.py
│   │   ├── event.py
│   │   └── person.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   └── processor.py
│   ├── storage/
│   │   ├── __init__.py
│   │   └── article_reader.py
│   ├── keywords/
│   │   ├── __init__.py
│   │   └── aml_keywords.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py
│   │   └── text_utils.py
│   └── tests/
│       ├── __init__.py
│       ├── test_company_matcher.py
│       ├── test_event_extractor.py
│       ├── test_person_extractor.py
│       ├── test_pipeline.py
│       ├── fixtures/
│       │   ├── sample_articles.py
│       │   └── sample_events.json
│       └── integration/
│           └── test_full_pipeline.py
├── requirements.txt
├── setup.py
├── .env.example
├── Dockerfile
├── Makefile
├── README.md
└── docs/
    ├── ARCHITECTURE.md
    ├── EXTRACTION_STRATEGY.md
    ├── DATABASE.md
    └── API_CONTRACT.md
```

---

**Document Version:** 1.0  
**Last Updated:** 2026-04-27  
**Status:** Ready for Implementation

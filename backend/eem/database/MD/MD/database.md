# Database

SQLAlchemy database models and session management used throughout the backend.

## What it does

Provides database models and connection handling for:
- Storing firms, events, persons, sources
- Managing connections between entities
- Persisting scoring results

## Key models

- `Firm` - Company records (name, NIP, REGON, KRS, country)
- `Event` - AML/fraud events linked to firms
- `Person` - Individuals associated with firms
- `Source` - Article sources and metadata
- `PersonEvent` - Links between persons and events
- `ConnectionEntity` - Entity connections with confidence scores

## Usage

```python
from tarkov.database.session import SessionLocal, get_session

with SessionLocal() as session:
    firm = session.query(Firm).filter_by(id=123).first()
```

## Session management

- `SessionLocal` - Session factory for creating DB connections
- `get_session` - Dependency injection helper
- `Base` - SQLAlchemy declarative base
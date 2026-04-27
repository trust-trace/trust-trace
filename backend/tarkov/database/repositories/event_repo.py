"""Event repository with Neo4j sync for Event nodes."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tarkov.database.models import Event
from tarkov.schemas.event import EventOut
from tarkov.database.session import get_neo4j_session


class EventRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_event(self, firm_id: int, event_data: EventOut, event_category: str = "classical") -> Event:
        obj = Event(
            firm_id=firm_id,
            title=event_data.title,
            event_type=event_data.event_type,
            event_category=event_category,
            risk_level=event_data.risk_level,
            occurred_at=event_data.occurred_at or datetime.utcnow(),
            extraction_confidence=event_data.confidence,
            source_text_quote=event_data.source_text,
        )
        self.db.add(obj)
        self.db.flush()

        # create Event node in Neo4j
        try:
            with get_neo4j_session() as g:
                props = {"event_id": obj.unique_id, "title": obj.title, "event_type": obj.event_type}
                g.create_node("Event", props)
                # link Event to Company node
                g.run("MATCH (e:Event {event_id: $eid}), (c:Company {company_id: $cid}) CREATE (c)-[:ABOUT]->(e)", eid=obj.unique_id, cid=firm_id)
        except Exception:
            pass

        return obj

    def get_event(self, event_id: str) -> Event | None:
        return self.db.execute(select(Event).where(Event.unique_id == event_id)).scalar_one_or_none()

    def list_events_by_firm(self, firm_id: int) -> list[Event]:
        stmt = select(Event).where(Event.firm_id == firm_id).order_by(Event.occurred_at.desc())
        return list(self.db.execute(stmt).scalars().all())

"""Person repository (Postgres-backed with standalone Neo4j node sync)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tarkov.database.models import Person, PersonEvent
from tarkov.database.session import get_neo4j_session


class PersonRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_person(
        self,
        name: str,
        role: str | None = None,
        firm_id: int | None = None,
        description: str | None = None,
    ) -> Person:
        obj = Person(name=name, role=role, firm_id=firm_id, description=description)
        self.db.add(obj)
        self.db.flush()

        try:
            with get_neo4j_session() as g:
                props = {"person_id": obj.id, "name": obj.name}
                if obj.role:
                    props["role"] = obj.role
                if firm_id:
                    props["firm_id"] = firm_id
                g.create_node("Person", props)
        except Exception:
            pass

        return obj

    def get_or_create_person(self, name: str, firm_id: int | None = None, role: str | None = None) -> Person:
        stmt = select(Person).where(func.lower(Person.name) == name.lower())
        if firm_id is not None:
            stmt = stmt.where(Person.firm_id == firm_id)
        obj = self.db.execute(stmt).scalar_one_or_none()
        if obj is not None:
            if role and not obj.role:
                obj.role = role
            return obj
        return self.create_person(name=name, role=role, firm_id=firm_id)

    def link_person_to_event(
        self,
        person_id: int,
        event_id: str,
        role: str | None = None,
        confidence: float | None = None,
    ) -> PersonEvent:
        existing = self.db.execute(
            select(PersonEvent).where(PersonEvent.person_id == person_id, PersonEvent.event_id == event_id)
        ).scalar_one_or_none()
        if existing:
            return existing

        obj = PersonEvent(
            person_id=person_id,
            event_id=event_id,
            role_in_event=role,
            confidence=confidence,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

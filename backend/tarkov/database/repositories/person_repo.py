"""Person repository (Postgres-backed with Neo4j node sync)."""

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

        # create person node in Neo4j
        try:
            with get_neo4j_session() as g:
                props = {"person_id": obj.id, "name": obj.name}
                if obj.role:
                    props["role"] = obj.role
                g.create_node("Person", props)
                if firm_id:
                    g.run(
                        "MATCH (p:Person {person_id: $pid}), (c:Company {company_id: $cid}) CREATE (p)-[:AFFILIATED_WITH {role: $role}]->(c)",
                        pid=obj.id,
                        cid=firm_id,
                        role=role,
                    )
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

        # create relationship in Neo4j
        try:
            with get_neo4j_session() as g:
                q = "MATCH (p:Person {person_id: $pid}), (e:Event {event_id: $eid}) CREATE (p)-[:INVOLVED_IN {role_in_event: $role, confidence: $conf}]->(e)"
                g.run(q, pid=person_id, eid=event_id, role=role, conf=confidence)
        except Exception:
            pass

        return obj

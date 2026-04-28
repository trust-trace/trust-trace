"""Frontend graph API bridge for the company graph dashboard."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from eem.database.models import EventEnrichment, FirmScore
from tarkov.config import Config
from tarkov.database.models import Event, Firm, Person, PersonEvent, Source
from tarkov.database.session import get_neo4j_driver, get_neo4j_session, init_neo4j


_LEGAL_SUFFIX_RE = re.compile(
    r"\s+(s\.?a\.?|sp\.?\s+z\s+o\.?o\.?|ltd\.?|ag|gmbh|inc\.?|llc|plc)\s*$",
    re.IGNORECASE,
)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_DATACLASS_KWARGS = {"slots": True} if sys.version_info >= (3, 10) else {}


@dataclass(**_DATACLASS_KWARGS)
class CompanyArticleStats:
    article_count: int
    last_update: datetime | None


class FrontendGraphService:
    """Reads Neo4j graph data and reshapes it into the frontend contract."""

    def __init__(self, config: Config):
        self._config = config

    def list_companies(self, db: Session) -> list[dict[str, Any]]:
        graph_rows = self._query_company_nodes()
        if not graph_rows:
            return []

        company_ids = [self._coerce_int(row.get("company_id")) for row in graph_rows]
        company_ids = [
            company_id for company_id in company_ids if company_id is not None
        ]
        firms = self._load_firms(db, company_ids)
        scores = self._load_scores(db, company_ids)
        article_stats = self._load_article_stats(db, company_ids)

        companies: list[dict[str, Any]] = []
        for row in graph_rows:
            firm_id = self._coerce_int(row.get("company_id"))
            if firm_id is None:
                continue

            firm = firms.get(firm_id)
            full_name = self._pick_company_name(row, firm)
            score_payload = self._build_score_payload(db, firm_id, scores.get(firm_id))
            stats = article_stats.get(
                firm_id, CompanyArticleStats(article_count=0, last_update=None)
            )

            companies.append(
                {
                    "id": self._company_slug(full_name, firm_id),
                    "name": full_name,
                    "short": self._short_company_name(full_name),
                    "nip": firm.nip if firm and firm.nip else "",
                    "sector": "Unknown",
                    "score": score_payload["score"],
                    "trend": score_payload["trend"],
                    "risk": score_payload["risk"],
                    "articles": stats.article_count,
                    "lastUpdate": self._to_iso8601(
                        stats.last_update or (firm.updated_at if firm else None)
                    ),
                    "history": score_payload["history"],
                    "keywords": score_payload["keywords"],
                }
            )

        companies.sort(key=lambda company: (company["name"], company["id"]))
        return companies

    def list_relations(self, db: Session) -> list[dict[str, Any]]:
        del db  # reserved for future SQL enrichments
        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}

        for row in self._query_company_relations():
            left_id = self._coerce_int(row.get("source_company_id"))
            right_id = self._coerce_int(row.get("target_company_id"))
            if left_id is None or right_id is None or left_id == right_id:
                continue

            source_name = (
                self._as_string(row.get("source_name")) or f"Company {left_id}"
            )
            target_name = (
                self._as_string(row.get("target_name")) or f"Company {right_id}"
            )
            relation_type = self._classify_relation_type(
                self._as_string(row.get("connection_type")),
                self._as_string(row.get("description")),
            )

            source_slug = self._company_slug(source_name, left_id)
            target_slug = self._company_slug(target_name, right_id)
            ordered = sorted(
                ((source_slug, source_name), (target_slug, target_name)),
                key=lambda item: item[0],
            )
            source_slug = ordered[0][0]
            target_slug = ordered[1][0]
            label = self._relation_label(row)
            strength = abs(self._coerce_float(row.get("intensity")) or 0.0)

            key = (source_slug, target_slug, relation_type)
            current = grouped.get(key)
            if current is None or strength > current["_strength"]:
                grouped[key] = {
                    "sourceCompanyId": source_slug,
                    "targetCompanyId": target_slug,
                    "type": relation_type,
                    "label": label,
                    "_strength": strength,
                }

        relations = []
        for relation in grouped.values():
            payload = {k: v for k, v in relation.items() if not k.startswith("_")}
            if not payload.get("label"):
                payload.pop("label", None)
            relations.append(payload)

        relations.sort(
            key=lambda relation: (
                relation["sourceCompanyId"],
                relation["targetCompanyId"],
                relation["type"],
            )
        )
        return relations

    def list_articles(self, db: Session, company_id: str) -> list[dict[str, Any]]:
        firm = self._find_firm_by_slug(db, company_id)
        if firm is None:
            return []

        stmt = (
            select(Event, Source, EventEnrichment)
            .outerjoin(
                Source,
                (Source.event_id == Event.unique_id)
                & (Source.source_category == "article"),
            )
            .outerjoin(EventEnrichment, EventEnrichment.event_id == Event.unique_id)
            .where(Event.firm_id == firm.id)
            .order_by(
                func.coalesce(
                    Source.published_at, Event.occurred_at, Source.created_at
                ).desc(),
                Event.unique_id.desc(),
            )
        )

        articles: list[dict[str, Any]] = []
        for event, source, enrichment in db.execute(stmt):
            keywords = self._load_json_list(enrichment.keywords if enrichment else None)
            entities = self._load_json_list(enrichment.entities if enrichment else None)
            article_date = None
            if source is not None and source.published_at is not None:
                article_date = source.published_at
            elif event.occurred_at is not None:
                article_date = event.occurred_at
            elif source is not None:
                article_date = source.created_at

            articles.append(
                {
                    "id": event.unique_id,
                    "headline": (
                        source.title if source and source.title else event.title
                    ),
                    "source": self._source_name(source.url if source else None),
                    "sourceTier": self._source_tier(source, enrichment),
                    "date": self._to_iso8601(article_date),
                    "sentiment": self._article_sentiment(event, enrichment),
                    "impact": self._article_impact(event, enrichment),
                    "keywords": keywords,
                    "excerpt": self._article_excerpt(event, source, enrichment),
                    "entities": entities or [firm.full_name],
                }
            )

        return articles

    def get_graph(
        self, db: Session, company_id: str, max_depth: int = 2
    ) -> dict[str, Any]:
        graph_company = self._find_graph_company_by_slug(company_id)
        firm = self._find_firm_by_slug(db, company_id)

        graph_company_id = graph_company["firm_id"] if graph_company else None
        root_company_id = firm.id if firm is not None else graph_company_id

        if root_company_id is None:
            return {"rootId": "", "nodes": [], "edges": []}

        node_rows = self._query_graph_nodes(root_company_id, max_depth)
        edge_rows = self._query_graph_edges(root_company_id, max_depth)

        company_ids: set[int] = set()
        person_ids: set[int] = set()
        event_ids: set[str] = set()
        for row in node_rows:
            node_type = self._graph_node_type(row.get("labels"))
            entity_id = self._graph_entity_id(row.get("node"), node_type)
            if entity_id is None:
                continue
            if node_type == "Company":
                company_ids.add(int(entity_id))
            elif node_type == "Person":
                person_ids.add(int(entity_id))
            elif node_type == "Event":
                event_ids.add(entity_id)

        direct_people = self._load_people_for_firms(db, sorted(company_ids))
        person_event_links = self._load_person_events_for_events(db, sorted(event_ids))
        for person in direct_people:
            person_ids.add(int(person.id))
        for link in person_event_links:
            person_ids.add(int(link.person_id))

        firms = self._load_firms(db, sorted(company_ids))
        scores = self._load_scores(db, sorted(company_ids))
        article_stats = self._load_article_stats(db, sorted(company_ids))
        people = self._load_people(db, sorted(person_ids))
        person_stats = self._load_person_event_stats(db, sorted(person_ids))
        events = self._load_events(db, sorted(event_ids))
        event_enrichments = self._load_event_enrichments(db, sorted(event_ids))
        event_sources = self._load_event_sources(db, sorted(event_ids))

        company_depths: dict[int, int] = {}
        event_depths: dict[str, int] = {}
        for row in node_rows:
            node_type = self._graph_node_type(row.get("labels"))
            entity_id = self._graph_entity_id(row.get("node") or {}, node_type)
            depth = self._coerce_int(row.get("depth")) or 0
            if entity_id is None:
                continue
            if node_type == "Company":
                company_depths[int(entity_id)] = depth
            elif node_type == "Event":
                event_depths[str(entity_id)] = depth

        person_links_by_person: dict[int, list[PersonEvent]] = {}
        for link in person_event_links:
            person_links_by_person.setdefault(int(link.person_id), []).append(link)

        person_trust: dict[int, int] = {}
        person_risk: dict[int, str] = {}
        for person_id in person_ids:
            trust_score = self._person_trust_score(
                person_links_by_person.get(int(person_id), []),
                events,
            )
            person_trust[int(person_id)] = trust_score
            person_risk[int(person_id)] = self._risk_from_score(trust_score)

        nodes: list[dict[str, Any]] = []
        seen_node_ids: set[str] = set()
        for row in node_rows:
            node_type = self._graph_node_type(row.get("labels"))
            node_props = row.get("node") or {}
            entity_id = self._graph_entity_id(node_props, node_type)
            if entity_id is None:
                continue

            depth = self._coerce_int(row.get("depth")) or 0
            node_key = self._typed_node_id(node_type, entity_id)
            node_payload = {
                "id": node_key,
                "entityType": node_type,
                "entityId": entity_id,
                "depth": depth,
            }

            if node_type == "Company":
                firm_id = int(entity_id)
                firm_row = firms.get(firm_id)
                full_name = self._pick_company_name(
                    {"name": node_props.get("name")}, firm_row
                )
                score_payload = self._build_score_payload(
                    db, firm_id, scores.get(firm_id)
                )
                stats = article_stats.get(
                    firm_id, CompanyArticleStats(article_count=0, last_update=None)
                )
                node_payload["label"] = full_name
                node_payload["data"] = {
                    "id": self._company_slug(full_name, firm_id),
                    "name": full_name,
                    "short": self._short_company_name(full_name),
                    "nip": firm_row.nip if firm_row and firm_row.nip else "",
                    "country": firm_row.country if firm_row else "",
                    "score": score_payload["score"],
                    "trend": score_payload["trend"],
                    "risk": score_payload["risk"],
                    "history": score_payload["history"],
                    "keywords": score_payload["keywords"],
                    "articles": stats.article_count,
                    "lastUpdate": self._to_iso8601(
                        stats.last_update or (firm_row.updated_at if firm_row else None)
                    ),
                }
            elif node_type == "Person":
                person_id = int(entity_id)
                person = people.get(person_id)
                stats = person_stats.get(person_id, 0)
                affiliated_slug = None
                affiliated_name = None
                if person is not None and person.firm_id is not None:
                    affiliated_firm = firms.get(person.firm_id) or db.get(
                        Firm, person.firm_id
                    )
                    if affiliated_firm is not None:
                        affiliated_name = affiliated_firm.full_name
                        affiliated_slug = self._company_slug(
                            affiliated_firm.full_name, affiliated_firm.id
                        )
                node_payload["label"] = (
                    person.name if person else node_props.get("name") or entity_id
                )
                node_payload["data"] = {
                    "name": person.name
                    if person
                    else self._as_string(node_props.get("name")),
                    "role": person.role if person and person.role else "",
                    "description": person.description
                    if person and person.description
                    else "",
                    "firmId": affiliated_slug or "",
                    "firmName": affiliated_name or "",
                    "eventCount": stats,
                    "trustScore": person_trust.get(person_id, 100),
                    "risk": person_risk.get(person_id, "low"),
                }
            else:
                event = events.get(entity_id)
                enrichment = event_enrichments.get(entity_id)
                source = event_sources.get(entity_id)
                company_slug_ref = ""
                company_name_ref = ""
                if event is not None:
                    owner_firm = firms.get(event.firm_id) or db.get(Firm, event.firm_id)
                    if owner_firm is not None:
                        company_name_ref = owner_firm.full_name
                        company_slug_ref = self._company_slug(
                            owner_firm.full_name, owner_firm.id
                        )
                label = (
                    event.title
                    if event
                    else self._as_string(node_props.get("title")) or entity_id
                )
                node_payload["label"] = label
                node_payload["data"] = {
                    "title": label,
                    "eventType": event.event_type
                    if event
                    else self._as_string(node_props.get("event_type")),
                    "eventCategory": event.event_category if event else "",
                    "riskLevel": int(event.risk_level)
                    if event
                    else self._coerce_int(node_props.get("risk_level")) or 0,
                    "risk": self._risk_from_score(
                        100
                        - (
                            (
                                int(event.risk_level)
                                if event
                                else self._coerce_int(node_props.get("risk_level")) or 0
                            )
                            * 10
                        )
                    ),
                    "occurredAt": self._to_iso8601(
                        event.occurred_at if event else None
                    ),
                    "companyId": company_slug_ref,
                    "companyName": company_name_ref,
                    "excerpt": self._article_excerpt(event, source, enrichment)
                    if event
                    else "",
                    "keywords": self._load_json_list(
                        enrichment.keywords if enrichment else None
                    ),
                    "entities": self._load_json_list(
                        enrichment.entities if enrichment else None
                    ),
                    "source": self._source_name(source.url if source else None),
                    "sourceTitle": source.title if source and source.title else "",
                    "sourceUrl": source.url if source else "",
                }

            seen_node_ids.add(node_payload["id"])
            nodes.append(node_payload)

        for person in people.values():
            node_key = self._typed_node_id("Person", str(person.id))
            if node_key in seen_node_ids:
                continue

            candidate_depths: list[int] = []
            if person.firm_id is not None and person.firm_id in company_depths:
                candidate_depths.append(company_depths[person.firm_id] + 1)
            for link in person_links_by_person.get(int(person.id), []):
                if link.event_id in event_depths:
                    candidate_depths.append(event_depths[link.event_id] + 1)

            if not candidate_depths:
                continue

            depth = min(candidate_depths)
            if depth > max_depth:
                continue

            affiliated_name = None
            affiliated_slug = None
            if person.firm_id is not None:
                affiliated_firm = firms.get(person.firm_id) or db.get(
                    Firm, person.firm_id
                )
                if affiliated_firm is not None:
                    affiliated_name = affiliated_firm.full_name
                    affiliated_slug = self._company_slug(
                        affiliated_firm.full_name, affiliated_firm.id
                    )

            node_payload = {
                "id": node_key,
                "entityType": "Person",
                "entityId": str(person.id),
                "depth": depth,
                "label": person.name,
                "data": {
                    "name": person.name,
                    "role": person.role if person.role else "",
                    "description": person.description if person.description else "",
                    "firmId": affiliated_slug or "",
                    "firmName": affiliated_name or "",
                    "eventCount": person_stats.get(int(person.id), 0),
                    "trustScore": person_trust.get(int(person.id), 100),
                    "risk": person_risk.get(int(person.id), "low"),
                },
            }
            seen_node_ids.add(node_key)
            nodes.append(node_payload)

        edges: list[dict[str, Any]] = []
        seen_edges: set[str] = set()
        for row in edge_rows:
            source_type = self._graph_node_type(row.get("source_labels"))
            target_type = self._graph_node_type(row.get("target_labels"))
            source_id = self._graph_entity_id(row.get("source_node") or {}, source_type)
            target_id = self._graph_entity_id(row.get("target_node") or {}, target_type)
            if source_id is None or target_id is None:
                continue

            edge_id = self._typed_edge_id(
                source_type,
                source_id,
                target_type,
                target_id,
                self._as_string(row.get("relationship_type")) or "CONNECTION",
                self._as_string(row.get("connection_type")),
            )
            if edge_id in seen_edges:
                continue
            seen_edges.add(edge_id)

            relationship_type = (
                self._as_string(row.get("relationship_type")) or "CONNECTION"
            )
            label = self._graph_edge_label(relationship_type, row)
            edges.append(
                {
                    "id": edge_id,
                    "source": self._typed_node_id(source_type, source_id),
                    "target": self._typed_node_id(target_type, target_id),
                    "relationshipType": relationship_type,
                    "connectionType": self._as_string(row.get("connection_type")),
                    "intensity": self._coerce_float(row.get("intensity")),
                    "label": label,
                    "sourceUrl": self._as_string(row.get("source_url")),
                    "sourceTitle": self._as_string(row.get("source_title")),
                }
            )

        for person in people.values():
            person_node_id = self._typed_node_id("Person", str(person.id))
            if person_node_id not in seen_node_ids or person.firm_id is None:
                continue
            if person.firm_id not in company_depths:
                continue

            edge_id = self._typed_edge_id(
                "Company",
                str(person.firm_id),
                "Person",
                str(person.id),
                "AFFILIATED_WITH",
                "",
            )
            if edge_id in seen_edges:
                continue
            seen_edges.add(edge_id)
            edges.append(
                {
                    "id": edge_id,
                    "source": self._typed_node_id("Company", str(person.firm_id)),
                    "target": person_node_id,
                    "relationshipType": "AFFILIATED_WITH",
                    "connectionType": "",
                    "intensity": None,
                    "label": "Affiliated with",
                    "sourceUrl": "",
                    "sourceTitle": "",
                }
            )

        for link in person_event_links:
            person_node_id = self._typed_node_id("Person", str(link.person_id))
            event_node_id = self._typed_node_id("Event", str(link.event_id))
            if (
                person_node_id not in seen_node_ids
                or str(link.event_id) not in event_depths
            ):
                continue

            source = event_sources.get(str(link.event_id))
            edge_id = self._typed_edge_id(
                "Person",
                str(link.person_id),
                "Event",
                str(link.event_id),
                "INVOLVED_IN",
                self._as_string(link.role_in_event),
            )
            if edge_id in seen_edges:
                continue
            seen_edges.add(edge_id)
            edges.append(
                {
                    "id": edge_id,
                    "source": person_node_id,
                    "target": event_node_id,
                    "relationshipType": "INVOLVED_IN",
                    "connectionType": self._as_string(link.role_in_event),
                    "intensity": self._coerce_float(link.confidence),
                    "label": "Involved in",
                    "sourceUrl": source.url if source else "",
                    "sourceTitle": source.title if source and source.title else "",
                }
            )

        nodes.sort(
            key=lambda node: (
                node["depth"],
                node["entityType"],
                node["label"],
                node["entityId"],
            )
        )
        edges.sort(key=lambda edge: edge["id"])

        return {
            "rootId": self._typed_node_id("Company", str(root_company_id)),
            "nodes": nodes,
            "edges": edges,
        }

    def _ensure_neo4j(self) -> None:
        try:
            get_neo4j_driver()
        except RuntimeError:
            init_neo4j(
                self._config.neo4j_uri,
                self._config.neo4j_user,
                self._config.neo4j_password,
            )

    def _query_company_nodes(self) -> list[dict[str, Any]]:
        return self._run_graph_query(
            """
            MATCH (c:Company)
            RETURN DISTINCT
              toString(c.company_id) AS company_id,
              coalesce(c.name, c.full_name) AS name
            ORDER BY name
            """
        )

    def _query_company_relations(self) -> list[dict[str, Any]]:
        return self._run_graph_query(
            """
            MATCH (source:Company)-[r:CONNECTION]->(target:Company)
            RETURN
              toString(source.company_id) AS source_company_id,
              coalesce(source.name, source.full_name) AS source_name,
              toString(target.company_id) AS target_company_id,
              coalesce(target.name, target.full_name) AS target_name,
              coalesce(r.type, '') AS connection_type,
              coalesce(r.llm_description, '') AS description,
              r.intensity AS intensity,
              r.scored_at AS scored_at
            ORDER BY source_name, target_name
            """
        )

    def _query_graph_nodes(self, firm_id: int, max_depth: int) -> list[dict[str, Any]]:
        depth = max(0, int(max_depth))
        return self._run_graph_query(
            f"""
            MATCH path = (root:Company {{company_id: $company_id}})-[*0..{depth}]-(node)
            RETURN node, labels(node) AS labels, min(length(path)) AS depth
            ORDER BY depth, coalesce(node.name, node.title, '')
            """,
            company_id=str(firm_id),
        )

    def _query_graph_edges(self, firm_id: int, max_depth: int) -> list[dict[str, Any]]:
        depth = max(1, int(max_depth))
        return self._run_graph_query(
            f"""
            MATCH path = (root:Company {{company_id: $company_id}})-[*1..{depth}]-(node)
            UNWIND relationships(path) AS rel
            WITH DISTINCT rel
            RETURN
              type(rel) AS relationship_type,
              labels(startNode(rel)) AS source_labels,
              startNode(rel) AS source_node,
              labels(endNode(rel)) AS target_labels,
              endNode(rel) AS target_node,
              coalesce(rel.type, '') AS connection_type,
              rel.intensity AS intensity,
              coalesce(rel.llm_description, rel.role, rel.role_in_event, '') AS description,
              coalesce(rel.source_url, '') AS source_url,
              coalesce(rel.source_title, '') AS source_title
            """,
            company_id=str(firm_id),
        )

    def _run_graph_query(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        self._ensure_neo4j()
        with get_neo4j_session() as session:
            return [record.data() for record in session.run(cypher, **params)]

    def _load_firms(self, db: Session, firm_ids: list[int]) -> dict[int, Firm]:
        if not firm_ids:
            return {}
        firms = db.execute(select(Firm).where(Firm.id.in_(firm_ids))).scalars().all()
        return {firm.id: firm for firm in firms}

    def _load_scores(self, db: Session, firm_ids: list[int]) -> dict[int, FirmScore]:
        if not firm_ids:
            return {}
        scores = (
            db.execute(select(FirmScore).where(FirmScore.firm_id.in_(firm_ids)))
            .scalars()
            .all()
        )
        return {score.firm_id: score for score in scores}

    def _load_article_stats(
        self, db: Session, firm_ids: list[int]
    ) -> dict[int, CompanyArticleStats]:
        if not firm_ids:
            return {}

        stmt = (
            select(
                Event.firm_id,
                func.count(Source.id),
                func.max(
                    func.coalesce(
                        Source.published_at, Event.occurred_at, Source.created_at
                    )
                ),
            )
            .outerjoin(
                Source,
                (Source.event_id == Event.unique_id)
                & (Source.source_category == "article"),
            )
            .where(Event.firm_id.in_(firm_ids))
            .group_by(Event.firm_id)
        )

        stats: dict[int, CompanyArticleStats] = {}
        for firm_id, article_count, last_update in db.execute(stmt):
            stats[int(firm_id)] = CompanyArticleStats(
                article_count=int(article_count or 0),
                last_update=last_update,
            )
        return stats

    def _load_people(self, db: Session, person_ids: list[int]) -> dict[int, Person]:
        if not person_ids:
            return {}
        people = (
            db.execute(select(Person).where(Person.id.in_(person_ids))).scalars().all()
        )
        return {person.id: person for person in people}

    def _load_people_for_firms(self, db: Session, firm_ids: list[int]) -> list[Person]:
        if not firm_ids:
            return []
        return list(
            db.execute(select(Person).where(Person.firm_id.in_(firm_ids)))
            .scalars()
            .all()
        )

    def _load_person_event_stats(
        self, db: Session, person_ids: list[int]
    ) -> dict[int, int]:
        if not person_ids:
            return {}
        stmt = (
            select(PersonEvent.person_id, func.count(PersonEvent.id))
            .where(PersonEvent.person_id.in_(person_ids))
            .group_by(PersonEvent.person_id)
        )
        return {
            int(person_id): int(count or 0) for person_id, count in db.execute(stmt)
        }

    def _load_person_events_for_events(
        self, db: Session, event_ids: list[str]
    ) -> list[PersonEvent]:
        if not event_ids:
            return []
        return list(
            db.execute(select(PersonEvent).where(PersonEvent.event_id.in_(event_ids)))
            .scalars()
            .all()
        )

    def _load_events(self, db: Session, event_ids: list[str]) -> dict[str, Event]:
        if not event_ids:
            return {}
        events = (
            db.execute(select(Event).where(Event.unique_id.in_(event_ids)))
            .scalars()
            .all()
        )
        return {event.unique_id: event for event in events}

    def _load_event_enrichments(
        self, db: Session, event_ids: list[str]
    ) -> dict[str, EventEnrichment]:
        if not event_ids:
            return {}
        rows = (
            db.execute(
                select(EventEnrichment).where(EventEnrichment.event_id.in_(event_ids))
            )
            .scalars()
            .all()
        )
        return {row.event_id: row for row in rows}

    def _load_event_sources(
        self, db: Session, event_ids: list[str]
    ) -> dict[str, Source]:
        if not event_ids:
            return {}

        stmt = (
            select(Source)
            .where(Source.event_id.in_(event_ids), Source.source_category == "article")
            .order_by(
                Source.event_id,
                func.coalesce(Source.published_at, Source.created_at).desc(),
                Source.id.desc(),
            )
        )

        sources: dict[str, Source] = {}
        for source in db.execute(stmt).scalars():
            sources.setdefault(source.event_id, source)
        return sources

    def _build_score_payload(
        self, db: Session, firm_id: int, score_row: FirmScore | None
    ) -> dict[str, Any]:
        if score_row is not None:
            history = [
                int(value)
                for value in self._load_json_list(score_row.score_history)
                if isinstance(value, (int, float))
            ]
            history = history or [int(score_row.score)]
            return {
                "score": int(score_row.score),
                "trend": int(score_row.trend),
                "risk": score_row.risk
                if score_row.risk in {"high", "medium", "low"}
                else self._risk_from_score(int(score_row.score)),
                "history": history,
                "keywords": self._load_json_list(score_row.keywords),
            }

        fallback_score = 50
        fallback_trend = 0
        try:
            row = db.execute(
                text(
                    "SELECT score, delta FROM reputation_score "
                    "WHERE firm_id = :firm_id ORDER BY calculated_at DESC LIMIT 1"
                ),
                {"firm_id": firm_id},
            ).first()
            if row is not None:
                fallback_score = int(round(float(row.score) * 100))
                fallback_trend = int(round(float(row.delta or 0) * 100))
        except Exception:
            pass

        return {
            "score": fallback_score,
            "trend": fallback_trend,
            "risk": self._risk_from_score(fallback_score),
            "history": [fallback_score],
            "keywords": [],
        }

    def _find_firm_by_slug(self, db: Session, company_id: str) -> Firm | None:
        firms = db.execute(select(Firm).order_by(Firm.id)).scalars().all()
        for firm in firms:
            if self._company_slug(firm.full_name, firm.id) == company_id:
                return firm
        return None

    def _find_graph_company_by_slug(self, company_id: str) -> dict[str, Any] | None:
        for row in self._query_company_nodes():
            firm_id = self._coerce_int(row.get("company_id"))
            if firm_id is None:
                continue

            name = self._as_string(row.get("name")) or f"Company {firm_id}"
            if self._company_slug(name, firm_id) == company_id:
                return {
                    "firm_id": firm_id,
                    "name": name,
                }

        return None

    @staticmethod
    def _pick_company_name(row: dict[str, Any], firm: Firm | None) -> str:
        graph_name = FrontendGraphService._as_string(row.get("name"))
        if graph_name:
            return graph_name
        if firm is not None:
            return firm.full_name
        return f"Company {row.get('company_id', '')}".strip()

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_string(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _load_json_list(value: str | None) -> list[Any]:
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []

    @staticmethod
    def _short_company_name(name: str) -> str:
        trimmed = _LEGAL_SUFFIX_RE.sub("", name).strip(" ,")
        return trimmed or name

    @staticmethod
    def _company_slug(name: str, firm_id: int) -> str:
        normalized = (
            unicodedata.normalize("NFKD", name)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        normalized = _LEGAL_SUFFIX_RE.sub("", normalized)
        slug = _NON_ALNUM_RE.sub("-", normalized.lower()).strip("-")
        return slug or f"company-{firm_id}"

    @staticmethod
    def _risk_from_score(score: int) -> str:
        if score < 40:
            return "high"
        if score < 70:
            return "medium"
        return "low"

    @staticmethod
    def _person_trust_score(links: list[PersonEvent], events: dict[str, Event]) -> int:
        if not links:
            return 100

        weighted_penalties: list[float] = []
        for link in links:
            event = events.get(str(link.event_id))
            if event is None:
                continue
            confidence = link.confidence if link.confidence is not None else 1.0
            confidence = max(0.0, min(float(confidence), 1.0))
            weighted_penalties.append(float(event.risk_level) * 10.0 * confidence)

        if not weighted_penalties:
            return 100

        trust_score = int(
            round(100.0 - (sum(weighted_penalties) / len(weighted_penalties)))
        )
        return max(0, min(100, trust_score))

    @staticmethod
    def _to_iso8601(value: datetime | None) -> str:
        if value is None:
            return ""
        return value.isoformat()

    @staticmethod
    def _classify_relation_type(connection_type: str, description: str) -> str:
        haystack = f"{connection_type} {description}".lower()
        if any(
            token in haystack
            for token in (
                "person",
                "board",
                "executive",
                "advisor",
                "director",
                "owner",
                "shareholder",
                "ceo",
                "supervisory",
            )
        ):
            return "person"
        if any(
            token in haystack
            for token in (
                "partnership",
                "partner",
                "alliance",
                "joint venture",
                "strategic",
            )
        ):
            return "partnership"
        return "business"

    @staticmethod
    def _relation_label(row: dict[str, Any]) -> str:
        description = FrontendGraphService._as_string(row.get("description"))
        if description:
            return description
        connection_type = FrontendGraphService._as_string(row.get("connection_type"))
        return connection_type.replace("_", " ").strip().title()

    @staticmethod
    def _graph_node_type(labels: Any) -> str:
        if isinstance(labels, list):
            for label in ("Company", "Person", "Event"):
                if label in labels:
                    return label
        return "Unknown"

    @staticmethod
    def _graph_entity_id(node: dict[str, Any], node_type: str) -> str | None:
        if node_type == "Company":
            value = node.get("company_id")
        elif node_type == "Person":
            value = node.get("person_id")
        elif node_type == "Event":
            value = node.get("event_id")
        else:
            value = (
                node.get("company_id") or node.get("person_id") or node.get("event_id")
            )
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _typed_node_id(node_type: str, entity_id: str) -> str:
        return f"{node_type.lower()}:{entity_id}"

    @staticmethod
    def _typed_edge_id(
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        relationship_type: str,
        connection_type: str,
    ) -> str:
        return (
            f"{source_type.lower()}:{source_id}->{target_type.lower()}:{target_id}"
            f":{relationship_type}:{connection_type or '-'}"
        )

    @staticmethod
    def _graph_edge_label(relationship_type: str, row: dict[str, Any]) -> str:
        description = FrontendGraphService._as_string(row.get("description"))
        if description:
            return description
        if relationship_type == "ABOUT":
            return "About"
        if relationship_type == "AFFILIATED_WITH":
            return "Affiliated with"
        if relationship_type == "INVOLVED_IN":
            return "Involved in"
        connection_type = FrontendGraphService._as_string(row.get("connection_type"))
        return connection_type.replace("_", " ").strip().title()

    @staticmethod
    def _source_name(url: str | None) -> str:
        if not url:
            return "Unknown source"
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        if not hostname:
            return "Unknown source"
        parts = hostname.split(".")
        return (
            parts[-2].replace("-", " ").title() if len(parts) >= 2 else hostname.title()
        )

    @staticmethod
    def _source_tier(source: Source | None, enrichment: EventEnrichment | None) -> str:
        if enrichment is not None and enrichment.source_tier in {
            "tier-1",
            "tier-2",
            "tier-3",
        }:
            return enrichment.source_tier
        credibility = source.credibility if source is not None else None
        if credibility is None:
            return "tier-3"
        if credibility >= 0.8:
            return "tier-1"
        if credibility >= 0.5:
            return "tier-2"
        return "tier-3"

    @staticmethod
    def _article_sentiment(event: Event, enrichment: EventEnrichment | None) -> float:
        if enrichment is not None:
            return float(enrichment.sentiment)
        return max(-1.0, min(1.0, -float(event.risk_level) / 10.0))

    @staticmethod
    def _article_impact(event: Event, enrichment: EventEnrichment | None) -> float:
        if enrichment is not None:
            return float(enrichment.impact)
        return -float(event.risk_level)

    @staticmethod
    def _article_excerpt(
        event: Event, source: Source | None, enrichment: EventEnrichment | None
    ) -> str:
        if enrichment is not None and enrichment.excerpt:
            return enrichment.excerpt
        if source is not None and source.content:
            return source.content[:400]
        if event.source_text_quote:
            return event.source_text_quote
        return event.title

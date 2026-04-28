"""Frontend graph API bridge for the company graph dashboard."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from eem.database.models import EventEnrichment, FirmScore
from tarkov.config import Config
from tarkov.database.models import Event, Firm, Source
from tarkov.database.session import get_neo4j_driver, get_neo4j_session, init_neo4j


_LEGAL_SUFFIX_RE = re.compile(
    r"\s+(s\.?a\.?|sp\.?\s+z\s+o\.?o\.?|ltd\.?|ag|gmbh|inc\.?|llc|plc)\s*$",
    re.IGNORECASE,
)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass(slots=True)
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

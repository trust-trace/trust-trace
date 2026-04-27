"""Main orchestration layer for Stage 2 processing."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from tarkov.config import Config
from tarkov.database.models import ConnectionEntity
from tarkov.database.repositories.event_repo import EventRepository
from tarkov.database.repositories.firm_repo import FirmRepository
from tarkov.database.repositories.person_repo import PersonRepository
from tarkov.database.repositories.source_repo import SourceRepository
from tarkov.extraction.company_matcher import CompanyMatcher
from tarkov.extraction.connection_extractor import ConnectionExtractor
from tarkov.extraction.event_extractor import EventExtractor
from tarkov.extraction.person_extractor import PersonExtractor
from tarkov.extraction.summary_generator import SummaryGenerator
from tarkov.llm.client import LLMClient
from tarkov.pipeline.result_emitter import ResultEmitter
from tarkov.schemas.article import ArticleIn
from tarkov.schemas.parsed_result import ParsedResult
from tarkov.utils.logger import get_logger


logger = get_logger(__name__)


class ArticleProcessor:
    def __init__(self, db_session: Session, config: Config, result_emitter: ResultEmitter | None = None):
        self.db_session = db_session
        self.config = config
        self.firm_repo = FirmRepository(db_session)
        self.event_repo = EventRepository(db_session)
        self.person_repo = PersonRepository(db_session)
        self.source_repo = SourceRepository(db_session)

        self.llm_client = LLMClient(config.llm_provider, config.llm_model, config.llm_api_key)
        self.summary_generator = SummaryGenerator(self.llm_client)
        self.company_matcher = CompanyMatcher(db_session, config.company_reference_path)
        self.event_extractor = EventExtractor(llm_client=self.llm_client)
        self.person_extractor = PersonExtractor(llm_client=self.llm_client)
        self.connection_extractor = ConnectionExtractor()
        self.result_emitter = result_emitter or ResultEmitter()

    def process_article(self, article: ArticleIn, correlation_id: str | None = None) -> ParsedResult | None:
        correlation_id = correlation_id or str(uuid.uuid4())
        try:
            summary = self.summary_generator.generate_article_summary(article.article.text)

            company_matches = self.company_matcher.match_companies(article.article.text)
            if not company_matches:
                logger.warning("No companies found in article: %s", article.article.title)
                return None

            firms = [self.company_matcher.get_or_create_firm(m.company_name, m.ticker) for m in company_matches]
            events = self.event_extractor.extract_events_keyword_based(article)
            people = self.person_extractor.extract_people(article, [e.description for e in events])

            connections = self.connection_extractor.extract_business_relationships(article, [f.full_name for f in firms])
            connections.extend(self.connection_extractor.extract_shared_directors(article, people))
            connections.extend(self.connection_extractor.extract_activity_links(article, events))

            for firm in firms:
                for extracted in events:
                    event_out = self.event_extractor.to_event_out(extracted)
                    db_event = self.event_repo.create_event(firm.id, event_out)
                    self.source_repo.create_source_from_article(db_event.unique_id, article, summary)
                    self.source_repo.create_source_with_excerpt(db_event.unique_id, extracted)

                    for person in people:
                        db_person = self.person_repo.get_or_create_person(person.name, firm.id, person.role)
                        self.person_repo.link_person_to_event(db_person.id, db_event.unique_id, person.role, person.confidence)

                    for conn in connections:
                        self.db_session.add(
                            ConnectionEntity(
                                connection_event_id=db_event.unique_id,
                                connection_type=conn.connection_type,
                                entity_1_type=conn.entity_1_type,
                                entity_1_id=conn.entity_1_id,
                                entity_1_name=conn.entity_1_name,
                                entity_2_type=conn.entity_2_type,
                                entity_2_id=conn.entity_2_id,
                                entity_2_name=conn.entity_2_name,
                                relationship_description=conn.relationship_description,
                                confidence=conn.confidence,
                            )
                        )

                        # Create graph connection in Neo4j
                        try:
                            from tarkov.database.session import get_neo4j_session

                            with get_neo4j_session() as g:
                                q = (
                                    "MATCH (a), (b) WHERE (a.company_id = $id1 OR a.person_id = $id1) AND (b.company_id = $id2 OR b.person_id = $id2) "
                                    "CREATE (a)-[r:CONNECTION {type: $type, intensity: $intensity, description: $desc, source_event_id: $eid}]->(b)"
                                )
                                g.run(
                                    q,
                                    id1=int(conn.entity_1_id) if conn.entity_1_id.isdigit() else conn.entity_1_id,
                                    id2=int(conn.entity_2_id) if conn.entity_2_id.isdigit() else conn.entity_2_id,
                                    type=conn.connection_type,
                                    intensity=conn.intensity or conn.confidence or 0.0,
                                    desc=conn.relationship_description,
                                    eid=db_event.unique_id,
                                )
                        except Exception:
                            pass

            parsed = ParsedResult(
                article_id=str(uuid.uuid4()),
                processed_at=datetime.utcnow(),
                llm_summary=summary,
                events=events,
                people=people,
                connections=connections,
                company_matches=[str(f.id) for f in firms],
                language=article.article.language,
                total_risk_score=(sum(e.risk_level for e in events) / len(events)) if events else 0.0,
            )

            self.result_emitter.emit(parsed, correlation_id)
            self.db_session.commit()
            logger.info("Processed article: %s", article.article.title)
            return parsed
        except Exception as exc:
            logger.exception("Error processing article: %s", exc)
            self.db_session.rollback()
            self._write_dead_letter(article, correlation_id, str(exc))
            raise

    def process_articles_batch(self, articles: list[ArticleIn]) -> list[ParsedResult]:
        out: list[ParsedResult] = []
        for article in articles:
            result = self.process_article(article)
            if result is not None:
                out.append(result)
        return out

    def process_articles_stream(self, article_iterator):
        for article in article_iterator:
            self.process_article(article)

    def _write_dead_letter(self, article: ArticleIn, correlation_id: str, error_message: str) -> None:
        payload = {
            "correlation_id": correlation_id,
            "error": error_message,
            "source_url": article.source.url,
            "title": article.article.title,
            "timestamp": datetime.utcnow().isoformat(),
        }
        path = Path(self.config.dead_letter_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")

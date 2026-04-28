"""Main orchestration layer for Stage 2 processing.

Tarkov is responsible for:
- Creating Postgres records (events, firms, people, sources, metadata)
- Creating standalone Neo4j nodes (Company, Person, Event)

Connection extraction is persisted as connection events, but no node edges
are created yet. Relationship analysis remains downstream.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from tarkov.config import Config
from tarkov.database.repositories.article_metadata_repo import ArticleMetadataRepository
from tarkov.database.repositories.event_repo import EventRepository
from tarkov.database.repositories.firm_repo import FirmRepository
from tarkov.database.models import ConnectionEntity
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
        self.article_metadata_repo = ArticleMetadataRepository(db_session)

        self.llm_client = LLMClient(
            config.llm_provider,
            config.llm_model,
            config.llm_api_key,
            openrouter_base_url=config.openrouter_base_url,
            openrouter_http_referer=config.openrouter_http_referer,
            openrouter_x_title=config.openrouter_x_title,
            web_search_enabled=config.llm_web_search_enabled,
        )
        self.summary_generator = SummaryGenerator(self.llm_client)
        self.company_matcher = CompanyMatcher(db_session, config.company_reference_path, llm_client=self.llm_client)
        self.event_extractor = EventExtractor(llm_client=self.llm_client)
        self.person_extractor = PersonExtractor(llm_client=self.llm_client)
        self.connection_extractor = ConnectionExtractor(llm_client=self.llm_client)
        self.result_emitter = result_emitter or ResultEmitter()

    def process_article(self, article: ArticleIn, correlation_id: str | None = None) -> ParsedResult | None:
        correlation_id = correlation_id or str(uuid.uuid4())
        article_id = str(uuid.uuid4())
        print(f"\n{'='*60}")
        print(f"[PROCESSOR] article_id : {article_id}")
        print(f"[PROCESSOR] title      : {article.article.title}")
        print(f"[PROCESSOR] source     : {article.source.url}")
        print(f"[PROCESSOR] text[:200] : {article.article.text[:200]}")
        try:
            self.article_metadata_repo.create_ingestion_record(article_id, correlation_id, article)
            summary = self.summary_generator.generate_article_summary(article.article.text)
            print(f"[PROCESSOR] summary    : {str(summary)[:150]!r}")

            company_matches = self.company_matcher.match_companies(article.article.text)
            print(f"[PROCESSOR] companies  : {[m.company_name for m in company_matches]}")
            if not company_matches:
                logger.warning("No companies found in article: %s", article.article.title)
                self.article_metadata_repo.mark_processed(article_id=article_id, companies_found=0)
                self.db_session.commit()
                print("[PROCESSOR] -> skipped (no company matches)")
                return None

            firms = []
            for match in company_matches:
                firm = self.company_matcher.get_or_create_firm(match.company_name, match.ticker)
                self.company_matcher.enrich_firm_profile(firm, article.article.text)
                firms.append(firm)
            print(f"[PROCESSOR] firms      : {[(f.id, f.full_name) for f in firms]}")
            events = self.event_extractor.extract_events_keyword_based(article)
            print(f"[PROCESSOR] events     : {[(e.event_type, e.risk_level) for e in events]}")
            people = self.person_extractor.extract_people(article, [e.description for e in events])
            print(f"[PROCESSOR] people     : {[p.name for p in people]}")

            connection_payloads = self.connection_extractor.extract_connections(
                article,
                [f.full_name for f in firms],
                people,
                events,
            )
            print(
                f"[PROCESSOR] connections: {[(c.connection_type, c.entity_1_name, '->', c.entity_2_name) for c in connection_payloads]}"
            )

            connection_events = [
                self.connection_extractor.to_event_extraction(payload, article, firms[0].full_name)
                for payload in connection_payloads
            ]

            for firm in firms:
                for extracted in events:
                    event_out = self.event_extractor.to_event_out(extracted)
                    db_event = self.event_repo.create_event(firm.id, event_out)
                    print(f"[PROCESSOR]   PG event {db_event.unique_id} ({db_event.event_type}) risk={db_event.risk_level} -> firm '{firm.full_name}'")
                    self.source_repo.create_source_from_article(db_event.unique_id, article, summary)
                    self.source_repo.create_source_with_excerpt(db_event.unique_id, extracted)

                    for person in people:
                        db_person = self.person_repo.get_or_create_person(person.name, firm.id, person.role)
                        self.person_repo.link_person_to_event(db_person.id, db_event.unique_id, person.role, person.confidence)
                        print(f"[PROCESSOR]   PG person '{person.name}' (id={db_person.id}) linked to event")

            if connection_payloads:
                anchor_firm = firms[0]
                for payload, connection_event in zip(connection_payloads, connection_events):
                    event_out = self.connection_extractor.to_event_out(payload, article, anchor_firm.full_name)
                    db_event = self.event_repo.create_event(anchor_firm.id, event_out, event_category="connection")
                    print(
                        f"[PROCESSOR]   PG connection event {db_event.unique_id} ({db_event.event_type}) "
                        f"risk={db_event.risk_level} -> firm '{anchor_firm.full_name}'"
                    )
                    self.source_repo.create_source_from_article(db_event.unique_id, article, summary)
                    self.source_repo.create_source_with_excerpt(db_event.unique_id, connection_event)
                    self.db_session.add(
                        ConnectionEntity(
                            connection_event_id=db_event.unique_id,
                            connection_type=payload.connection_type,
                            entity_1_type=payload.entity_1_type,
                            entity_1_id=payload.entity_1_id,
                            entity_1_name=payload.entity_1_name,
                            entity_2_type=payload.entity_2_type,
                            entity_2_id=payload.entity_2_id,
                            entity_2_name=payload.entity_2_name,
                            relationship_description=payload.relationship_description,
                            confidence=payload.confidence,
                        )
                    )
                    print(
                        f"[PROCESSOR]   PG connection payload {payload.connection_type}: "
                        f"'{payload.entity_1_name}' -> '{payload.entity_2_name}'"
                    )

            parsed = ParsedResult(
                article_id=article_id,
                processed_at=datetime.utcnow(),
                llm_summary=summary,
                events=[*events, *connection_events],
                people=people,
                company_matches=[str(f.id) for f in firms],
                firm_ids=[f.id for f in firms],
                language=article.article.language,
                total_risk_score=(sum(e.risk_level for e in events) / len(events)) if events else 0.0,
            )

            self.article_metadata_repo.mark_processed(article_id=article_id, companies_found=len(firms))
            self.db_session.commit()
            self.result_emitter.emit(parsed, correlation_id)
            logger.info("Processed article: %s", article.article.title)
            print(f"[PROCESSOR] DONE  total_risk={parsed.total_risk_score:.2f}  events={len(events)}  people={len(people)}")
            print(f"{'='*60}\n")
            return parsed
        except Exception as exc:
            logger.exception("Error processing article: %s", exc)
            print(f"[PROCESSOR] ERROR: {exc}")
            self.db_session.rollback()
            self._write_dead_letter(article, correlation_id, article_id, str(exc))
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

    def _write_dead_letter(self, article: ArticleIn, correlation_id: str, article_id: str, error_message: str) -> None:
        payload = {
            "correlation_id": correlation_id,
            "article_id": article_id,
            "error": error_message,
            "source_url": article.source.url,
            "title": article.article.title,
            "timestamp": datetime.utcnow().isoformat(),
        }
        path = Path(self.config.dead_letter_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")

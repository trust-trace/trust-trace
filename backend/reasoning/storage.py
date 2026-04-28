"""Database persistence utilities for reasoning traces."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from reasoning.models import ReasoningTraceModel
from reasoning.schemas import ReasoningTraceStorageModel

logger = logging.getLogger(__name__)


class ReasoningTraceRepository:
    """Repository for CRUD operations on reasoning traces."""

    def __init__(self, db: Session) -> None:
        """Initialize repository with a database session."""
        self._db = db

    def save(
        self,
        classifier_name: str,
        entity_type: str,
        entity_id: str,
        trace_data: dict,
        correlation_id: Optional[str] = None,
    ) -> int:
        """Save a reasoning trace to the database.

        Args:
            classifier_name: Name of the classifier (e.g., "EEM", "NSA", "RKR")
            entity_type: Type of entity being traced (e.g., "event", "person", "article")
            entity_id: ID of the entity being traced
            trace_data: Domain-specific trace data as dict
            correlation_id: Optional correlation ID linking to parent event/article

        Returns:
            The ID of the saved reasoning trace record.
        """
        trace_json = json.dumps(trace_data, ensure_ascii=False, default=str)

        model = ReasoningTraceModel(
            classifier_name=classifier_name,
            entity_type=entity_type,
            entity_id=entity_id,
            correlation_id=correlation_id,
            trace_data=trace_json,
            created_at=datetime.utcnow(),
        )
        self._db.add(model)
        self._db.flush()
        return model.id

    def get_by_id(self, trace_id: int) -> Optional[ReasoningTraceStorageModel]:
        """Retrieve a reasoning trace by ID.

        Args:
            trace_id: The ID of the reasoning trace to retrieve

        Returns:
            ReasoningTraceStorageModel if found, None otherwise.
        """
        model = self._db.execute(
            select(ReasoningTraceModel).where(ReasoningTraceModel.id == trace_id)
        ).scalar_one_or_none()

        if model is None:
            return None

        return self._model_to_storage(model)

    def get_by_entity_id(self, entity_id: str) -> list[ReasoningTraceStorageModel]:
        """Retrieve all reasoning traces for a specific entity.

        Args:
            entity_id: The ID of the entity (event_id, person_id, article_id, etc.)

        Returns:
            List of matching ReasoningTraceStorageModel records.
        """
        models = self._db.execute(
            select(ReasoningTraceModel).where(ReasoningTraceModel.entity_id == entity_id)
        ).scalars()

        return [self._model_to_storage(m) for m in models]

    def get_by_correlation_id(
        self, correlation_id: str
    ) -> list[ReasoningTraceStorageModel]:
        """Retrieve all reasoning traces linked to a correlation ID.

        Args:
            correlation_id: The correlation ID (links to parent event/article)

        Returns:
            List of matching ReasoningTraceStorageModel records.
        """
        models = self._db.execute(
            select(ReasoningTraceModel).where(
                ReasoningTraceModel.correlation_id == correlation_id
            )
        ).scalars()

        return [self._model_to_storage(m) for m in models]

    def get_by_classifier(
        self, classifier_name: str, limit: int = 100, offset: int = 0
    ) -> list[ReasoningTraceStorageModel]:
        """Retrieve reasoning traces by classifier name.

        Args:
            classifier_name: Name of the classifier (e.g., "EEM", "NSA", "RKR")
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of matching ReasoningTraceStorageModel records.
        """
        models = self._db.execute(
            select(ReasoningTraceModel)
            .where(ReasoningTraceModel.classifier_name == classifier_name)
            .order_by(ReasoningTraceModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars()

        return [self._model_to_storage(m) for m in models]

    def get_by_classifier_and_entity_id(
        self, classifier_name: str, entity_id: str
    ) -> list[ReasoningTraceStorageModel]:
        """Retrieve reasoning traces by classifier and entity ID.

        Args:
            classifier_name: Name of the classifier (e.g., "EEM", "NSA", "Tarkov")
            entity_id: The ID of the entity being traced

        Returns:
            List of matching ReasoningTraceStorageModel records.
        """
        models = self._db.execute(
            select(ReasoningTraceModel)
            .where(
                (ReasoningTraceModel.classifier_name == classifier_name)
                & (ReasoningTraceModel.entity_id == entity_id)
            )
            .order_by(ReasoningTraceModel.created_at.desc())
        ).scalars()

        return [self._model_to_storage(m) for m in models]

    def get_by_classifier_and_entity_type(
        self, classifier_name: str, entity_type: str, limit: int = 100, offset: int = 0
    ) -> list[ReasoningTraceStorageModel]:
        """Retrieve reasoning traces by classifier and entity type.

        Args:
            classifier_name: Name of the classifier
            entity_type: Type of entity being traced
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of matching ReasoningTraceStorageModel records.
        """
        models = self._db.execute(
            select(ReasoningTraceModel)
            .where(
                (ReasoningTraceModel.classifier_name == classifier_name)
                & (ReasoningTraceModel.entity_type == entity_type)
            )
            .order_by(ReasoningTraceModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars()

        return [self._model_to_storage(m) for m in models]

    def delete_by_id(self, trace_id: int) -> bool:
        """Delete a reasoning trace by ID.

        Args:
            trace_id: The ID of the reasoning trace to delete

        Returns:
            True if a record was deleted, False otherwise.
        """
        result = self._db.execute(
            select(ReasoningTraceModel).where(ReasoningTraceModel.id == trace_id)
        ).scalar_one_or_none()

        if result is None:
            return False

        self._db.delete(result)
        self._db.flush()
        return True

    def delete_old_traces(self, days_old: int = 90) -> int:
        """Delete reasoning traces older than the specified number of days.

        Args:
            days_old: Number of days to retain (default: 90)

        Returns:
            Number of records deleted.
        """
        cutoff = datetime.utcnow()
        from datetime import timedelta

        cutoff = cutoff - timedelta(days=days_old)

        result = self._db.execute(
            select(ReasoningTraceModel).where(ReasoningTraceModel.created_at < cutoff)
        ).scalars()

        count = 0
        for model in result:
            self._db.delete(model)
            count += 1

        self._db.flush()
        return count

    @staticmethod
    def _model_to_storage(model: ReasoningTraceModel) -> ReasoningTraceStorageModel:
        """Convert a database model to a storage model."""
        trace_data = json.loads(model.trace_data) if model.trace_data else {}

        return ReasoningTraceStorageModel(
            classifier_name=model.classifier_name,
            entity_type=model.entity_type,
            entity_id=model.entity_id,
            correlation_id=model.correlation_id,
            trace_data=trace_data,
            created_at=model.created_at,
        )

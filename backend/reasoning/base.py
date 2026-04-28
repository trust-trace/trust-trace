"""Abstract base classes for reasoning trace collectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from reasoning.schemas import ReasoningTraceData


class ReasoningTraceCollector(ABC):
    """Abstract base class for all reasoning trace collectors.

    Subclasses should implement this interface to collect domain-specific
    reasoning data during classifier execution, and provide a `collect()`
    method that returns the domain-specific trace object.
    """

    @abstractmethod
    def collect(self) -> ReasoningTraceData:
        """Collect and return the reasoning trace.

        Returns:
            A domain-specific reasoning trace object (one of the ReasoningTraceData union types).
        """
        pass


class TraceCollectorRegistry:
    """Registry for associating classifier names with their collectors.

    Useful for dynamically instantiating the correct collector based on
    classifier name.
    """

    _collectors: dict[str, type[ReasoningTraceCollector]] = {}

    @classmethod
    def register(cls, classifier_name: str) -> callable:
        """Decorator for registering a collector class.

        Usage:
            @TraceCollectorRegistry.register("EEM")
            class EEMTraceCollector(ReasoningTraceCollector):
                pass
        """

        def decorator(collector_cls: type[ReasoningTraceCollector]) -> type[ReasoningTraceCollector]:
            cls._collectors[classifier_name] = collector_cls
            return collector_cls

        return decorator

    @classmethod
    def get_collector(cls, classifier_name: str) -> type[ReasoningTraceCollector] | None:
        """Get a registered collector class by classifier name."""
        return cls._collectors.get(classifier_name)

    @classmethod
    def list_registered(cls) -> list[str]:
        """List all registered classifier names."""
        return list(cls._collectors.keys())

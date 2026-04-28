"""Reasoning traces module for capturing classifier decision-making logic."""

from reasoning.base import ReasoningTraceCollector, TraceCollectorRegistry
from reasoning.formatters import (
    format_trace_compact,
    format_trace_csv_header,
    format_trace_detailed,
    format_trace_pretty,
)
from reasoning.models import ReasoningTraceModel
from reasoning.schemas import (
    EEMReasoningTrace,
    MarketReasoningTrace,
    NSAReasoningTrace,
    ReasoningTraceStorageModel,
    TarkovReasoningTrace,
)
from reasoning.session import SessionLocal, create_all, get_db, get_engine, init_engine
from reasoning.storage import ReasoningTraceRepository

__all__ = [
    # Session management
    "init_engine",
    "get_engine",
    "create_all",
    "get_db",
    "SessionLocal",
    # Models
    "ReasoningTraceModel",
    # Schemas
    "ReasoningTraceStorageModel",
    "EEMReasoningTrace",
    "NSAReasoningTrace",
    "TarkovReasoningTrace",
    "MarketReasoningTrace",
    # Base classes
    "ReasoningTraceCollector",
    "TraceCollectorRegistry",
    # Storage
    "ReasoningTraceRepository",
    # Formatters
    "format_trace_compact",
    "format_trace_pretty",
    "format_trace_detailed",
    "format_trace_csv_header",
]

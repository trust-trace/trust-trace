"""Result event dispatcher."""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from typing import Any, Callable, Coroutine, cast

from tarkov.schemas.parsed_result import ParsedResult, ParsingEvent
from tarkov.utils.logger import get_logger


logger = get_logger(__name__)


class ResultEmitter:
    def __init__(self):
        self.handlers: list[Callable[[ParsingEvent], None]] = []
        self.async_handlers: list[Callable[[ParsingEvent], Coroutine[Any, Any, None]]] = []

    def register_handler(self, handler: Callable[[ParsingEvent], None]) -> None:
        self.handlers.append(handler)

    def register_async_handler(self, handler: Callable[[ParsingEvent], Coroutine[Any, Any, None]]) -> None:
        self.async_handlers.append(handler)

    def emit(self, parsed_result: ParsedResult, correlation_id: str) -> ParsingEvent:
        event = ParsingEvent(
            timestamp=datetime.utcnow(),
            parsed_result=parsed_result,
            firm_ids=list(parsed_result.firm_ids),
            correlation_id=correlation_id,
        )

        for handler in self.handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.exception("sync handler failed: %s", exc)

        for handler in self.async_handlers:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(cast(Coroutine[Any, Any, None], handler(event)))
            except RuntimeError:
                threading.Thread(target=self._run_async_handler, args=(handler, event), daemon=True).start()
            except Exception as exc:
                logger.exception("async handler failed: %s", exc)
        return event

    @staticmethod
    def _run_async_handler(handler: Callable[[ParsingEvent], Coroutine[Any, Any, None]], event: ParsingEvent) -> None:
        try:
            asyncio.run(cast(Coroutine[Any, Any, None], handler(event)))
        except Exception as exc:
            logger.exception("background async handler failed: %s", exc)

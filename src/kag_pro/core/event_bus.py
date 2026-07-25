"""Lightweight in-process event bus for inter-module communication.

Synchronous pub/sub — no asyncio, no external dependencies.
Modules subscribe to event types and receive published data as dicts.
"""

from collections import defaultdict
from collections.abc import Callable
from typing import Any


# Event type constants for type-safe referencing
class Events:
    """Canonical event type names."""

    QUERY_RECEIVED = "query.received"
    STAGE_DETECTED = "stage.detected"
    RETRIEVAL_COMPLETED = "retrieval.completed"
    RETRIEVAL_EMPTY = "retrieval.empty"
    RETRIEVAL_WEAK = "retrieval.weak"
    ANSWER_GENERATED = "answer.generated"
    ANSWER_VERIFIED = "answer.verified"
    ANSWER_REVISED = "answer.revised"
    ANSWER_CACHE_HIT = "answer.cache_hit"
    DIAGNOSIS_COMPLETED = "diagnosis.completed"
    ERROR_RECORDED = "error.recorded"
    RECOMMENDATION_READY = "recommendation.ready"
    DOCUMENTS_INDEXED = "documents.indexed"
    PAPER_GENERATED = "paper.generated"


class EventBus:
    """In-process pub/sub event bus."""

    def __init__(self):
        self._handlers: dict[str, list[Callable[[dict], Any]]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable[[dict], Any]) -> None:
        """Subscribe a handler to an event type."""
        self._handlers[event_type].append(handler)

    def publish(self, event_type: str, data: dict) -> None:
        """Publish an event to all subscribers. Synchronous."""
        for handler in self._handlers.get(event_type, []):
            handler(data)

    def unsubscribe(self, event_type: str, handler: Callable[[dict], Any]) -> None:
        """Remove a specific handler from an event type."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h is not handler
            ]

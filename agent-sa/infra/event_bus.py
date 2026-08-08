"""A minimal in-process publish/subscribe event bus.

Handlers publish Domain Events; infra listeners subscribe to react (audit
logging, writing output files, ...) without the handler knowing who's
listening, or how many listeners there are. This is the whole EDA mechanism
in this repo — no broker, no queue, just decoupling handlers from side effects.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, DefaultDict, List, Sequence, Type

from domain.events import DomainEvent

Listener = Callable[[DomainEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._listeners: DefaultDict[Type[DomainEvent], List[Listener]] = defaultdict(list)

    def subscribe(self, event_type: Type[DomainEvent], listener: Listener) -> None:
        self._listeners[event_type].append(listener)

    def publish(self, event: DomainEvent) -> None:
        for listener in self._listeners.get(type(event), []):
            listener(event)

    def publish_all(self, events: Sequence[DomainEvent]) -> None:
        for event in events:
            self.publish(event)

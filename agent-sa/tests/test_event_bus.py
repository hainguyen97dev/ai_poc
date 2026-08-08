"""Tests for infra/event_bus.py — the whole EDA mechanism in this repo."""

from __future__ import annotations

from domain.events import AnalysisBlocked, AnalysisCompleted
from domain.value_objects import AnalysisId


def _blocked(reason: str = "test") -> AnalysisBlocked:
    return AnalysisBlocked(AnalysisId("X-1"), reason=reason)


class TestEventBus:
    def test_publish_calls_subscribed_listener(self, event_bus):
        received = []
        event_bus.subscribe(AnalysisBlocked, received.append)
        event = _blocked()

        event_bus.publish(event)

        assert received == [event]

    def test_publish_ignores_listeners_of_other_event_types(self, event_bus):
        received = []
        event_bus.subscribe(AnalysisCompleted, received.append)

        event_bus.publish(_blocked())

        assert received == []

    def test_multiple_listeners_for_same_type_all_called_in_order(self, event_bus):
        calls = []
        event_bus.subscribe(AnalysisBlocked, lambda e: calls.append("first"))
        event_bus.subscribe(AnalysisBlocked, lambda e: calls.append("second"))

        event_bus.publish(_blocked())

        assert calls == ["first", "second"]

    def test_publish_all_publishes_every_event_in_order(self, event_bus):
        calls = []
        event_bus.subscribe(AnalysisBlocked, lambda e: calls.append(e.reason))

        event_bus.publish_all([_blocked("first"), _blocked("second")])

        assert calls == ["first", "second"]

    def test_publish_with_no_subscribers_does_not_raise(self, event_bus):
        event_bus.publish(_blocked())  # no assertion needed — just must not raise

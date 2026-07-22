"""Tests for EventBus — synchronous pub/sub."""

from kag_pro.core.event_bus import EventBus, Events


class TestEventBus:

    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe("test.event", lambda data: received.append(data))
        bus.publish("test.event", {"value": 1})
        assert received == [{"value": 1}]

    def test_multiple_handlers_invoked_in_order(self):
        bus = EventBus()
        order = []
        bus.subscribe("e", lambda d: order.append("first"))
        bus.subscribe("e", lambda d: order.append("second"))
        bus.publish("e", {})
        assert order == ["first", "second"]

    def test_publish_no_subscribers_is_noop(self):
        bus = EventBus()
        # Should not raise even though nobody subscribed
        bus.publish("nobody.listening", {"x": 1})

    def test_handlers_isolated_per_event_type(self):
        bus = EventBus()
        a_received = []
        b_received = []
        bus.subscribe("a", lambda d: a_received.append(d))
        bus.subscribe("b", lambda d: b_received.append(d))
        bus.publish("a", {"n": 1})
        assert a_received == [{"n": 1}]
        assert b_received == []

    def test_unsubscribe(self):
        bus = EventBus()
        received = []

        def handler(data):
            received.append(data)

        bus.subscribe("e", handler)
        bus.publish("e", {"n": 1})
        bus.unsubscribe("e", handler)
        bus.publish("e", {"n": 2})
        assert received == [{"n": 1}]

    def test_unsubscribe_unknown_event_is_safe(self):
        bus = EventBus()
        # Unsubscribing from an event with no handlers should not raise
        bus.unsubscribe("never.subscribed", lambda d: None)

    def test_data_payload_passed_through(self):
        bus = EventBus()
        captured = {}
        bus.subscribe(Events.QUERY_RECEIVED, lambda d: captured.update(d))
        bus.publish(Events.QUERY_RECEIVED, {"question": "什么是分数？"})
        assert captured["question"] == "什么是分数？"

    def test_events_constants_are_unique(self):
        names = [
            Events.QUERY_RECEIVED,
            Events.STAGE_DETECTED,
            Events.RETRIEVAL_COMPLETED,
            Events.RETRIEVAL_EMPTY,
            Events.ANSWER_GENERATED,
            Events.ANSWER_VERIFIED,
            Events.DIAGNOSIS_COMPLETED,
            Events.ERROR_RECORDED,
            Events.RECOMMENDATION_READY,
            Events.DOCUMENTS_INDEXED,
            Events.PAPER_GENERATED,
        ]
        assert len(names) == len(set(names))

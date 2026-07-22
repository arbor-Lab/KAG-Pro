"""Tests for PluginRegistry — service registration and resolution."""

import pytest

from kag_pro.core.registry import PluginRegistry


class TestPluginRegistry:

    def test_register_and_resolve_instance(self):
        registry = PluginRegistry()
        obj = {"key": "value"}
        registry.register("config", obj)
        assert registry.resolve("config") is obj

    def test_register_factory_lazy_singleton(self):
        registry = PluginRegistry()
        calls = {"count": 0}

        def factory():
            calls["count"] += 1
            return object()

        registry.register("service", factory)
        # Factory not called until first resolve
        assert calls["count"] == 0

        first = registry.resolve("service")
        assert calls["count"] == 1

        # Second resolve returns the same singleton without re-calling factory
        second = registry.resolve("service")
        assert calls["count"] == 1
        assert first is second

    def test_register_class_stored_as_instance(self):
        """A class is a callable but also a type, so it is stored directly
        (not invoked as a factory)."""
        registry = PluginRegistry()

        class Dummy:
            pass

        registry.register("dummy", Dummy)
        resolved = registry.resolve("dummy")
        assert resolved is Dummy  # class object itself, not an instance

    def test_resolve_unknown_raises_keyerror(self):
        registry = PluginRegistry()
        with pytest.raises(KeyError):
            registry.resolve("does-not-exist")

    def test_has(self):
        registry = PluginRegistry()
        assert not registry.has("x")
        registry.register("x", 123)
        assert registry.has("x")

    def test_has_covers_unresolved_factory(self):
        registry = PluginRegistry()
        registry.register("lazy", lambda: 42)
        # has() is true even before the factory has been resolved
        assert registry.has("lazy")

    def test_list_services(self):
        registry = PluginRegistry()
        registry.register("a", 1)
        registry.register("b", lambda: 2)
        services = registry.list_services()
        assert services == ["a", "b"]

    def test_list_services_no_duplicates_after_resolve(self):
        registry = PluginRegistry()
        registry.register("svc", lambda: object())
        registry.resolve("svc")  # promotes factory result into _instances
        # "svc" should appear only once even though it lives in both maps
        assert registry.list_services().count("svc") == 1

    def test_reregister_overrides(self):
        registry = PluginRegistry()
        registry.register("x", 1)
        registry.register("x", 2)
        assert registry.resolve("x") == 2

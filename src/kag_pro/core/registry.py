"""Lightweight service registry for dependency injection.

A simple dict-based container — no external framework, no magic.
Supports both direct instance registration and lazy factory (singleton) registration.
"""

from collections.abc import Callable
from typing import Any


class PluginRegistry:
    """Dict-based service registry for pluggable module management."""

    def __init__(self):
        self._instances: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}

    def register(self, name: str, instance_or_factory: Any) -> None:
        """Register a service instance or a lazy factory.

        If the value is a callable (but not a class/type), it is treated as
        a lazy factory that will be called on first resolve (singleton pattern).
        Otherwise, the value is stored directly as the instance.
        """
        if callable(instance_or_factory) and not isinstance(instance_or_factory, type):
            self._factories[name] = instance_or_factory
        else:
            self._instances[name] = instance_or_factory

    def resolve(self, name: str) -> Any:
        """Resolve a service by name. Creates singleton on first factory call."""
        if name in self._instances:
            return self._instances[name]
        if name in self._factories:
            instance = self._factories[name]()
            self._instances[name] = instance
            return instance
        raise KeyError(f"Service not registered: {name}")

    def has(self, name: str) -> bool:
        """Check if a service is registered."""
        return name in self._instances or name in self._factories

    def list_services(self) -> list[str]:
        """Return all registered service names."""
        return sorted(set(list(self._instances.keys()) + list(self._factories.keys())))

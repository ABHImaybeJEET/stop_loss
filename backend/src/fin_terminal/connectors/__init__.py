"""Connector interfaces. Provider imports are lazy to avoid dependency cycles."""

from fin_terminal.config import Settings
from fin_terminal.connectors.base import AsyncConnector


def create_connectors(settings: Settings, *, live: bool = False) -> dict[str, AsyncConnector]:
    from fin_terminal.connectors.factory import create_connectors as factory

    return factory(settings, live=live)


__all__ = ["AsyncConnector", "create_connectors"]

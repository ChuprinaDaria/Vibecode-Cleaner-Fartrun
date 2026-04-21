"""Plugin base class for dev-monitor."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite
    from textual.widget import Widget


@dataclass
class Alert:
    source: str
    severity: str  # "critical", "high", "warning", "info"
    title: str
    message: str


class Plugin(abc.ABC):
    """Every plugin implements this interface."""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def icon(self) -> str: ...

    @abc.abstractmethod
    async def migrate(self, db: aiosqlite.Connection) -> None:
        """Create plugin-specific tables."""

    @abc.abstractmethod
    async def collect(self, db: aiosqlite.Connection) -> None:
        """Gather metrics. Called every refresh_interval."""

    @abc.abstractmethod
    def render(self) -> Widget:
        """Return Textual widget for plugin tab."""

    @abc.abstractmethod
    async def get_alerts(self, db: aiosqlite.Connection) -> list[Alert]:
        """Check thresholds and return alerts."""

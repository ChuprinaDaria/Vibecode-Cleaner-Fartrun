"""SQLite database manager for dev-monitor plugins."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Callable, Awaitable

import aiosqlite


class Database:
    """Async SQLite wrapper with migration support."""

    def __init__(self, path: Path | str):
        self._path = Path(path)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def run_migration(self, migrate_fn: Callable[[aiosqlite.Connection], Awaitable[None]]) -> None:
        if not self._conn:
            raise RuntimeError("Database not connected")
        await migrate_fn(self._conn)
        await self._conn.commit()

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        if not self._conn:
            raise RuntimeError("Database not connected")
        yield self._conn

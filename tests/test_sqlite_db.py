"""Tests for SQLite database manager."""

import pytest
import asyncio
from core.sqlite_db import Database


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_monitor.db"
    return Database(db_path)


@pytest.mark.asyncio
async def test_connect_and_close(db):
    await db.connect()
    assert db._conn is not None
    await db.close()


@pytest.mark.asyncio
async def test_run_migration(db):
    await db.connect()

    async def migrate(conn):
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)

    await db.run_migration(migrate)

    async with db.connection() as conn:
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "test_table"

    await db.close()


@pytest.mark.asyncio
async def test_connection_context_manager(db):
    await db.connect()

    async def migrate(conn):
        await conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, val TEXT)")

    await db.run_migration(migrate)

    async with db.connection() as conn:
        await conn.execute("INSERT INTO items (val) VALUES (?)", ("hello",))
        await conn.commit()

    async with db.connection() as conn:
        cursor = await conn.execute("SELECT val FROM items")
        row = await cursor.fetchone()
        assert row[0] == "hello"

    await db.close()

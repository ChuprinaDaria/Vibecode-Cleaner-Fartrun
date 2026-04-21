"""Shared test fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / "test_monitor.db"

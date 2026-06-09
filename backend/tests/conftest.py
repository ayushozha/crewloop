"""Test bootstrap: provide the required env vars before app.config imports.

The config intentionally has no defaults for secrets (DATABASE_URL is
required so a missing env fails fast instead of silently using a leaked
fallback). Tests run without a database — they only exercise pure logic.
"""
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("AGENTPHONE_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgres://test:test@localhost:5432/test")
os.environ.setdefault("APP_PASSWORD", "")
os.environ.setdefault("DEMO_MODE", "false")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def anyio_backend():
    # asyncio only — trio is not a dependency of this project.
    return "asyncio"

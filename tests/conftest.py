"""
Pytest configuration and shared async fixtures.
"""
import asyncio
import pytest
import pytest_asyncio


# ── Make all async tests use the same event loop ─────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Shared mock fixtures ──────────────────────────────────────────────────────
@pytest.fixture
def mock_redis(mocker):
    """Mock async Redis client."""
    redis_mock = mocker.AsyncMock()
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.incr.return_value  = 1
    redis_mock.expire.return_value = True
    return redis_mock


@pytest.fixture
def mock_db_session(mocker):
    """Mock async SQLAlchemy session."""
    session_mock = mocker.AsyncMock()
    session_mock.commit.return_value  = None
    session_mock.rollback.return_value = None
    session_mock.add.return_value     = None
    return session_mock

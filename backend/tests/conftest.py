import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.deps import get_image_repo
from app.repository.dynamo_image_repo import DynamoImageRepository


def make_mock_repo() -> DynamoImageRepository:
    """
    Returns a MagicMock that satisfies DynamoImageRepository's async interface.
    Every method that image_service / router awaits must be an AsyncMock.
    """
    repo = MagicMock(spec=DynamoImageRepository)
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.update_status = AsyncMock()
    repo.list_by_status = AsyncMock(return_value={"items": [], "last_key": None})
    repo.list_all = AsyncMock(return_value=[])
    return repo


@pytest_asyncio.fixture
async def mock_repo() -> DynamoImageRepository:
    """Bare mock repo — tests can customise return values as needed."""
    return make_mock_repo()


@pytest_asyncio.fixture
async def client(mock_repo):
    """
    AsyncClient with get_image_repo overridden to use the mock repo.
    Replaces the old fixture that overrode get_db with a SQLite session.
    """
    app.dependency_overrides[get_image_repo] = lambda: mock_repo

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
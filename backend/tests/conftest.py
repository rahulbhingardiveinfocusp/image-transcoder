import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.deps import get_image_repo
from app.repository.dynamo_image_repo import DynamoImageRepository


def make_mock_repo() -> DynamoImageRepository:
    repo = MagicMock(spec=DynamoImageRepository)

    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.update_status = AsyncMock()
    repo.list_by_status = AsyncMock(return_value={"items": [], "last_key": None})
    repo.list_all = AsyncMock(return_value=[])

    return repo


# -----------------------
# FIXED MOCK REPO
# -----------------------

@pytest.fixture
def mock_repo():
    return make_mock_repo()


# -----------------------
# FIXED CLIENT
# -----------------------

@pytest_asyncio.fixture
async def client(mock_repo):
    app.dependency_overrides[get_image_repo] = lambda: mock_repo

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
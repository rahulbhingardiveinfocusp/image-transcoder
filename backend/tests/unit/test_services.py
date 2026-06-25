import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.image_service import ImageService
from app.repository.dynamo_image_repo import DynamoImageRepository


# ---------------------------------------------------------------------------
# MOCK REPO
# ---------------------------------------------------------------------------

def make_mock_repo(**overrides) -> DynamoImageRepository:
    repo = MagicMock(spec=DynamoImageRepository)

    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.update_status = AsyncMock()
    repo.list_by_status = AsyncMock(return_value={"items": [], "last_key": None})

    repo.list_by_user = AsyncMock(return_value=[])

    for k, v in overrides.items():
        setattr(repo, k, v)

    return repo


# ---------------------------------------------------------------------------
# get_upload_url
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_upload_url_creates_record_and_returns_url():
    repo = make_mock_repo()

    user = {
        "sub": "test-user-123",
        "email": "test@example.com",
    }

    with patch(
        "app.services.image_service.S3Service.generate_presigned_url",
        return_value="https://s3.example.com/presigned",
    ):
        result = await ImageService.get_upload_url(
            repo,
            "photo.jpg",
            "image/jpeg",
            user,
        )

    assert "image_id" in result
    assert result["upload_url"] == "https://s3.example.com/presigned"

    repo.create.assert_awaited_once()

    item = repo.create.call_args[0][0]

    assert item["filename"] == "photo.jpg"
    assert item["status"] == "PENDING"
    assert item["created_by"] == "test-user-123"
    assert "raw/" in item["s3_key"]


# ---------------------------------------------------------------------------
# already_processed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_already_processed_returns_true():
    repo = make_mock_repo(
        list_by_status=AsyncMock(return_value={
            "items": [{"s3_key": "raw/x.jpg"}],
            "last_key": None,
        })
    )

    result = await ImageService.already_processed(repo, "raw/x.jpg")
    assert result is True


@pytest.mark.asyncio
async def test_already_processed_returns_false():
    repo = make_mock_repo(
        list_by_status=AsyncMock(return_value={
            "items": [],
            "last_key": None,
        })
    )

    result = await ImageService.already_processed(repo, "raw/x.jpg")
    assert result is False


# ---------------------------------------------------------------------------
# process_image
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_image_success():
    repo = make_mock_repo()

    existing_item = {
        "id": "1",
        "s3_key": "raw/test.jpg",
        "filename": "test.jpg",
        "status": "PENDING",
        "created_at": datetime.datetime.utcnow().isoformat(),
    }

    # process_image STILL uses list_all internally (your current code)
    repo.list_all = AsyncMock(return_value=[existing_item])

    mock_s3 = MagicMock()
    mock_s3.copy_object = MagicMock()
    mock_s3.delete_object = MagicMock()

    with patch.object(ImageService, "_get_s3_client", return_value=mock_s3):
        new_key = await ImageService.process_image(
            repo,
            "bucket",
            "raw/test.jpg",
        )

    assert new_key == "processed/test.jpg"


@pytest.mark.asyncio
async def test_process_image_not_found():
    repo = make_mock_repo()
    repo.list_all = AsyncMock(return_value=[])

    with pytest.raises(ValueError):
        await ImageService.process_image(
            repo,
            "bucket",
            "raw/missing.jpg",
        )


# ---------------------------------------------------------------------------
# get_all_images
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_all_images():
    repo = make_mock_repo()

    repo.list_by_user = AsyncMock(return_value=[
        {
            "id": "123",
            "filename": "photo.jpg",
            "status": "COMPLETED",
            "s3_key": "raw/x.jpg",
            "s3_processed_file": "processed/x.jpg",
            "created_at": "2024-01-01T00:00:00",
        }
    ])

    with patch(
        "app.services.image_service.S3Service.generate_presigned_url",
        return_value="https://signed-url",
    ):
        result = await ImageService.get_all_images(repo, "test-user")

    assert len(result) == 1
    assert result[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_get_all_images_empty():
    repo = make_mock_repo()
    repo.list_by_user = AsyncMock(return_value=[])

    result = await ImageService.get_all_images(repo, "test-user")

    assert result == []
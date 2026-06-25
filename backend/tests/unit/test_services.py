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

    # UPDATED: no more list_all in production usage
    repo.list_by_user = AsyncMock(return_value=[])

    for attr, val in overrides.items():
        setattr(repo, attr, val)

    return repo


# ---------------------------------------------------------------------------
# get_upload_url
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_upload_url_creates_record_and_returns_url():
    repo = make_mock_repo()

    with patch(
        "app.services.image_service.S3Service.generate_presigned_url",
        return_value="https://s3.example.com/presigned",
    ):
        result = await ImageService.get_upload_url(
            repo,
            "photo.jpg",
            "image/jpeg",
            user_id="test-user-123",
        )

    assert "image_id" in result
    assert result["upload_url"] == "https://s3.example.com/presigned"

    repo.create.assert_awaited_once()

    item = repo.create.call_args[0][0]

    assert item["filename"] == "photo.jpg"
    assert item["status"] == "PENDING"
    assert "raw/" in item["s3_key"]
    assert item["created_by"] == "test-user-123"


# ---------------------------------------------------------------------------
# already_processed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_already_processed_returns_true_when_key_found():
    repo = make_mock_repo(
        list_by_status=AsyncMock(return_value={
            "items": [{"s3_key": "raw/abc-photo.jpg", "status": "COMPLETED"}],
            "last_key": None,
        })
    )

    result = await ImageService.already_processed(repo, "raw/abc-photo.jpg")
    assert result is True


@pytest.mark.asyncio
async def test_already_processed_returns_false_when_key_absent():
    repo = make_mock_repo(
        list_by_status=AsyncMock(return_value={"items": [], "last_key": None})
    )

    result = await ImageService.already_processed(repo, "raw/abc-photo.jpg")
    assert result is False


# ---------------------------------------------------------------------------
# process_image
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_image_copies_and_deletes_s3_object():
    existing_item = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "filename": "photo.jpg",
        "status": "PENDING",
        "s3_key": "raw/abc-123-photo.jpg",
        "created_at": datetime.datetime(2024, 1, 1).isoformat(),
    }

    repo = make_mock_repo(list_by_user=AsyncMock(return_value=[existing_item]))

    mock_s3 = MagicMock()
    mock_s3.copy_object = MagicMock()
    mock_s3.delete_object = MagicMock()

    with patch.object(ImageService, "_get_s3_client", return_value=mock_s3):
        new_key = await ImageService.process_image(
            repo,
            "my-bucket",
            "raw/abc-123-photo.jpg",
        )

    assert new_key == "processed/abc-123-photo.jpg"

    mock_s3.copy_object.assert_called_once_with(
        Bucket="my-bucket",
        CopySource={
            "Bucket": "my-bucket",
            "Key": "raw/abc-123-photo.jpg",
        },
        Key="processed/abc-123-photo.jpg",
    )

    mock_s3.delete_object.assert_called_once_with(
        Bucket="my-bucket",
        Key="raw/abc-123-photo.jpg",
    )


@pytest.mark.asyncio
async def test_process_image_raises_when_record_not_found():
    repo = make_mock_repo(list_by_user=AsyncMock(return_value=[]))

    with pytest.raises(ValueError, match="Record not found"):
        await ImageService.process_image(
            repo,
            "my-bucket",
            "raw/missing.jpg",
        )


# ---------------------------------------------------------------------------
# get_all_images (USER SCOPED)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_all_images_maps_dynamo_items_correctly():
    repo = make_mock_repo(
        list_by_user=AsyncMock(return_value=[
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "filename": "photo.jpg",
                "status": "COMPLETED",
                "s3_key": "raw/abc-123-photo.jpg",
                "s3_processed_file": "thumbnails/photo.jpg",
                "created_at": "2024-01-01T12:00:00",
            }
        ])
    )

    with patch(
        "app.services.image_service.S3Service.generate_presigned_url",
        return_value="https://s3.example.com/presigned",
    ):
        result = await ImageService.get_all_images(
            repo,
            user_id="test-user-123",
        )

    assert len(result) == 1

    item = result[0]

    assert item["id"] == "123e4567-e89b-12d3-a456-426614174000"
    assert item["status"] == "completed"
    assert item["url"] == "https://s3.example.com/presigned"


@pytest.mark.asyncio
async def test_get_all_images_empty():
    repo = make_mock_repo(list_by_user=AsyncMock(return_value=[]))

    with patch("app.services.image_service.S3Service.generate_presigned_url"):
        result = await ImageService.get_all_images(
            repo,
            user_id="test-user-123",
        )

    assert result == []
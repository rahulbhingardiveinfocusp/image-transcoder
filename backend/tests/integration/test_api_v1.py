import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# POST /api/v1/request-upload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_request_upload_returns_upload_url(client: AsyncClient, mock_repo):
    """Happy path — service creates a record and returns a presigned URL."""

    # patch S3Service so no real AWS call is made
    with patch(
        "app.services.image_service.S3Service.generate_presigned_url",
        return_value="https://s3.example.com/presigned",
    ):
        response = await client.post(
            "/api/v1/request-upload",
            json={"filename": "test_image.jpg", "content_type": "image/jpeg"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "image_id" in body
    assert "upload_url" in body
    assert body["upload_url"] == "https://s3.example.com/presigned"

    # repo.create was called once with the right shape
    mock_repo.create.assert_awaited_once()
    call_data = mock_repo.create.call_args[0][0]
    assert call_data["filename"] == "test_image.jpg"
    assert call_data["status"] == "PENDING"
    assert call_data["s3_key"].startswith("raw/")


@pytest.mark.asyncio
async def test_request_upload_missing_content_type(client: AsyncClient):
    """Pydantic should reject a payload missing content_type."""
    response = await client.post(
        "/api/v1/request-upload",
        json={"filename": "test_image.jpg"},   # content_type omitted
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/get-all-images
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_all_images_empty(client: AsyncClient, mock_repo):
    """Returns an empty list when the table has no items."""
    mock_repo.list_all = AsyncMock(return_value=[])

    response = await client.get("/api/v1/get-all-images")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_all_images_returns_list(client: AsyncClient, mock_repo):
    """Returns mapped image dicts with presigned URLs."""
    import datetime

    mock_repo.list_all = AsyncMock(return_value=[
        {
            "id": "abc-123",
            "filename": "photo.jpg",
            "status": "COMPLETED",
            "s3_key": "raw/abc-123-photo.jpg",
            "s3_processed_file": "thumbnails/photo.jpg",
            "created_at": datetime.datetime(2024, 1, 1, 12, 0, 0).isoformat(),
        }
    ])

    with patch(
        "app.services.image_service.S3Service.generate_presigned_url",
        return_value="https://s3.example.com/presigned",
    ):
        response = await client.get("/api/v1/get-all-images")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == "abc-123"
    assert items[0]["status"] == "completed"   # service lowercases before returning
    assert "url" in items[0]
    assert "s3_key" in items[0]
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_request_upload_endpoint(client: AsyncClient):
    """
    Test the /images/request-upload endpoint
    """
    payload = {"filename": "test_image.jpg"}
    
    response = await client.post("/images/request-upload", json=payload)
    
    assert response.status_code == 200
    # Add assertions based on what ImageService.get_upload_url returns
    assert "upload_url" in response.json()
from unittest.mock import MagicMock
from app.services.image_service import process_image

def test_process_image_logic():
    # Mock the S3 service so we don't upload actual files
    mock_s3 = MagicMock()
    result = process_image(mock_s3, "test_file.jpg")
    assert result == "expected_output"
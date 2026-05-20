import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from main import app
from app.config import settings
from app.schemas import ContractChangeOutput, ContractChangeDetail

# Force API_KEY to None to prevent local .env values from requiring X-API-Key in tests
settings.API_KEY = None

client = TestClient(app)


def test_health_endpoint():
    """
    Verifies that the /health endpoint is operational and returns a success status.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": settings.VERSION}

def test_compare_endpoint_validation_error():
    """
    Verifies that malformed Base64 strings trigger a Sentinel 422 HTTP validation exception.
    """
    payload = {
        "contract_original_base64": "invalid_base64_str!!!",
        "addendum_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    }
    response = client.post("/api/v1/compare", json=payload)
    assert response.status_code == 422
    detail_str = str(response.json()["detail"]).lower()
    assert "sentinel 422" in detail_str or "validation" in detail_str or "base64" in detail_str


@patch("app.api.endpoints.execute_contract_comparison_pipeline", new_callable=AsyncMock)
def test_compare_endpoint_success(mock_pipeline):
    """
    Verifies that a valid payload is successfully authorized and processes correctly (using pipeline mocks).
    """
    mock_data = ContractChangeOutput(
        changes=[
            ContractChangeDetail(
                sections_changed="Clause 4 - Indemnity",
                topics_touched=["Indemnity", "Liability"],
                summary_of_the_change="Liability limit was increased from $1M to $5M."
            )
        ]
    )
    mock_pipeline.return_value = (mock_data, "test-trace-id")

    payload = {
        "contract_original_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "addendum_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    }
    
    response = client.post("/api/v1/compare", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["telemetry_trace_id"] == "test-trace-id"
    assert len(data["data"]["changes"]) == 1
    assert data["data"]["changes"][0]["sections_changed"] == "Clause 4 - Indemnity"

@patch("app.api.dependencies.settings")
def test_api_key_unauthorized(mock_settings):
    """
    Verifies that requests fail with HTTP 401 Unauthorized when API Key security is configured but invalid.
    """
    mock_settings.API_KEY = "secure-test-key"
    payload = {
        "contract_original_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "addendum_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    }
    
    # 1. Missing authentication header
    response = client.post("/api/v1/compare", json=payload)
    assert response.status_code == 401
    
    # 2. Invalid authentication header
    response = client.post("/api/v1/compare", json=payload, headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401
    
    # 3. Valid authentication header
    with patch("app.api.endpoints.execute_contract_comparison_pipeline", new_callable=AsyncMock) as mock_p:
        mock_p.return_value = (ContractChangeOutput(changes=[]), "test-trace")
        response = client.post("/api/v1/compare", json=payload, headers={"X-API-Key": "secure-test-key"})
        assert response.status_code == 200

def test_docs_csp_headers():
    """
    Verifies that security headers are set, specifically validating the relaxed CSP
    for docs paths vs the strict default-src 'none' CSP on regular endpoints.
    """
    # 1. /docs path gets relaxed CSP
    response_docs = client.get("/docs")
    assert response_docs.status_code == 200
    assert "Content-Security-Policy" in response_docs.headers
    csp_docs = response_docs.headers["Content-Security-Policy"]
    assert "https://cdn.jsdelivr.net" in csp_docs
    assert "default-src 'self'" in csp_docs
    
    # 2. /health path gets strict CSP
    response_health = client.get("/health")
    assert response_health.status_code == 200
    assert "Content-Security-Policy" in response_health.headers
    csp_health = response_health.headers["Content-Security-Policy"]
    assert "default-src 'none'" in csp_health

@patch("app.api.endpoints.execute_contract_comparison_pipeline", new_callable=AsyncMock)
def test_compare_endpoint_files_success(mock_pipeline):
    """
    Verifies that direct file upload works correctly, parses files, encodes to base64,
    and returns a success response.
    """
    mock_data = ContractChangeOutput(
        changes=[
            ContractChangeDetail(
                sections_changed="Clause 5",
                topics_touched=["Termination"],
                summary_of_the_change="Termination notice reduced to 15 days."
            )
        ]
    )
    mock_pipeline.return_value = (mock_data, "test-files-trace")
    
    # Create fake files using bytes
    original_file_data = b"fake-original-file-bytes"
    addendum_file_data = b"fake-addendum-file-bytes"
    
    files = {
        "original_file": ("original.png", original_file_data, "image/png"),
        "addendum_file": ("addendum.png", addendum_file_data, "image/png")
    }
    
    response = client.post("/api/v1/compare/files", files=files)
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert data["telemetry_trace_id"] == "test-files-trace"
    assert len(data["data"]["changes"]) == 1
    assert data["data"]["changes"][0]["sections_changed"] == "Clause 5"
    
    # Verify the mocked pipeline was called with base64 encoded strings of our data
    import base64
    expected_original_b64 = base64.b64encode(original_file_data).decode("utf-8")
    expected_addendum_b64 = base64.b64encode(addendum_file_data).decode("utf-8")
    
    mock_pipeline.assert_called_once_with(
        original_b64=expected_original_b64,
        addendum_b64=expected_addendum_b64,
        language="Spanish"  # Default test fallback language
    )

def test_compare_endpoint_files_validation_error():
    """
    Verifies that uploading empty files triggers a 422 HTTP validation exception.
    """
    files = {
        "original_file": ("original.png", b"", "image/png"),  # Empty file bytes
        "addendum_file": ("addendum.png", b"fake-bytes", "image/png")
    }
    
    response = client.post("/api/v1/compare/files", files=files)
    assert response.status_code == 422
    assert "validation" in str(response.json()["detail"]).lower()



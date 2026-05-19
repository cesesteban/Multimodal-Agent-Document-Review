import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from main import app
from app.config import settings
from app.schemas import ContractChangeOutput, ContractChangeDetail

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
    assert "Sentinel 422" in response.json()["detail"] or "validation" in response.json()["detail"].lower()

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

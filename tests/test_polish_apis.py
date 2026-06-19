import pytest
from httpx import ASGITransport, AsyncClient

from core.main import app


@pytest.mark.asyncio
async def test_system_capabilities_endpoint():
    """Verify system capabilities endpoint returns expected structure."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/system/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert "ledger" in data
    assert "intelligence" in data
    assert "alerts" in data
    assert "collections" in data
    assert "decisioning" in data
    assert "feature_store" in data
    assert "ml" in data
    assert "advisor" in data
    assert data["ledger"]["healthy"] is True
    assert data["ml"]["models"] > 0

@pytest.mark.asyncio
async def test_ml_status_endpoint():
    """Verify ML status endpoint returns healthy and counts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/ml/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "total_models" in data
    assert "active_models_count" in data

@pytest.mark.asyncio
async def test_ml_models_endpoint():
    """Verify ML models listing returns list of registered models metadata."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/ml/models")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        model = data[0]
        assert "model_name" in model
        assert "version" in model
        assert "status" in model

@pytest.mark.asyncio
async def test_ml_models_active_endpoint():
    """Verify ML active models listing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/ml/models/active")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_ml_calibration_endpoint():
    """Verify ML calibration endpoint runs audit and updates artifacts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/ml/calibration")
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert "reliability_curves" in data
    assert "report_path" in data

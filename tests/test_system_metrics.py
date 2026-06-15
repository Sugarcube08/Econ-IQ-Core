import pytest
from httpx import AsyncClient, ASGITransport

from core.main import app


@pytest.mark.asyncio
async def test_health_check_endpoint():
    """Verify /api/v1/health endpoint response structure and status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert "data" in json_data
        assert json_data["data"]["status"] == "healthy"

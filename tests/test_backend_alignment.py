import pytest
from httpx import ASGITransport, AsyncClient

from core.main import app


@pytest.fixture(autouse=True)
def mock_auth():
    from core.core.dependencies import get_current_identity
    from core.models.auth_models import User, UserRole
    
    def get_mock_identity():
        user = User(
            email="admin@econiq.com",
            full_name="Regression Admin",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_verified=True,
            token_version=0
        )
        user.id = None
        return user
        
    app.dependency_overrides[get_current_identity] = get_mock_identity
    yield
    app.dependency_overrides.pop(get_current_identity, None)



@pytest.mark.asyncio
async def test_global_recommendations_endpoint_default():
    """Verify GET /api/v1/recommendations returns list format by default for backward compatibility."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/recommendations")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    items = data["data"]
    assert isinstance(items, list)
    if len(items) > 0:
        rec = items[0]
        assert "customer_id" in rec
        assert "customer_name" in rec
        assert "recommendation_type" in rec
        assert "severity" in rec
        assert "confidence" in rec
        assert "status" in rec
        assert "created_at" in rec


@pytest.mark.asyncio
async def test_global_recommendations_endpoint_paginated():
    """Verify GET /api/v1/recommendations returns paginated format when page is passed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/recommendations?page=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    res_data = data["data"]
    assert isinstance(res_data, dict)
    assert "items" in res_data
    assert "page" in res_data
    assert "limit" in res_data
    assert "total" in res_data
    assert "total_pages" in res_data
    assert isinstance(res_data["items"], list)
    assert len(res_data["items"]) <= 2


@pytest.mark.asyncio
async def test_alerts_enrichment_and_pagination():
    """Verify GET /api/v1/alerts returns customer_name and supports pagination."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Check enriched format by default
        response_default = await ac.get("/api/v1/alerts")
        assert response_default.status_code == 200
        data_default = response_default.json()
        assert data_default["success"] is True
        items = data_default["data"]
        assert isinstance(items, list)
        if len(items) > 0:
            alert = items[0]
            assert "customer_name" in alert
            assert alert["customer_name"] != "Unknown"
        
        # Check paginated format when page is passed
        response_paginated = await ac.get("/api/v1/alerts?page=1&limit=5")
        assert response_paginated.status_code == 200
        data_paginated = response_paginated.json()
        assert data_paginated["success"] is True
        res_data = data_paginated["data"]
        assert isinstance(res_data, dict)
        assert "items" in res_data
        assert "page" in res_data
        assert "total" in res_data
        assert isinstance(res_data["items"], list)


@pytest.mark.asyncio
async def test_risk_signals_endpoint():
    """Verify GET /api/v1/intelligence/risk-signals works and is shaped correctly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/intelligence/risk-signals")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    items = data["data"]
    assert isinstance(items, list)
    if len(items) > 0:
        signal = items[0]
        assert "customer_id" in signal
        assert "customer_name" in signal
        assert "risk_score" in signal
        assert "safety_score" in signal
        assert "trust_delta" in signal
        assert "outstanding_current" in signal
        assert "state" in signal
        assert signal["safety_score"] == pytest.approx(1.0 - signal["risk_score"], abs=1e-3)


@pytest.mark.asyncio
async def test_high_risk_customers_metrics():
    """Verify high-risk customers queue contains true risk_score, safety_score, and payment delays."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/dashboard/high-risk-customers?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    items = data["data"]
    assert isinstance(items, list)
    if len(items) > 0:
        cust = items[0]
        assert "risk_score" in cust
        assert "safety_score" in cust
        assert "average_payment_delay_days" in cust
        assert "payment_delay" in cust
        assert "days_past_due" in cust
        assert "dso" in cust
        assert "overdue_amount" in cust
        assert "credit_limit" in cust
        assert "credit_utilization" in cust
        assert cust["safety_score"] == pytest.approx(1.0 - cust["risk_score"], abs=1e-3)

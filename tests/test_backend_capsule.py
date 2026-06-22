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
async def test_segment_aggregation_endpoint():
    """Verify GET /api/v1/customers/segments returns counts, outstanding sums, and week-over-week trends."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/analytics/segments")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    items = data["data"]["items"] if isinstance(data["data"], dict) and "items" in data["data"] else data["data"]
    assert isinstance(items, list)
    if len(items) > 0:
        segment = items[0]
        assert "state" in segment
        assert "current_state" in segment
        assert "count" in segment
        assert "exposure" in segment
        assert "outstanding" in segment
        assert "trend" in segment
        assert "week_over_week_trend" in segment


@pytest.mark.asyncio
async def test_portfolio_overview_growth_and_adherence():
    """Verify GET /api/v1/analytics/portfolio-overview contains adherence rate, growth trajectory, and concentration metrics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/analytics/portfolio-overview")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    res_data = data["data"]
    
    # Verify Recovery Analytics updated adherence rate
    assert "recovery_analytics" in res_data
    assert "commitment_adherence_rate" in res_data["recovery_analytics"]
    assert isinstance(res_data["recovery_analytics"]["commitment_adherence_rate"], float)
    
    # Verify Growth Analytics added fields
    assert "growth_analytics" in res_data
    growth = res_data["growth_analytics"]
    assert "top_account_share" in growth
    assert "growth_trajectory" in growth
    assert "opportunity_index" in growth
    assert isinstance(growth["top_account_share"], float)
    assert isinstance(growth["growth_trajectory"], str)
    assert isinstance(growth["opportunity_index"], str)
    
    # Verify top-level fallbacks/fields for growth
    assert "top_account_share" in res_data
    assert "growth_trajectory" in res_data
    assert "opportunity_index" in res_data

    # Verify refactored collections fields
    assert "summary" in res_data
    assert "total_outstanding" in res_data["summary"]
    assert "total_recovered_30d" in res_data["summary"]
    assert "recovery_rate_ytd" in res_data["summary"]
    assert "active_commitments_count" in res_data["summary"]

    assert "priority_distribution" in res_data
    assert "critical_count" in res_data["priority_distribution"]
    assert "high_count" in res_data["priority_distribution"]
    assert "medium_count" in res_data["priority_distribution"]
    assert "low_count" in res_data["priority_distribution"]


@pytest.mark.asyncio
async def test_collection_queue_endpoint():
    """Verify GET /api/v1/analytics/collection-queue returns paginated list of prioritized accounts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/analytics/collection-queue?page=1&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    res_data = data["data"]
    assert "items" in res_data
    assert "pagination" in res_data
    pagination = res_data["pagination"]
    assert "page" in pagination
    assert "limit" in pagination
    assert "total" in pagination
    assert "total_pages" in pagination
    
    if len(res_data["items"]) > 0:
        item = res_data["items"][0]
        assert "customer_id" in item
        assert "customer_name" in item
        assert "outstanding" in item
        assert "recovered_ytd" in item
        assert "priority_score" in item
        assert "priority_level" in item
        assert "primary_dunning_reason" in item
        assert "last_outreach_date" in item


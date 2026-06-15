from unittest.mock import AsyncMock, MagicMock

import pytest

from core.models.state_models import CustomerIntelligence, Recommendation
from core.recommendation.rules_engine import RecommendationRulesEngine as RecommendationService
from core.services.alert_service import AlertService


@pytest.mark.asyncio
async def test_alert_rules_risk_spike():
    """Verify that a risk score spike triggers a RISK_SPIKE critical alert."""
    db_session = MagicMock()
    db_session.execute = AsyncMock()
    db_session.flush = AsyncMock()
    db_session.commit = AsyncMock()
    
    # Mock CustomerIntelligence with a risk score spike (0.2 -> 0.4)
    intel = CustomerIntelligence(
        customer_id="cust-1",
        risk_score=0.4,
        risk_previous=0.2,
        trust_score=0.8,
        trust_previous=0.8,
        outstanding_current=100.0,
        outstanding_previous=100.0,
        collection_score=0.8,
        collection_previous=0.8,
        state="active"
    )
    
    # Mock result and scalars chains
    res = MagicMock()
    db_session.execute.return_value = res
    res.scalars.return_value.first.side_effect = [intel, None]

    alert_service = AlertService()
    generated = await alert_service.scan_and_generate_alerts("cust-1", db_session)
    
    assert len(generated) == 1
    assert generated[0].alert_type == "RISK_SPIKE"
    assert generated[0].alert_severity == "CRITICAL"


@pytest.mark.asyncio
async def test_alert_rules_trust_drop():
    """Verify that a trust score drop triggers a TRUST_DROP critical alert."""
    db_session = MagicMock()
    db_session.execute = AsyncMock()
    db_session.flush = AsyncMock()
    db_session.commit = AsyncMock()
    
    # Mock CustomerIntelligence with a trust score drop (0.8 -> 0.6)
    intel = CustomerIntelligence(
        customer_id="cust-2",
        risk_score=0.2,
        risk_previous=0.2,
        trust_score=0.6,
        trust_previous=0.8,
        outstanding_current=100.0,
        outstanding_previous=100.0,
        collection_score=0.8,
        collection_previous=0.8,
        state="active"
    )
    
    res = MagicMock()
    db_session.execute.return_value = res
    res.scalars.return_value.first.side_effect = [intel, None]

    alert_service = AlertService()
    generated = await alert_service.scan_and_generate_alerts("cust-2", db_session)
    
    assert len(generated) == 1
    assert generated[0].alert_type == "TRUST_DROP"
    assert generated[0].alert_severity == "CRITICAL"


@pytest.mark.asyncio
async def test_alert_rules_outstanding_spike():
    """Verify that an outstanding balance spike triggers an OUTSTANDING_SPIKE warning."""
    db_session = MagicMock()
    db_session.execute = AsyncMock()
    db_session.flush = AsyncMock()
    db_session.commit = AsyncMock()
    
    # Mock CustomerIntelligence with an outstanding spike (2000 -> 2500, >120% and previous >= 1000)
    intel = CustomerIntelligence(
        customer_id="cust-3",
        risk_score=0.2,
        risk_previous=0.2,
        trust_score=0.8,
        trust_previous=0.8,
        outstanding_current=2500.0,
        outstanding_previous=2000.0,
        collection_score=0.8,
        collection_previous=0.8,
        state="active"
    )
    
    res = MagicMock()
    db_session.execute.return_value = res
    res.scalars.return_value.first.side_effect = [intel, None]

    alert_service = AlertService()
    generated = await alert_service.scan_and_generate_alerts("cust-3", db_session)
    
    assert len(generated) == 1
    assert generated[0].alert_type == "OUTSTANDING_SPIKE"
    assert generated[0].alert_severity == "WARNING"


@pytest.mark.asyncio
async def test_recommendation_rules_high_growth():
    """Verify that high health, low risk, and high growth triggers HIGH_GROWTH_OPPORTUNITY."""
    db_session = MagicMock()
    db_session.execute = AsyncMock()
    db_session.flush = AsyncMock()
    db_session.commit = AsyncMock()
    
    intel = CustomerIntelligence(
        customer_id="cust-4",
        health_score=0.8,
        risk_score=0.1,
        growth_score=0.8,
        trust_score=0.8,
        collection_score=0.8,
        state="active"
    )
    
    res = MagicMock()
    db_session.execute.return_value = res
    res.scalars.return_value.first.return_value = intel
    
    rec_obj = Recommendation(
        customer_id="cust-4",
        recommendation_type="HIGH_GROWTH_OPPORTUNITY",
        severity="INFO",
        reason="Customer shows strong commercial growth with exceptionally low credit risk profile.",
        confidence=0.90,
        status="ACTIVE"
    )
    res.scalars.return_value.all.return_value = [rec_obj]

    rec_service = RecommendationService()
    res_schema = await rec_service.generate_recommendations(db_session, "cust-4")
    
    assert len(res_schema.recommendations) == 1
    assert res_schema.recommendations[0].action_category == "INCREASE_CREDIT_LIMIT"
    assert res_schema.recommendations[0].priority == "MEDIUM"


@pytest.mark.asyncio
async def test_recommendation_rules_reduce_exposure():
    """Verify that a high risk score triggers REDUCE_EXPOSURE recommendation."""
    db_session = MagicMock()
    db_session.execute = AsyncMock()
    db_session.flush = AsyncMock()
    db_session.commit = AsyncMock()
    
    intel = CustomerIntelligence(
        customer_id="cust-5",
        health_score=0.4,
        risk_score=0.72,
        growth_score=0.4,
        trust_score=0.4,
        collection_score=0.4,
        state="active"
    )
    
    res = MagicMock()
    db_session.execute.return_value = res
    res.scalars.return_value.first.return_value = intel
    
    rec_obj = Recommendation(
        customer_id="cust-5",
        recommendation_type="REDUCE_EXPOSURE",
        severity="WARNING",
        reason="Risk score exceeded threshold. Suggest reducing credit exposure boundaries.",
        confidence=0.90,
        status="ACTIVE"
    )
    res.scalars.return_value.all.return_value = [rec_obj]

    rec_service = RecommendationService()
    res_schema = await rec_service.generate_recommendations(db_session, "cust-5")
    
    assert len(res_schema.recommendations) == 1
    assert res_schema.recommendations[0].action_category == "DECREASE_CREDIT_LIMIT"
    assert res_schema.recommendations[0].priority == "HIGH"

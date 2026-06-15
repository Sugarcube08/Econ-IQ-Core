import polars as pl
import pytest

from core.prediction.registry import model_registry
from core.prediction.service import (
    DefaultGrowthEstimator,
    DefaultRiskEstimator,
)
from core.schemas.prediction import GrowthPrediction, RiskPrediction


@pytest.mark.asyncio
async def test_model_registry_lifecycle():
    """Tests registration, version resolution, and swapping in registry."""
    class MockEstimator:
        def predict(self, customer_id, df):
            return "prediction"
        def get_metadata(self):
            return None

    # Register a temporary model
    model_registry.register_model("TEST_MODEL", "1.0.0", MockEstimator())
    model_registry.register_model("TEST_MODEL", "2.0.0", MockEstimator())

    # Get specific version
    m1 = model_registry.get_model("TEST_MODEL", "1.0.0")
    assert isinstance(m1, MockEstimator)

    # Get latest version resolved automatically
    m2 = model_registry.get_model("TEST_MODEL")
    assert isinstance(m2, MockEstimator)


@pytest.mark.asyncio
async def test_risk_estimator_heuristics():
    """Verifies that DefaultRiskEstimator outputs valid contracts and limits."""
    estimator = DefaultRiskEstimator()
    
    # Test with empty dataframe (default proxy logic)
    pred_empty = estimator.predict("cust-1", pl.DataFrame())
    assert isinstance(pred_empty, RiskPrediction)
    assert pred_empty.score == 0.5
    assert pred_empty.risk_level == "MEDIUM"

    # Test with normal dataframe
    df = pl.DataFrame({
        "sales_window": [10000.0],
        "payments_window": [9000.0],
        "penalty_window": [0.0],
        "sales_recent": [1000.0],
        "last_purchased_at": [None],
    })
    pred = estimator.predict("cust-2", df)
    assert pred.score < 0.25
    assert pred.risk_level == "LOW"


@pytest.mark.asyncio
async def test_growth_estimator_heuristics():
    """Verifies DefaultGrowthEstimator computes expansion/stable boundaries."""
    estimator = DefaultGrowthEstimator()
    
    pred_empty = estimator.predict("cust-1", pl.DataFrame())
    assert isinstance(pred_empty, GrowthPrediction)
    assert pred_empty.growth_potential == "STABLE"

    # Test acceleration
    df = pl.DataFrame({
        "sales_window": [10000.0],
        "sales_recent": [8000.0], # high recent velocity
    })
    pred = estimator.predict("cust-2", df)
    assert pred.growth_potential == "ACCELERATING"

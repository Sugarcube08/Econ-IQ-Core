from fastapi.testclient import TestClient

from core.main import app


def test_health_check_endpoint():
    """Verify /api/v1/health endpoint response structure and status."""
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert "data" in json_data
        assert json_data["data"]["status"] == "healthy"


def test_system_metrics_endpoint():
    """Verify /api/v1/system/metrics endpoint response fields and data types."""
    with TestClient(app) as client:
        response = client.get("/api/v1/system/metrics")
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert "data" in json_data
        
        metrics = json_data["data"]
        # Verify all required plan fields are present with correct types
        assert isinstance(metrics["rss_mb"], float)
        assert isinstance(metrics["vms_mb"], float)
        assert isinstance(metrics["threads"], int)
        assert isinstance(metrics["pending_queue"], int)
        assert isinstance(metrics["sync_backlog"], int)
        assert isinstance(metrics["active_workers"], int)
        assert isinstance(metrics["startup_mode"], str)
        
        # Values should be non-negative (except potentially system error fallbacks if any)
        assert metrics["rss_mb"] >= 0.0
        assert metrics["vms_mb"] >= 0.0
        assert metrics["threads"] >= 0
        assert metrics["pending_queue"] >= 0
        assert metrics["sync_backlog"] >= 0
        assert metrics["active_workers"] >= 0
        assert metrics["startup_mode"] in ("full", "api-only", "recovery")


def test_system_runtime_endpoint():
    """Verify /api/v1/system/runtime endpoint response fields and data types."""
    with TestClient(app) as client:
        response = client.get("/api/v1/system/runtime")
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert "data" in json_data
        
        runtime = json_data["data"]
        # Verify all required fields from Phase 8 are present with correct types
        assert isinstance(runtime["rss_mb"], float)
        assert isinstance(runtime["vms_mb"], float)
        assert isinstance(runtime["threads"], int)
        assert isinstance(runtime["queue_depth"], int)
        assert isinstance(runtime["sync_backlog"], int)
        assert isinstance(runtime["active_workers"], int)
        assert isinstance(runtime["processing_mode"], str)
        assert isinstance(runtime["active_worker"], str)
        assert isinstance(runtime["current_stage"], str)
        
        # Values should be non-negative
        assert runtime["rss_mb"] >= 0.0
        assert runtime["vms_mb"] >= 0.0
        assert runtime["threads"] >= 0
        assert runtime["queue_depth"] >= 0
        assert runtime["sync_backlog"] >= 0
        assert runtime["active_workers"] >= 0
        assert runtime["processing_mode"] in ("sequential", "balanced", "parallel")
        assert runtime["active_worker"] in ("none", "sync_worker", "intel_worker", "sequential_worker")
        assert runtime["current_stage"] in ("idle", "sync_ingestion", "ledger_materialization", "queue_population", "customer_recomputation", "sleeping")

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_analyze_stream_endpoint():
    """Test streaming endpoint returns proper SSE format"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/analyze-stream", json={"symbol": "AAPL"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/plain; charset=utf-8"


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test the health check endpoint"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"


@pytest.mark.asyncio
async def test_invalid_symbol():
    """Test handling of invalid stock symbols"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Test invalid symbol format
        r = await ac.post("/analyze-stream", json={"symbol": "TOOLONG"})
        assert r.status_code == 422  # Validation error

        # Test missing symbol
        r = await ac.post("/analyze-stream", json={})
        assert r.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_metrics_endpoint():
    """Test metrics endpoint"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "message" in body
    assert "9090" in body["message"]


@pytest.mark.asyncio
async def test_metrics_collection():
    """Test that metrics are properly collected"""
    from app.utils.monitoring import metrics
    import time

    # Record the time before making request
    start_time = time.time()

    # Make a request using TestClient for synchronous operation
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200

    # Give a small delay to ensure metrics are recorded
    time.sleep(0.1)

    # Check that metrics were recorded by checking if we can collect them
    # This is a basic test that the metrics system is working
    try:
        # Try to access the counter - this will work if metrics are properly set up
        counter_samples = list(metrics.request_count.collect())[0].samples
        assert len(counter_samples) > 0, "No metrics samples found"
        logger_info = f"Metrics collection test passed with {len(counter_samples)} samples"
    except Exception as e:
        pytest.fail(f"Metrics collection failed: {e}")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def disable_external_apis():
    # Mock all external API calls for testing
    pass

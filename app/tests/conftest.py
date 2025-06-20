import pytest
import asyncio
import os
from unittest.mock import patch
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set up test environment variables"""
    test_env = {
        "ALPHA_VANTAGE_KEY": "test_alpha_key",
        "NEWSAPI_KEY": "test_news_key",
        "OPENAI_API_KEY": "test_openai_key",
        "FINNHUB_KEY": "test_finnhub_key",
        "LOG_LEVEL": "ERROR",  # Reduce logging noise in tests
        "ENABLE_METRICS": "false",  # Disable metrics in tests
        "RATE_LIMIT_REQUESTS": "1000",  # High limit for tests
    }

    with patch.dict(os.environ, test_env):
        yield


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def mock_external_apis():
    """Mock all external API calls to avoid rate limiting and network issues in tests"""
    with patch('app.services.market_data.fetch_price_alpha') as mock_alpha, \
            patch('app.services.market_data.fetch_price_yf') as mock_yf, \
            patch('app.services.sentiment.fetch_news_articles') as mock_news, \
            patch('app.services.sentiment.analyze_with_openai') as mock_openai:

        # Set up default mock responses
        mock_alpha.return_value = {
            "price": 150.0,
            "symbol": "TEST",
            "change": 1.0,
            "change_percent": 0.67,
            "volume": 1000000,
            "currency": "USD",
            "source": "alpha_vantage"
        }

        mock_yf.return_value = {
            "price": 150.0,
            "symbol": "TEST",
            "change": 1.0,
            "change_percent": 0.67,
            "volume": 1000000,
            "currency": "USD",
            "source": "yfinance"
        }

        mock_news.return_value = []
        mock_openai.return_value = "neutral"

        yield {
            "alpha": mock_alpha,
            "yfinance": mock_yf,
            "news": mock_news,
            "openai": mock_openai
        }

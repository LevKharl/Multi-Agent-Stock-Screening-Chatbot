import pytest
from app.agents import orchestrate
from app.schemas import StockRequest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_orchestration():
    """Test basic orchestration functionality"""
    res = await orchestrate(StockRequest(symbol="MSFT"))
    assert res.price > 0 and res.sentiment_summary
    assert res.symbol == "MSFT"
    assert res.company_name is not None


@pytest.mark.asyncio
async def test_invalid_symbol():
    """Test handling of invalid stock symbols"""
    with pytest.raises(Exception):  # Should raise InvalidSymbolError
        await orchestrate(StockRequest(symbol="INVALID"))


@pytest.mark.asyncio
async def test_orchestration_data_completeness():
    """Test that orchestration returns complete data structure"""
    res = await orchestrate(StockRequest(symbol="AAPL"))

    # Check required fields
    assert hasattr(res, 'price')
    assert hasattr(res, 'financial_metrics')
    assert hasattr(res, 'sentiment_summary')
    assert hasattr(res, 'analyst_ratings')
    assert hasattr(res, 'data_sources')

    # Check data sources are populated
    assert len(res.data_sources) > 0


@pytest.mark.asyncio
@patch('app.services.market_data.fetch_price_with_fallback')
@patch('app.services.market_data.fetch_fundamentals_yf')
@patch('app.services.market_data.fetch_analyst_ratings_finnhub')
@patch('app.services.market_data.fetch_earnings_data_yf')
@patch('app.services.sentiment.fetch_comprehensive_sentiment')
@patch('app.services.market_data.get_company_name')
async def test_orchestration_with_mocks(mock_company, mock_sentiment, mock_earnings, mock_analyst, mock_fundamentals, mock_price):
    """Test orchestration with mocked services"""
    from app.schemas import FinancialMetrics, SentimentSummary, SentimentScore, AnalystRating

    # Mock all external API calls
    mock_price.return_value = {"price": 150.0, "symbol": "AAPL", "change": 1.0,
                               "change_percent": 0.67, "volume": 1000000, "currency": "USD", "source": "mock"}

    mock_fundamentals.return_value = FinancialMetrics(
        market_cap=2500000000000,
        pe_ratio=25.0,
        revenue_ttm=350000000000
    )

    mock_analyst.return_value = [
        AnalystRating(firm="Mock Firm", rating="BUY", price_target=160.0)
    ]

    mock_earnings.return_value = []

    mock_sentiment.return_value = (
        [],  # sentiment items
        SentimentSummary(
            overall_score=SentimentScore.POSITIVE,
            confidence=0.8,
            positive_count=5,
            negative_count=1,
            neutral_count=2,
            summary_text="Mock positive sentiment"
        )
    )

    mock_company.return_value = "Apple Inc."

    result = await orchestrate(StockRequest(symbol="AAPL"))

    # Verify the result uses mocked data
    assert result.symbol == "AAPL"
    assert result.price == 150.0
    assert result.company_name == "Apple Inc."
    assert len(result.analyst_ratings) > 0
    assert result.financial_metrics.market_cap == 2500000000000


@pytest.mark.asyncio
async def test_orchestration_fallback_logic():
    """Test that orchestration handles API failures gracefully"""
    # This test will rely on the actual fallback logic in the system
    # when primary APIs fail (like Alpha Vantage rate limiting)
    res = await orchestrate(StockRequest(symbol="GOOGL"))

    # Should still return a result even if some APIs fail
    assert res.symbol == "GOOGL"
    assert res.company_name is not None
    # Price should be available from fallback (Yahoo Finance)
    assert res.price is not None and res.price > 0


@pytest.mark.asyncio
async def test_orchestration_performance():
    """Test that orchestration completes within reasonable time"""
    import time

    start_time = time.time()
    res = await orchestrate(StockRequest(symbol="TSLA"))
    end_time = time.time()

    # Should complete within 30 seconds
    assert end_time - start_time < 45
    assert res.symbol == "TSLA"

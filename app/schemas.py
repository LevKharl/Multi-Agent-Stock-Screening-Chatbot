from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class StockRequest(BaseModel):
    symbol: str = Field(..., pattern=r"^[A-Z]{1,5}$",
                        description="NASDAQ stock symbol")


class SentimentScore(str, Enum):
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


class SentimentItem(BaseModel):
    source: str
    title: str
    polarity: float = Field(..., ge=-1, le=1,
                            description="Sentiment polarity from -1 to 1")
    sentiment_score: SentimentScore
    published_at: Optional[datetime] = None
    url: Optional[str] = None


class AnalystRating(BaseModel):
    firm: str
    rating: str
    price_target: Optional[float] = None
    date: Optional[datetime] = None


class EarningsData(BaseModel):
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    revenue_estimate: Optional[float] = None
    revenue_actual: Optional[float] = None
    quarter: Optional[str] = None
    year: Optional[int] = None


class FinancialMetrics(BaseModel):
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    peg_ratio: Optional[float] = None
    price_to_book: Optional[float] = None
    price_to_sales: Optional[float] = None
    revenue_ttm: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    profit_margin: Optional[float] = None
    return_on_equity: Optional[float] = None
    return_on_assets: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None


class SentimentSummary(BaseModel):
    overall_score: SentimentScore
    confidence: float = Field(..., ge=0, le=1)
    positive_count: int
    negative_count: int
    neutral_count: int
    summary_text: str


class StockResponse(BaseModel):
    symbol: str
    company_name: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"
    change: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None

    # Enhanced financial data
    financial_metrics: FinancialMetrics

    # Analyst data
    analyst_ratings: List[AnalystRating] = []
    consensus_rating: Optional[str] = None
    average_price_target: Optional[float] = None

    # Earnings data
    earnings_data: List[EarningsData] = []
    next_earnings_date: Optional[datetime] = None

    # Enhanced sentiment
    sentiment_items: List[SentimentItem] = []
    sentiment_summary: SentimentSummary

    # Metadata
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    data_sources: List[str] = []

    # For backwards compatibility
    @property
    def sentiment(self) -> List[Dict[str, Any]]:
        """Backwards compatibility with old sentiment format"""
        return [
            {
                "source": item.source,
                "title": item.title,
                "polarity": item.polarity
            }
            for item in self.sentiment_items
        ]

    @property
    def market_cap(self) -> Optional[float]:
        """Backwards compatibility"""
        return self.financial_metrics.market_cap

    @property
    def pe_ratio(self) -> Optional[float]:
        """Backwards compatibility"""
        return self.financial_metrics.pe_ratio

    @property
    def revenue_ttm(self) -> Optional[float]:
        """Backwards compatibility"""
        return self.financial_metrics.revenue_ttm


class APIError(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None

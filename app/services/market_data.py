import httpx
import yfinance as yf
import finnhub
import pandas as pd
import asyncio
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from loguru import logger

from app.config import settings
from app.utils.error_handling import (
    handle_api_errors,
    create_retry_decorator,
    fallback_manager,
    DataNotFoundError,
    InvalidSymbolError,
    APIRateLimitError
)
from app.utils.monitoring import track_performance
from app.schemas import FinancialMetrics, AnalystRating, EarningsData

# Initialize clients
finnhub_client = finnhub.Client(
    api_key=settings.finnhub_key) if settings.finnhub_key else None

ALPHA_URL = "https://www.alphavantage.co/query"


def validate_stock_symbol(symbol: str) -> bool:
    """
    Validate stock symbol format before making API calls.

    Args:
        symbol: Stock symbol to validate

    Returns:
        True if symbol format is valid, False otherwise

    Raises:
        InvalidSymbolError: If symbol format is invalid
    """
    if not symbol or not isinstance(symbol, str):
        raise InvalidSymbolError("Symbol must be a non-empty string")

    # Remove whitespace and convert to uppercase
    symbol = symbol.strip().upper()

    # Basic format validation
    if len(symbol) < 1 or len(symbol) > 5:
        raise InvalidSymbolError(
            f"Invalid symbol '{symbol}': Stock symbols must be 1-5 characters long")

    # Check for valid characters (letters and dots only)
    if not re.match(r'^[A-Z\.]+$', symbol):
        raise InvalidSymbolError(
            f"Invalid symbol '{symbol}': Stock symbols can only contain letters and dots")

    # Additional checks for obviously invalid patterns
    if symbol.startswith('.') or symbol.endswith('.'):
        raise InvalidSymbolError(
            f"Invalid symbol '{symbol}': Cannot start or end with a dot")

    if '..' in symbol:
        raise InvalidSymbolError(
            f"Invalid symbol '{symbol}': Cannot contain consecutive dots")

    return True


@handle_api_errors
@create_retry_decorator()
@track_performance("source_alpha_vantage_price")
async def fetch_price_alpha(symbol: str) -> Dict[str, Any]:
    """Fetch real-time price from Alpha Vantage"""
    # Check if API key is available
    if not settings.alpha_vantage_key:
        raise DataNotFoundError("Alpha Vantage API key not configured")

    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        response = await client.get(
            ALPHA_URL,
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": settings.alpha_vantage_key
            }
        )
        response.raise_for_status()
        data = response.json()

        # Better error handling for Alpha Vantage responses
        if "Error Message" in data:
            raise InvalidSymbolError(f"Invalid symbol: {symbol}")

        if "Information" in data:
            # API call frequency limit reached
            raise APIRateLimitError("Alpha Vantage API rate limit exceeded")

        if "Note" in data:
            # API call frequency limit reached (different format)
            raise APIRateLimitError("Alpha Vantage API rate limit exceeded")

        if "Global Quote" not in data or not data["Global Quote"]:
            raise DataNotFoundError(f"No price data found for {symbol}")

        quote = data["Global Quote"]

        # Check if quote has valid data
        if not quote or "05. price" not in quote:
            raise DataNotFoundError(f"Invalid price data format for {symbol}")

        result = {
            "price": float(quote["05. price"]),
            "change": float(quote["09. change"]),
            "change_percent": float(quote["10. change percent"].replace("%", "")),
            "volume": int(quote["06. volume"]),
            "currency": "USD",
            "source": "alpha_vantage"
        }

        return result


@handle_api_errors
@create_retry_decorator()
@track_performance("source_yfinance_price")
async def fetch_price_yfinance(symbol: str) -> Dict[str, Any]:
    """Fetch price from Yahoo Finance with multi-index column support"""
    # Add delay to avoid rate limiting
    await asyncio.sleep(1.0)

    try:
        ticker = yf.Ticker(symbol)
        # Use 2 days to ensure we have recent data
        hist = ticker.history(period="2d", timeout=15)

        # Handle multi-index columns (standard in latest yfinance)
        if hasattr(hist, 'columns') and isinstance(hist.columns, pd.MultiIndex):
            # Flatten multi-index columns
            hist.columns = hist.columns.droplevel(1)

        if hist.empty:
            raise DataNotFoundError(f"No price data found for {symbol}")

        latest = hist.iloc[-1]

        # Calculate change from previous day if available
        if len(hist) > 1:
            previous = hist.iloc[-2]
            change = float(latest["Close"] - previous["Close"])
            change_percent = float(
                (latest["Close"] - previous["Close"]) / previous["Close"] * 100)
        else:
            # Fallback to intraday change
            change = float(latest["Close"] - latest["Open"])
            change_percent = float(
                (latest["Close"] - latest["Open"]) / latest["Open"] * 100)

        result = {
            "price": float(latest["Close"]),
            "change": change,
            "change_percent": change_percent,
            "volume": int(latest["Volume"]),
            "currency": "USD",  # Default to USD to avoid extra API call
            "source": "yfinance"
        }

        return result

    except Exception as e:
        if "429" in str(e) or "Too Many Requests" in str(e):
            raise APIRateLimitError(f"Yahoo Finance rate limit exceeded: {e}")
        raise


async def fetch_price_with_fallback(symbol: str) -> Dict[str, Any]:
    """Fetch price with fallback chain (Alpha Vantage → Yahoo Finance)"""
    return await fallback_manager.execute_with_fallback(
        "price",
        symbol,
        fetch_price_alpha,
        [fetch_price_yfinance]
    )


@handle_api_errors
@create_retry_decorator()
@track_performance("source_yfinance_fundamentals")
async def fetch_fundamentals_yf(symbol: str) -> FinancialMetrics:
    """Fetch comprehensive fundamental data compatible with latest yfinance"""
    # Delay to avoid rate limiting
    await asyncio.sleep(3.0)

    try:
        logger.debug(
            f"Starting fundamentals fetch for {symbol} with latest yfinance")

        # Let yfinance handle session management (required for latest versions)
        ticker = yf.Ticker(symbol)

        # Strategy 1: Try historical data first (most reliable)
        hist_data = {}
        try:
            logger.debug(f"Getting 52-week range for {symbol}")
            # Use shorter period to reduce load
            hist = ticker.history(period="1y", timeout=30,
                                  auto_adjust=True, prepost=False)

            # Handle both old and new yfinance multi-index format
            if hasattr(hist, 'columns') and isinstance(hist.columns, pd.MultiIndex):
                # Flatten multi-index columns (new yfinance format)
                hist.columns = hist.columns.droplevel(1)

            if not hist.empty:
                hist_data = {
                    "fifty_two_week_high": float(hist["High"].max()),
                    "fifty_two_week_low": float(hist["Low"].min())
                }
                logger.info(
                    f"Historical data success for {symbol}: 52w range ${hist_data['fifty_two_week_low']:.2f}-${hist_data['fifty_two_week_high']:.2f}")
            else:
                logger.debug(f"Empty historical data for {symbol}")
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                logger.warning(
                    f"Rate limited on historical data for {symbol}: {e}")
                # Longer backoff for rate limits
                await asyncio.sleep(10.0)
            else:
                logger.debug(
                    f"Failed to get historical data for {symbol}: {e}")

        # Strategy 2: Try basic info (simplified approach for latest yfinance)
        info_data = {}
        try:
            logger.debug(f"Attempting basic info for {symbol}")

            # Single attempt with basic info - let yfinance handle retries internally
            info = ticker.info

            if info and isinstance(info, dict) and len(info) > 5:
                # Extract key metrics available in most responses
                info_data = {
                    "market_cap": info.get("marketCap"),
                    "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
                    "price_to_book": info.get("priceToBook"),
                    "dividend_yield": info.get("dividendYield"),
                    "beta": info.get("beta"),
                    "revenue_ttm": info.get("totalRevenue"),
                    "profit_margin": info.get("profitMargins")
                }

                # Count valid metrics
                valid_count = sum(
                    1 for v in info_data.values() if v is not None)
                if valid_count > 0:
                    logger.info(
                        f"Info success for {symbol}: {valid_count} metrics")
                else:
                    logger.debug(f"No valid metrics in info for {symbol}")
            else:
                logger.debug(f"Limited info response for {symbol}")

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                logger.warning(f"Rate limited getting info for {symbol}")
            elif "curl_cffi" in error_msg:
                logger.debug(
                    f"Session error for {symbol} - using yfinance defaults")
            else:
                logger.debug(f"Info error for {symbol}: {error_msg}")

        # Strategy 3: Try fast_info as lightweight fallback
        if not info_data:
            try:
                logger.debug(f"Trying fast_info fallback for {symbol}")
                fast_info = ticker.fast_info

                if fast_info:
                    # Get basic metrics from fast_info
                    try:
                        if hasattr(fast_info, 'market_cap') and fast_info.market_cap:
                            info_data['market_cap'] = fast_info.market_cap
                        if hasattr(fast_info, 'shares') and fast_info.shares:
                            info_data['shares_outstanding'] = fast_info.shares

                        if info_data:
                            logger.info(f"Fast info success for {symbol}")
                    except:
                        logger.debug(
                            f"Could not extract fast_info data for {symbol}")

            except Exception as e:
                logger.debug(f"Fast info failed for {symbol}: {e}")

        # Combine all collected data
        metrics_data = {**hist_data, **info_data}

        # Filter out None values
        metrics_data = {k: v for k, v in metrics_data.items()
                        if v is not None and v != 0}

        # Log final results
        if metrics_data:
            logger.info(
                f"Fundamentals completed for {symbol}: {len(metrics_data)} metrics collected: {list(metrics_data.keys())}")
        else:
            logger.warning(
                f"No fundamental data collected for {symbol} - Yahoo Finance may be blocking requests")

        return FinancialMetrics(**metrics_data)

    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Too Many Requests" in error_msg:
            logger.warning(
                f"Yahoo Finance rate limited for {symbol}: {error_msg}")
        elif "Expecting value" in error_msg:
            logger.warning(
                f"Yahoo Finance blocked requests for {symbol} - returning empty metrics")
        elif any(keyword in error_msg.lower() for keyword in ["disconnected", "cancelled", "closed", "connection"]):
            logger.info(
                f"🛑 Client disconnection detected during fundamentals fetch for {symbol}: {error_msg}")
        else:
            logger.error(f"Fundamentals error for {symbol}: {error_msg}")

        # Always return empty metrics rather than failing
        return FinancialMetrics()


@handle_api_errors
@create_retry_decorator()
@track_performance("source_finnhub_analyst_ratings")
async def fetch_analyst_ratings_finnhub(symbol: str) -> List[AnalystRating]:
    """Fetch analyst ratings from Finnhub with better error handling"""
    if not finnhub_client:
        logger.debug(
            "Finnhub client not configured - skipping analyst ratings")
        return []

    try:
        # Get recommendation trends (this should work on free tier)
        recommendations = finnhub_client.recommendation_trends(symbol)

        ratings = []
        if recommendations:
            for rec in recommendations[:5]:  # Limit to 5 most recent
                if rec.get("period"):
                    rating = AnalystRating(
                        firm="Consensus",
                        rating=f"Buy: {rec.get('buy', 0)}, Hold: {rec.get('hold', 0)}, Sell: {rec.get('sell', 0)}",
                        date=datetime.strptime(
                            rec["period"], "%Y-%m-%d") if rec.get("period") else None
                    )
                    ratings.append(rating)

        # Skip price targets as they require premium tier
        logger.debug(f"Got {len(ratings)} analyst ratings from Finnhub")
        return ratings

    except Exception as e:
        if "403" in str(e) or "don't have access" in str(e):
            logger.debug(
                f"Finnhub API access denied (check API key or upgrade plan): {e}")
        elif any(keyword in str(e).lower() for keyword in ["disconnected", "cancelled", "closed", "connection"]):
            logger.info(
                f"🛑 Client disconnection detected during analyst ratings fetch for {symbol}: {e}")
        else:
            logger.warning(f"Finnhub API error: {e}")
        return []


@handle_api_errors
@create_retry_decorator()
@track_performance("source_yfinance_earnings")
async def fetch_earnings_data_yf(symbol: str) -> List[EarningsData]:
    """Fetch earnings data from Yahoo Finance with correct methods"""
    # Add delay to avoid rate limiting
    await asyncio.sleep(1.5)

    earnings_data = []

    try:
        ticker = yf.Ticker(symbol)
        try:
            info = ticker.info
            if info and isinstance(info, dict):
                # Get trailing EPS if available
                if info.get("trailingEps"):
                    earning = EarningsData(
                        eps_actual=float(info["trailingEps"]),
                        quarter="TTM",
                        year=datetime.now().year
                    )
                    earnings_data.append(earning)

                # Get forward EPS if available
                if info.get("forwardEps"):
                    earning = EarningsData(
                        eps_estimate=float(info["forwardEps"]),
                        quarter="Forward",
                        year=datetime.now().year + 1
                    )
                    earnings_data.append(earning)

        except Exception as e:
            if "429" in str(e):
                logger.debug(f"Rate limited getting earnings info: {e}")
            else:
                logger.debug(f"Could not get earnings from info: {e}")

        # Try to get earnings from income statement
        try:
            income_stmt = ticker.income_stmt
            if income_stmt is not None and not income_stmt.empty:
                # Handle multi-index columns if present
                if hasattr(income_stmt, 'columns') and isinstance(income_stmt.columns, pd.MultiIndex):
                    income_stmt.columns = income_stmt.columns.droplevel(1)

                # Look for Net Income in the most recent quarters
                if 'Net Income' in income_stmt.index:
                    net_income_row = income_stmt.loc['Net Income']
                    for i, (date, value) in enumerate(net_income_row.head(4).items()):
                        if pd.notna(value) and i < 4:  # Limit to 4 quarters
                            try:
                                quarter = f"Q{((date.month-1)//3)+1}"
                                # Convert to EPS (approximate, would need shares outstanding)
                                earning = EarningsData(
                                    revenue_actual=float(
                                        value) if value > 0 else None,
                                    quarter=quarter,
                                    year=date.year
                                )
                                earnings_data.append(earning)
                            except Exception as e:
                                logger.debug(
                                    f"Error parsing income statement: {e}")
                                continue

        except Exception as e:
            logger.debug(f"Income statement not available: {e}")

        # Fallback: try quarterly_earnings
        if not earnings_data:
            try:
                quarterly = ticker.quarterly_earnings
                if quarterly is not None and not quarterly.empty:
                    # Handle multi-index if present
                    if hasattr(quarterly, 'columns') and isinstance(quarterly.columns, pd.MultiIndex):
                        quarterly.columns = quarterly.columns.droplevel(1)

                    for date, row in quarterly.head(4).iterrows():
                        try:
                            quarter = f"Q{((date.month-1)//3)+1}"
                            earning = EarningsData(
                                eps_actual=float(row["Earnings"]) if pd.notna(
                                    row.get("Earnings")) else None,
                                revenue_actual=float(row["Revenue"]) if pd.notna(
                                    row.get("Revenue")) else None,
                                quarter=quarter,
                                year=date.year
                            )
                            earnings_data.append(earning)
                        except Exception as e:
                            logger.debug(
                                f"Error parsing quarterly earnings: {e}")
                            continue

            except Exception as e:
                logger.debug(f"Quarterly earnings fallback failed: {e}")

    except Exception as e:
        if "429" in str(e) or "Too Many Requests" in str(e):
            logger.debug(f"Yahoo Finance rate limited for earnings: {e}")
        elif any(keyword in str(e).lower() for keyword in ["disconnected", "cancelled", "closed", "connection"]):
            logger.info(
                f"🛑 Client disconnection detected during earnings fetch for {symbol}: {e}")
        else:
            logger.debug(f"Error fetching earnings data: {e}")

    return earnings_data


async def get_company_name(symbol: str) -> Optional[str]:
    """Get company name with better fallback strategy"""
    try:
        validate_stock_symbol(symbol)

        # Add delay to reduce rate limiting
        await asyncio.sleep(0.5)

        ticker = yf.Ticker(symbol)

        # Try to get basic info with short timeout
        info = ticker.info
        if info and isinstance(info, dict):
            name = info.get("longName") or info.get("shortName")
            if name:
                return name

    except InvalidSymbolError:
        raise
    except Exception as e:
        if "429" in str(e):
            logger.debug(f"Rate limited getting company name for {symbol}")
        elif any(keyword in str(e).lower() for keyword in ["disconnected", "cancelled", "closed", "connection"]):
            logger.info(
                f"🛑 Client disconnection detected during company name fetch for {symbol}: {e}")
        else:
            logger.debug(f"Failed to get company name for {symbol}: {e}")

    return f"{symbol} Corporation"


# Main functions for agents
async def fetch_current_price(symbol: str) -> Dict[str, Any]:
    """Main function to fetch current price with fallback"""
    validate_stock_symbol(symbol)
    return await fetch_price_with_fallback(symbol)


async def fetch_financial_metrics(symbol: str) -> FinancialMetrics:
    """Main function to fetch comprehensive financial metrics"""
    validate_stock_symbol(symbol)
    return await fetch_fundamentals_yf(symbol)


async def fetch_analyst_ratings(symbol: str) -> List[AnalystRating]:
    """Main function to fetch analyst ratings"""
    validate_stock_symbol(symbol)
    return await fetch_analyst_ratings_finnhub(symbol)


async def fetch_earnings_data(symbol: str) -> List[EarningsData]:
    """Main function to fetch earnings data"""
    validate_stock_symbol(symbol)
    return await fetch_earnings_data_yf(symbol)

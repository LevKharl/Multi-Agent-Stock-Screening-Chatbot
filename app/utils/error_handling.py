import asyncio
import traceback
from typing import Any, Callable, Type, List
from functools import wraps
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from loguru import logger
from app.config import settings


class StockDataError(Exception):
    """Base exception for stock data operations"""
    pass


class APITimeoutError(StockDataError):
    """Raised when API requests timeout"""
    pass


class APIRateLimitError(StockDataError):
    """Raised when API rate limit is exceeded"""
    pass


class DataNotFoundError(StockDataError):
    """Raised when requested data is not found"""
    pass


class InvalidSymbolError(StockDataError):
    """Raised when stock symbol is invalid"""
    pass


class ServiceUnavailableError(StockDataError):
    """Raised when external service is unavailable"""
    pass


def create_retry_decorator(
    max_attempts: int = None,
    backoff_factor: float = None,
    retry_exceptions: List[Type[Exception]] = None
):
    """Create a retry decorator with configurable parameters"""
    max_attempts = max_attempts or settings.max_retries
    backoff_factor = backoff_factor or settings.retry_delay
    retry_exceptions = retry_exceptions or [
        APITimeoutError,
        ServiceUnavailableError,
        ConnectionError,
        asyncio.TimeoutError
    ]

    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=backoff_factor, min=1, max=10),
        retry=retry_if_exception_type(tuple(retry_exceptions)),
        before_sleep=before_sleep_log(logger, "WARNING")
    )


def handle_api_errors(func: Callable) -> Callable:
    """Decorator to handle and transform common API errors"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except asyncio.TimeoutError as e:
            logger.error(f"Timeout in {func.__name__}: {e}")
            raise APITimeoutError(f"Request timed out: {func.__name__}")
        except ConnectionError as e:
            # Handle connection errors more gracefully (often client disconnection)
            if any(keyword in str(e).lower() for keyword in ["disconnected", "cancelled", "closed"]):
                logger.info(
                    f"Client disconnection detected in {func.__name__}: {e}")
            else:
                logger.error(f"Connection error in {func.__name__}: {e}")
            raise ServiceUnavailableError(
                f"Service unavailable: {func.__name__}")
        except Exception as e:
            # Check if it's a client disconnection before logging as error
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ["disconnected", "cancelled", "closed", "client"]):
                logger.info(f"Client disconnection in {func.__name__}: {e}")
            else:
                # Log the full traceback for debugging only for real errors
                logger.error(
                    f"Unexpected error in {func.__name__}: {e}\n{traceback.format_exc()}")
            # Re-raise as StockDataError for consistent error handling
            raise StockDataError(f"Error in {func.__name__}: {str(e)}") from e

    return wrapper


class ErrorContext:
    """Context manager for tracking operation context in errors"""

    def __init__(self, operation: str, symbol: str = None, source: str = None):
        self.operation = operation
        self.symbol = symbol
        self.source = source
        self.start_time = None

    def __enter__(self):
        self.start_time = asyncio.get_event_loop().time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            duration = asyncio.get_event_loop().time() - self.start_time
            context_info = {
                "operation": self.operation,
                "duration": f"{duration:.2f}s",
                "symbol": self.symbol,
                "source": self.source
            }

            # Check if it's a client disconnection error
            error_str = str(exc_val).lower()
            if any(keyword in error_str for keyword in ["disconnected", "cancelled", "closed", "client", "connection"]):
                logger.info(
                    f"🛑 Client disconnection detected in {self.operation} for {self.symbol or 'unknown symbol'}",
                    extra={"context": context_info, "error": str(exc_val)}
                )
            else:
                logger.error(
                    f"Error in {self.operation}",
                    extra={"context": context_info, "error": str(exc_val)}
                )


class FallbackManager:
    """Manages fallback strategies for data sources"""

    def __init__(self):
        self.fallback_chains = {
            "price": ["alpha_vantage", "yfinance"],
            "fundamentals": ["yfinance", "alpha_vantage", "finnhub"],
            "sentiment": ["newsapi", "rss_feeds", "web_scraping"],
            "analyst_ratings": ["finnhub", "alpha_vantage"]
        }

    async def execute_with_fallback(
        self,
        data_type: str,
        symbol: str,
        primary_func: Callable,
        fallback_funcs: List[Callable],
        **kwargs
    ) -> Any:
        """Execute function with fallback chain"""
        errors = []

        # Try primary function first
        try:
            with ErrorContext(f"primary_{data_type}", symbol):
                result = await primary_func(symbol, **kwargs)
                if result is not None:
                    logger.info(
                        f"Primary source succeeded for {data_type}:{symbol}")
                    return result
        except Exception as e:
            errors.append(f"Primary source failed: {str(e)}")
            logger.warning(
                f"Primary source failed for {data_type}:{symbol}: {e}")

        # Try fallback functions
        for i, fallback_func in enumerate(fallback_funcs):
            try:
                with ErrorContext(f"fallback_{i}_{data_type}", symbol):
                    result = await fallback_func(symbol, **kwargs)
                    if result is not None:
                        logger.info(
                            f"Fallback {i+1} succeeded for {data_type}:{symbol}")
                        return result
            except Exception as e:
                errors.append(f"Fallback {i+1} failed: {str(e)}")
                logger.warning(
                    f"Fallback {i+1} failed for {data_type}:{symbol}: {e}")

        # All sources failed
        error_summary = "; ".join(errors)
        logger.error(
            f"All sources failed for {data_type}:{symbol}: {error_summary}")
        raise StockDataError(
            f"All data sources failed for {data_type}: {error_summary}")


class PartialDataHandler:
    """Handles cases where only partial data is available"""

    @staticmethod
    def merge_partial_results(results: List[dict], required_fields: List[str] = None) -> dict:
        """Merge multiple partial results into a complete dataset"""
        merged = {}
        missing_fields = []

        for result in results:
            if isinstance(result, dict):
                merged.update(
                    {k: v for k, v in result.items() if v is not None})

        if required_fields:
            missing_fields = [
                field for field in required_fields if field not in merged]
            if missing_fields:
                logger.warning(f"Missing required fields: {missing_fields}")

        merged["_missing_fields"] = missing_fields
        merged["_partial_data"] = len(missing_fields) > 0

        return merged

    @staticmethod
    def validate_minimum_data(data: dict, minimum_fields: List[str]) -> bool:
        """Validate that minimum required data is available"""
        available_fields = [
            field for field in minimum_fields if field in data and data[field] is not None]
        # At least 50% required
        return len(available_fields) >= len(minimum_fields) * 0.5


# Global instances
fallback_manager = FallbackManager()
partial_data_handler = PartialDataHandler()

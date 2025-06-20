from langgraph.graph import StateGraph
from typing import Annotated, TypedDict, List, Optional, Dict, Any, AsyncGenerator
from loguru import logger
import asyncio

from app.services.market_data import (
    fetch_current_price,
    fetch_financial_metrics,
    fetch_analyst_ratings,
    fetch_earnings_data,
    get_company_name
)
from app.services.sentiment import fetch_comprehensive_sentiment
from app.schemas import (
    StockRequest,
    StockResponse,
    FinancialMetrics,
    AnalystRating,
    EarningsData,
    SentimentItem,
    SentimentSummary,
    SentimentScore
)
from app.utils.error_handling import (
    ErrorContext,
    StockDataError
)

from app.utils.monitoring import track_performance

# Enhanced state for streaming


class GraphState(TypedDict, total=False):
    """Enhanced state for the multi-agent system with streaming support"""
    # Input
    symbol: Annotated[str, "broadcast"]

    # Price data
    price_data: Dict[str, Any]
    price_error: Optional[str]
    price_status: str  # 'pending', 'success', 'failed'

    # Financial metrics
    financial_metrics: FinancialMetrics
    fundamentals_error: Optional[str]
    fundamentals_status: str

    # Analyst data
    analyst_ratings: List[AnalystRating]
    analyst_error: Optional[str]
    analyst_status: str

    # Earnings data
    earnings_data: List[EarningsData]
    earnings_error: Optional[str]
    earnings_status: str

    # Sentiment data
    sentiment_items: List[SentimentItem]
    sentiment_summary: SentimentSummary
    sentiment_error: Optional[str]
    sentiment_status: str

    # Company info
    company_name: Optional[str]
    company_status: str

    # Coordination metadata
    agents_completed: List[str]
    validation_results: Dict[str, bool]
    overall_status: str  # 'initializing', 'processing', 'validating', 'complete', 'error'
    progress_percentage: int

    # Metadata
    data_sources: List[str]
    processing_errors: List[str]
    partial_data: bool


async def root_node(state: dict) -> dict:
    """Initialize the analysis with better state management"""
    logger.debug(f"Initializing analysis for {state['symbol']}")

    # Initialize all status fields
    enhanced_state = state.copy()
    enhanced_state.update({
        'price_status': 'pending',
        'fundamentals_status': 'pending',
        'analyst_status': 'pending',
        'sentiment_status': 'pending',
        'company_status': 'pending',
        'agents_completed': [],
        'validation_results': {},
        'overall_status': 'initializing',
        'progress_percentage': 0,
        'data_sources': [],
        'processing_errors': [],
        'partial_data': False
    })

    return enhanced_state


class CoordinatingAgent:
    """Enhanced coordinating agent with real-time validation and streaming"""

    def __init__(self):
        self.agent_validators = {
            'price': self._validate_price_data,
            'fundamentals': self._validate_financial_metrics,
            'analyst': self._validate_analyst_data,
            'sentiment': self._validate_sentiment_data,
            'company': self._validate_company_data
        }

    def _validate_price_data(self, state: dict) -> tuple[bool, str]:
        """Validate price data completeness and accuracy"""
        price_data = state.get('price_data')
        if not price_data:
            return False, "No price data available"

        required_fields = ['price', 'source']
        missing = [field for field in required_fields if field not in price_data]
        if missing:
            return False, f"Missing required fields: {missing}"

        if not isinstance(price_data['price'], (int, float)) or price_data['price'] <= 0:
            return False, "Invalid price value"

        return True, "Price data validated successfully"

    def _validate_financial_metrics(self, state: dict) -> tuple[bool, str]:
        """Validate financial metrics"""
        metrics = state.get('financial_metrics')
        if not metrics:
            return False, "No financial metrics available (rate limited)"

        # For rate-limited data, this is acceptable
        return True, "Financial metrics processed (may be limited due to API constraints)"

    def _validate_analyst_data(self, state: dict) -> tuple[bool, str]:
        """Validate analyst ratings"""
        ratings = state.get('analyst_ratings', [])
        if not ratings:
            return False, "No analyst ratings available"

        # Check if ratings have proper structure
        for rating in ratings:
            # Handle both dict and Pydantic model formats
            if hasattr(rating, 'firm'):  # Pydantic model
                if not rating.firm or not rating.rating:
                    return False, "Invalid rating structure"
            elif isinstance(rating, dict):  # Dictionary
                if not rating.get('firm') or not rating.get('rating'):
                    return False, "Invalid rating structure"
            else:
                return False, "Unknown rating format"

        return True, f"Validated {len(ratings)} analyst ratings"

    def _validate_sentiment_data(self, state: dict) -> tuple[bool, str]:
        """Validate sentiment analysis results"""
        sentiment_items = state.get('sentiment_items', [])
        sentiment_summary = state.get('sentiment_summary')

        if not sentiment_items and not sentiment_summary:
            return False, "No sentiment data available"

        if sentiment_summary and not hasattr(sentiment_summary, 'overall_score'):
            return False, "Invalid sentiment summary structure"

        return True, f"Validated sentiment data with {len(sentiment_items)} articles"

    def _validate_company_data(self, state: dict) -> tuple[bool, str]:
        """Validate company information"""
        company_name = state.get('company_name')
        if not company_name:
            return False, "Company name not available"

        return True, f"Company validated: {company_name}"

    async def validate_agent_result(self, agent_name: str, state: dict) -> dict:
        """Validate individual agent results and update state"""
        validator = self.agent_validators.get(agent_name)
        if not validator:
            logger.warning(f"No validator for agent: {agent_name}")
            return state

        is_valid, message = validator(state)

        # Update validation results
        validation_results = state.get('validation_results', {})
        validation_results[agent_name] = is_valid

        state['validation_results'] = validation_results

        if is_valid:
            logger.info(f"✅ {agent_name.title()} agent validation: {message}")
        else:
            logger.warning(
                f"⚠️ {agent_name.title()} agent validation failed: {message}")
            # Add to processing errors but continue
            errors = state.get('processing_errors', [])
            errors.append(f"{agent_name}: {message}")
            state['processing_errors'] = errors

        return state

    async def calculate_progress(self, state: dict) -> int:
        """Calculate overall progress based on completed agents"""
        completed = state.get('agents_completed', [])
        total_agents = 5  # price, fundamentals, analyst, sentiment, company

        base_progress = (len(completed) / total_agents) * \
            85  # 85% for agent completion

        # Add validation progress
        validation_results = state.get('validation_results', {})
        validation_progress = (len(validation_results) /
                               total_agents) * 10  # 10% for validation

        # Final 5% for response formatting
        formatting_progress = 5 if len(completed) == total_agents else 0

        return min(100, int(base_progress + validation_progress + formatting_progress))


coordinating_agent = CoordinatingAgent()


@track_performance("agent_price")
async def price_agent(state: dict) -> dict:
    """Enhanced price agent with status tracking"""
    symbol = state["symbol"]
    result = state.copy()
    result['price_status'] = 'processing'

    with ErrorContext("price_agent", symbol):
        try:
            # Fetch comprehensive price data
            price_data = await fetch_current_price(symbol)

            # Add data source to tracking
            data_sources = state.get("data_sources", []).copy()
            data_sources.append(price_data.get("source", "unknown"))

            # Return the complete updated state
            result.update({
                "price_data": price_data,
                "data_sources": data_sources,
                "price_status": "success"
            })

            # Add to completed agents
            completed = result.get('agents_completed', [])
            if 'price' not in completed:
                completed.append('price')
            result['agents_completed'] = completed

            logger.info(
                f"Price agent succeeded for {symbol}: ${price_data.get('price', 'N/A')}")
            return result

        except Exception as e:
            logger.error(f"Price agent failed for {symbol}: {e}")
            errors = state.get("processing_errors", []).copy()
            errors.append(f"Price fetch failed: {str(e)}")

            result.update({
                "price_error": str(e),
                "processing_errors": errors,
                "partial_data": True,
                "price_status": "failed"
            })
            return result


@track_performance("agent_fundamentals")
async def fundamentals_agent(state: dict) -> dict:
    """Enhanced fundamentals agent with status tracking"""
    symbol = state["symbol"]
    result = state.copy()
    result['fundamentals_status'] = 'processing'

    with ErrorContext("fundamentals_agent", symbol):
        try:
            # Fetch comprehensive financial metrics
            financial_metrics = await fetch_financial_metrics(symbol)

            # Add data source to tracking
            data_sources = state.get("data_sources", []).copy()
            data_sources.append("yfinance_fundamentals")

            result.update({
                "financial_metrics": financial_metrics,
                "data_sources": data_sources,
                "fundamentals_status": "success"
            })

            # Add to completed agents
            completed = result.get('agents_completed', [])
            if 'fundamentals' not in completed:
                completed.append('fundamentals')
            result['agents_completed'] = completed

            logger.info(f"Fundamentals agent succeeded for {symbol}")
            return result

        except Exception as e:
            logger.error(f"Fundamentals agent failed for {symbol}: {e}")
            errors = state.get("processing_errors", []).copy()
            errors.append(f"Fundamentals fetch failed: {str(e)}")

            # Provide empty financial metrics as fallback
            empty_metrics = FinancialMetrics()

            result.update({
                "financial_metrics": empty_metrics,
                "fundamentals_error": str(e),
                "processing_errors": errors,
                "partial_data": True,
                "fundamentals_status": "failed"
            })
            return result


@track_performance("agent_analyst")
async def analyst_agent(state: dict) -> dict:
    """Enhanced analyst agent with status tracking"""
    symbol = state["symbol"]
    result = state.copy()
    result['analyst_status'] = 'processing'

    with ErrorContext("analyst_agent", symbol):
        try:
            # Fetch analyst ratings and earnings data
            analyst_ratings = await fetch_analyst_ratings(symbol)
            earnings_data = await fetch_earnings_data(symbol)

            # Add data sources to tracking
            data_sources = state.get("data_sources", []).copy()
            if analyst_ratings:
                data_sources.append("finnhub_analysts")
            if earnings_data:
                data_sources.append("yfinance_earnings")

            result.update({
                "analyst_ratings": analyst_ratings,
                "earnings_data": earnings_data,
                "data_sources": data_sources,
                "analyst_status": "success"
            })

            # Add to completed agents
            completed = result.get('agents_completed', [])
            if 'analyst' not in completed:
                completed.append('analyst')
            result['agents_completed'] = completed

            logger.info(
                f"Analyst agent succeeded for {symbol}: {len(analyst_ratings)} ratings, {len(earnings_data)} earnings")
            return result

        except Exception as e:
            logger.error(f"Analyst agent failed for {symbol}: {e}")
            errors = state.get("processing_errors", []).copy()
            errors.append(f"Analyst data fetch failed: {str(e)}")

            result.update({
                "analyst_ratings": [],
                "earnings_data": [],
                "analyst_error": str(e),
                "processing_errors": errors,
                "partial_data": True,
                "analyst_status": "failed"
            })
            return result


@track_performance("agent_sentiment")
async def sentiment_agent(state: dict) -> dict:
    """Enhanced sentiment agent with status tracking"""
    symbol = state["symbol"]
    result = state.copy()
    result['sentiment_status'] = 'processing'

    with ErrorContext("sentiment_agent", symbol):
        try:
            # Fetch comprehensive sentiment analysis
            sentiment_items, sentiment_summary = await fetch_comprehensive_sentiment(symbol)

            # Add data sources to tracking
            data_sources = state.get("data_sources", []).copy()
            data_sources.extend(["newsapi", "rss_feeds"])

            result.update({
                "sentiment_items": sentiment_items,
                "sentiment_summary": sentiment_summary,
                "data_sources": data_sources,
                "sentiment_status": "success"
            })

            # Add to completed agents
            completed = result.get('agents_completed', [])
            if 'sentiment' not in completed:
                completed.append('sentiment')
            result['agents_completed'] = completed

            logger.info(
                f"Sentiment agent succeeded for {symbol}: {len(sentiment_items)} articles, {sentiment_summary.overall_score.value} sentiment")
            return result

        except Exception as e:
            logger.error(f"Sentiment agent failed for {symbol}: {e}")
            errors = state.get("processing_errors", []).copy()
            errors.append(f"Sentiment analysis failed: {str(e)}")

            # Provide empty sentiment as fallback
            empty_sentiment = SentimentSummary(
                overall_score=SentimentScore.NEUTRAL,
                confidence=0.0,
                positive_count=0,
                negative_count=0,
                neutral_count=0,
                summary_text="Sentiment analysis unavailable"
            )

            result.update({
                "sentiment_items": [],
                "sentiment_summary": empty_sentiment,
                "sentiment_error": str(e),
                "processing_errors": errors,
                "partial_data": True,
                "sentiment_status": "failed"
            })
            return result


@track_performance("agent_company_info")
async def company_info_agent(state: dict) -> dict:
    """Enhanced company info agent with status tracking"""
    symbol = state["symbol"]
    result = state.copy()
    result['company_status'] = 'processing'

    with ErrorContext("company_info_agent", symbol):
        try:
            company_name = await get_company_name(symbol)

            result.update({
                "company_name": company_name,
                "company_status": "success"
            })

            # Add to completed agents
            completed = result.get('agents_completed', [])
            if 'company' not in completed:
                completed.append('company')
            result['agents_completed'] = completed

            logger.info(
                f"Company info agent succeeded for {symbol}: {company_name}")
            return result

        except Exception as e:
            logger.warning(f"Company info agent failed for {symbol}: {e}")
            result.update({
                "company_name": None,
                "company_status": "failed"
            })
            return result


# Helper functions for response formatting
def calculate_consensus_rating(ratings: List[AnalystRating]) -> Optional[str]:
    """Calculate consensus rating from analyst ratings"""
    if not ratings:
        return None

    # Simple consensus logic - this could be enhanced
    rating_counts = {}
    for rating in ratings:
        rating_text = rating.rating.upper()
        if "BUY" in rating_text:
            rating_counts["BUY"] = rating_counts.get("BUY", 0) + 1
        elif "HOLD" in rating_text:
            rating_counts["HOLD"] = rating_counts.get("HOLD", 0) + 1
        elif "SELL" in rating_text:
            rating_counts["SELL"] = rating_counts.get("SELL", 0) + 1

    if rating_counts:
        consensus = max(rating_counts, key=rating_counts.get)
        return consensus

    return "HOLD"  # Default consensus


async def stream_coordinated_analysis(symbol: str) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream coordinated multi-agent analysis with real-time validation"""

    # Validate symbol format first before doing anything else
    from app.services.market_data import validate_stock_symbol
    validate_stock_symbol(symbol)

    # Initialize state
    state = {"symbol": symbol}
    state = await root_node(state)

    yield {
        "status": "started",
        "message": f"🚀 Starting coordinated analysis for {symbol}",
        "progress": 0,
        "agents_status": {
            "price": "pending",
            "fundamentals": "pending",
            "analyst": "pending",
            "sentiment": "pending",
            "company": "pending"
        }
    }

    # Run agents sequentially with validation
    agents = [
        ("price", price_agent, "📈 Fetching real-time price data..."),
        ("fundamentals", fundamentals_agent, "💼 Analyzing financial metrics..."),
        ("analyst", analyst_agent, "🎯 Gathering analyst ratings..."),
        ("sentiment", sentiment_agent, "📰 Analyzing market sentiment..."),
        ("company", company_info_agent, "🏢 Retrieving company information...")
    ]

    for i, (agent_name, agent_func, message) in enumerate(agents):
        # Update progress
        progress = int((i / len(agents)) * 80)  # 80% for agents
        yield {
            "status": "processing",
            "message": message,
            "progress": progress,
            "current_agent": agent_name
        }

        # Run agent
        state = await agent_func(state)

        # Validate results
        state = await coordinating_agent.validate_agent_result(agent_name, state)

        # Calculate dynamic progress
        progress = await coordinating_agent.calculate_progress(state)

        # Stream partial results
        validation = state.get('validation_results', {}).get(agent_name, False)
        agent_status = "success" if validation else "warning"

        yield {
            "status": "agent_complete",
            "message": f"✅ {agent_name.title()} agent completed",
            "progress": progress,
            "agent": agent_name,
            "agent_status": agent_status,
            "partial_data": {
                agent_name: state.get(
                    f"{agent_name}_data") or state.get(agent_name)
            }
        }

    # Final validation and response formatting
    yield {
        "status": "finalizing",
        "message": "🔄 Validating results and formatting response...",
        "progress": 95
    }

    try:
        response = format_response(symbol, state)

        # Convert to dict and handle datetime serialization
        response_dict = response.model_dump(mode='json')

        yield {
            "status": "complete",
            "message": f"✅ Analysis complete for {symbol}",
            "progress": 100,
            "data": response_dict,
            "validation_summary": state.get('validation_results', {}),
            "data_sources": state.get('data_sources', [])
        }

    except Exception as e:
        logger.error(f"Response formatting failed: {e}")
        yield {
            "status": "error",
            "message": f"❌ Failed to format final response: {str(e)}",
            "progress": 100,
            "error": str(e)
        }


def format_response(symbol: str, state: dict) -> StockResponse:
    """Enhanced response formatter with validation and partial data support"""
    with ErrorContext("response_formatting", symbol):
        # Find price data - but allow partial responses without it
        price_data = state.get("price_data")

        # Check if we have ANY valid data to create a response
        has_fundamentals = state.get("financial_metrics") is not None
        has_analyst = state.get("analyst_ratings") and len(
            state.get("analyst_ratings", [])) > 0
        has_sentiment = state.get("sentiment_items") and len(
            state.get("sentiment_items", [])) > 0
        has_company = state.get("company_name") is not None

        # If we have no data at all, that's an error
        if not any([price_data, has_fundamentals, has_analyst, has_sentiment, has_company]):
            logger.error(
                f"No data available for {symbol}. Full state: {state}")
            raise StockDataError("No data available - all agents failed")

        # Handle missing price data gracefully
        if not price_data:
            logger.warning(
                f"No price data available for {symbol}, creating partial response")
            price = None
            currency = "USD"
            change = None
            change_percent = None
            volume = None
        else:
            # Validate price data has required fields
            if not isinstance(price_data, dict) or "price" not in price_data:
                logger.warning(
                    f"Invalid price data format: {price_data}, using defaults")
                price = None
                currency = "USD"
                change = None
                change_percent = None
                volume = None
            else:
                price = price_data["price"]
                currency = price_data.get("currency", "USD")
                change = price_data.get("change")
                change_percent = price_data.get("change_percent")
                volume = price_data.get("volume")

        financial_metrics = state.get("financial_metrics", [])
        analyst_ratings = state.get("analyst_ratings", [])
        earnings_data = state.get("earnings_data", [])
        sentiment_items = state.get("sentiment_items", [])
        sentiment_summary = state.get("sentiment_summary", [])

        # Ensure we have a sentiment summary
        if not sentiment_summary:
            sentiment_summary = SentimentSummary(
                overall_score=SentimentScore.NEUTRAL,
                confidence=0.0,
                positive_count=0,
                negative_count=0,
                neutral_count=0,
                summary_text="No sentiment data available"
            )

        # Get unique data sources
        data_sources = list(set(state.get("data_sources", [])))

        response = StockResponse(
            symbol=symbol,
            company_name=state.get("company_name", f"{symbol} Corporation"),
            price=price,
            currency=currency,
            change=change,
            change_percent=change_percent,
            volume=volume,
            financial_metrics=financial_metrics,
            analyst_ratings=analyst_ratings,
            earnings_data=earnings_data,
            sentiment_items=sentiment_items,
            sentiment_summary=sentiment_summary,
            data_sources=data_sources
        )

        # Log processing summary
        errors = state.get("processing_errors", [])
        if errors:
            logger.warning(
                f"Response generated with errors for {symbol}: {errors}")
        else:
            logger.info(f"Complete response generated for {symbol}")

        # Log what data we actually have
        data_availability = {
            "price": price is not None,
            "fundamentals": has_fundamentals,
            "analyst": has_analyst,
            "sentiment": has_sentiment,
            "company": has_company
        }
        logger.info(f"Data availability for {symbol}: {data_availability}")

        return response


# Simplified graph with a single orchestrating agent
graph = StateGraph(GraphState)

# Single orchestrating agent that runs all tasks concurrently


@track_performance("orchestrating_agent")
async def orchestrating_agent(state: dict) -> dict:
    """Run all agents concurrently with proper state merging"""
    symbol = state["symbol"]

    logger.debug(f"Starting orchestrating agent for {symbol}")

    # Run all agents concurrently
    tasks = [
        price_agent(state),
        fundamentals_agent(state),
        analyst_agent(state),
        sentiment_agent(state),
        company_info_agent(state)
    ]

    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Start with the original state
    final_state = state.copy()

    logger.debug(f"Got {len(results)} results from agents")

    # Merge all results properly - only update if the value is NOT None
    for i, result in enumerate(results):
        if isinstance(result, dict):
            logger.debug(f"Merging result {i}: keys = {list(result.keys())}")
            # Deep merge the result into final_state
            for key, value in result.items():
                if key == "data_sources":
                    # Merge data sources lists
                    existing = final_state.get("data_sources", [])
                    new_sources = value if isinstance(value, list) else []
                    final_state["data_sources"] = list(
                        set(existing + new_sources))
                elif key == "processing_errors":
                    # Merge error lists
                    existing = final_state.get("processing_errors", [])
                    new_errors = value if isinstance(value, list) else []
                    final_state["processing_errors"] = existing + new_errors
                elif value is not None:
                    # Only update if the value is not None - preserve successful data
                    final_state[key] = value
                    logger.debug(f"Updated {key} with value: {type(value)}")
        elif isinstance(result, Exception):
            # Log error but continue
            logger.error(f"Agent {i} failed with exception: {result}")
            if "processing_errors" not in final_state:
                final_state["processing_errors"] = []
            final_state["processing_errors"].append(str(result))

    logger.debug(f"Final state keys: {list(final_state.keys())}")
    logger.debug(f"Final state price_data: {final_state.get('price_data')}")

    return final_state

# Add nodes
graph.add_node("root", root_node)
graph.add_node("orchestrate", orchestrating_agent)

# Simple linear flow
graph.add_edge("root", "orchestrate")

# Set entry and finish points
graph.set_entry_point("root")
graph.set_finish_point("orchestrate")

# Compile the graph
compiled_graph = graph.compile()


# Main orchestration function
@track_performance("orchestration")
async def orchestrate(req: StockRequest) -> StockResponse:
    """Enhanced orchestration with proper error handling and monitoring"""
    symbol = req.symbol.upper()

    try:
        with ErrorContext("orchestration", symbol):
            # Run the multi-agent system
            result = await compiled_graph.ainvoke({"symbol": symbol})

            # Format and return the response
            response = format_response(symbol, result)

            # Record success metrics
            logger.info(f"Successfully orchestrated response for {symbol}")
            return response

    except Exception as e:
        logger.error(f"Orchestration failed for {symbol}: {e}")
        raise StockDataError(
            f"Failed to process stock data for {symbol}: {str(e)}") from e

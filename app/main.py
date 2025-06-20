import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from loguru import logger
import json
from app.schemas import StockRequest
from app.agents import stream_coordinated_analysis
from app.utils.monitoring import metrics
from app.utils.error_handling import StockDataError, InvalidSymbolError, APITimeoutError
from app.config import settings


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    services: dict


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting Multi-Agent Stock Screening API")

    # Start metrics server
    metrics.start_metrics_server()

    # Configure logging
    logger.add(
        "logs/api.log",
        rotation="100 MB",
        retention="30 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )

    logger.info("API startup complete")

    yield

    # Shutdown
    logger.info("Shutting down API")
    logger.info("API shutdown complete")


app = FastAPI(
    title="Multi-Agent Stock Screening Bot",
    description="A comprehensive stock analysis API using multiple AI agents",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def track_request_metrics(request: Request, response_time: float, status_code: int):
    """Track request metrics"""
    endpoint = request.url.path
    status = "success" if status_code < 400 else "error"
    metrics.record_request(endpoint, status, response_time)


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    """Middleware to track request timing and metrics"""
    start_time = time.time()

    try:
        # Process request
        response = await call_next(request)

        # Track metrics
        response_time = time.time() - start_time
        await track_request_metrics(request, response_time, response.status_code)

        return response

    except HTTPException as e:
        # Track failed requests
        response_time = time.time() - start_time
        await track_request_metrics(request, response_time, e.status_code)
        raise
    except Exception as e:
        # Track unexpected errors
        response_time = time.time() - start_time
        await track_request_metrics(request, response_time, 500)
        raise


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    services = {
        "metrics": "enabled" if settings.enable_metrics else "disabled"
    }

    return HealthResponse(
        status="healthy",
        services=services
    )


@app.post("/analyze-stream", summary="Get real-time stock analysis updates via SSE")
async def analyze_stock_stream(req: StockRequest, request: Request):
    """Get real-time stock analysis updates via Server-Sent Events with coordinating agent validation
    - Real-time price data
    - Financial metrics and ratios
    - Analyst ratings and price targets
    - Earnings data and forecasts
    """

    async def event_generator():
        try:
            symbol = req.symbol.upper()

            # Track the symbol query
            metrics.record_symbol_query(symbol)

            async for update in stream_coordinated_analysis(symbol):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(
                        f"🛑 Client disconnected during analysis for {symbol} - stopping analysis")
                    # Send a cancellation message to indicate clean stop
                    yield f"data: {json.dumps({'status': 'cancelled', 'message': 'Analysis stopped - client disconnected'})}\n\n"
                    break

                yield f"data: {json.dumps(update)}\n\n"

        except InvalidSymbolError as e:
            error_data = {"status": "error",
                          "error": "invalid_symbol", "message": str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"
        except ConnectionError as e:
            # Handle connection errors gracefully (often client disconnection)
            logger.info(
                f"🔌 Connection terminated for {req.symbol} (likely user stopped): {e}")
            yield f"data: {json.dumps({'status': 'cancelled', 'message': 'Analysis stopped by user'})}\n\n"
        except Exception as e:
            # Only log as error if it's not a client disconnection
            if "client disconnected" not in str(e).lower() and "connection" not in str(e).lower():
                logger.error(f"Streaming error for {req.symbol}: {e}")
                error_data = {"error": "internal_error",
                              "message": "An error occurred during analysis"}
                yield f"data: {json.dumps(error_data)}\n\n"
            else:
                logger.info(
                    f"🛑 Analysis for {req.symbol} stopped by client disconnection")

    return StreamingResponse(
        event_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/metrics", summary="API metrics (if enabled)")
async def get_metrics():
    """Get API metrics (if metrics are enabled)"""
    if not settings.enable_metrics:
        raise HTTPException(status_code=404, detail="Metrics disabled")

    return {"message": f"Metrics available at http://localhost:{settings.metrics_port}/metrics"}


@app.exception_handler(StockDataError)
async def stock_data_exception_handler(request: Request, exc: StockDataError):
    return JSONResponse(
        status_code=502,
        content={"error": "stock_data_error", "detail": str(exc)}
    )


@app.exception_handler(InvalidSymbolError)
async def invalid_symbol_exception_handler(request: Request, exc: InvalidSymbolError):
    return JSONResponse(
        status_code=400,
        content={"error": "invalid_symbol", "detail": str(exc)}
    )


@app.exception_handler(APITimeoutError)
async def timeout_exception_handler(request: Request, exc: APITimeoutError):
    return JSONResponse(
        status_code=504,
        content={"error": "timeout", "detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

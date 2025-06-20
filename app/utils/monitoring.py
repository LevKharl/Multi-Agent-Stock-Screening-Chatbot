import time
from typing import Dict, Optional
from datetime import datetime
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from loguru import logger
from app.config import settings


class MetricsCollector:
    def __init__(self):
        # Request metrics
        self.request_count = Counter(
            'stock_api_requests_total',
            'Total number of stock API requests',
            ['endpoint', 'status']
        )

        self.request_duration = Histogram(
            'stock_api_request_duration_seconds',
            'Request duration in seconds',
            ['endpoint']
        )

        # Agent metrics
        self.agent_execution_time = Histogram(
            'agent_execution_duration_seconds',
            'Agent execution duration in seconds',
            ['agent_name']
        )

        self.agent_success_rate = Counter(
            'agent_executions_total',
            'Total agent executions',
            ['agent_name', 'status']
        )

        # Data source metrics
        self.data_source_requests = Counter(
            'data_source_requests_total',
            'Total requests to data sources',
            ['source', 'status']
        )

        self.data_source_latency = Histogram(
            'data_source_latency_seconds',
            'Data source response latency',
            ['source']
        )

        # Business metrics
        self.active_symbols = Gauge(
            'active_stock_symbols',
            'Number of unique symbols queried'
        )

        self._symbol_cache: Dict[str, datetime] = {}
        self._metrics_server_started = False

    def start_metrics_server(self):
        """Start Prometheus metrics server"""
        if settings.enable_metrics and not self._metrics_server_started:
            try:
                start_http_server(settings.metrics_port)
                self._metrics_server_started = True
                logger.info(
                    f"Metrics server started on port {settings.metrics_port}")
            except Exception as e:
                logger.error(f"Failed to start metrics server: {e}")

    def record_request(self, endpoint: str, status: str, duration: float):
        """Record API request metrics"""
        self.request_count.labels(endpoint=endpoint, status=status).inc()
        self.request_duration.labels(endpoint=endpoint).observe(duration)

    def record_agent_execution(self, agent_name: str, duration: float, success: bool):
        """Record agent execution metrics"""
        status = "success" if success else "failure"
        self.agent_execution_time.labels(
            agent_name=agent_name).observe(duration)
        self.agent_success_rate.labels(
            agent_name=agent_name, status=status).inc()

    def record_data_source_request(self, source: str, latency: float, success: bool):
        """Record data source request metrics"""
        status = "success" if success else "failure"
        self.data_source_requests.labels(source=source, status=status).inc()
        self.data_source_latency.labels(source=source).observe(latency)

    def record_symbol_query(self, symbol: str):
        """Record unique symbol queries"""
        current_time = datetime.utcnow()
        if symbol not in self._symbol_cache:
            self._symbol_cache[symbol] = current_time
            self.active_symbols.set(len(self._symbol_cache))

        # Clean old entries (older than 24 hours)
        cutoff = current_time.timestamp() - 86400
        self._symbol_cache = {
            sym: ts for sym, ts in self._symbol_cache.items()
            if ts.timestamp() > cutoff
        }
        self.active_symbols.set(len(self._symbol_cache))


class PerformanceTracker:
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.start_time: Optional[float] = None
        self.operation_name: str = ""

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            success = exc_type is None

            if self.operation_name.startswith("agent_"):
                agent_name = self.operation_name.replace("agent_", "")
                self.metrics.record_agent_execution(
                    agent_name, duration, success)
            elif self.operation_name.startswith("source_"):
                source_name = self.operation_name.replace("source_", "")
                self.metrics.record_data_source_request(
                    source_name, duration, success)

    def set_operation(self, name: str):
        self.operation_name = name
        return self


# Global metrics instance
metrics = MetricsCollector()


def track_performance(operation_name: str):
    """Decorator for tracking performance"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with PerformanceTracker(metrics) as tracker:
                tracker.set_operation(operation_name)
                return await func(*args, **kwargs)
        return wrapper
    return decorator

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Required API keys for external services
    alpha_vantage_key: str = Field(..., env='ALPHA_VANTAGE_KEY')
    newsapi_key: str = Field(..., env='NEWSAPI_KEY')
    openai_api_key: str = Field(..., env='OPENAI_API_KEY')
    finnhub_key: str = Field("", env='FINNHUB_KEY')

    # Application settings
    log_level: str = Field("INFO", env='LOG_LEVEL')
    cors_origins: str = Field("*", env='CORS_ORIGINS')

    # HTTP and retry settings
    http_timeout: int = Field(15, env='HTTP_TIMEOUT')
    max_retries: int = Field(3, env='MAX_RETRIES')
    retry_delay: float = Field(1.0, env='RETRY_DELAY')

    # Basic rate limiting (requests per hour)
    rate_limit_requests: int = Field(100, env='RATE_LIMIT_REQUESTS')
    rate_limit_window: int = Field(3600, env='RATE_LIMIT_WINDOW')

    # Monitoring
    enable_metrics: bool = Field(True, env='ENABLE_METRICS')
    metrics_port: int = Field(9090, env='METRICS_PORT')

    # Sentiment analysis settings
    use_openai_sentiment: bool = Field(True, env='USE_OPENAI_SENTIMENT')
    openai_model: str = Field("gpt-4.1-nano-2025-04-14", env='OPENAI_MODEL')
    sentiment_temperature: float = Field(0.1, env='SENTIMENT_TEMPERATURE')

    # News settings
    news_days_back: int = Field(7, env='NEWS_DAYS_BACK')
    max_news_articles: int = Field(20, env='MAX_NEWS_ARTICLES')

    # Application metadata
    app_name: str = Field("Multi-Agent Stock Screening API")
    version: str = Field("1.0.0")

    model_config = SettingsConfigDict(env_file=".env", extra='ignore')


settings = Settings()

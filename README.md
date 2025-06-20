# 📈 Multi-Agent Stock Screening Chatbot

A comprehensive, production-ready stock analysis platform that leverages multiple AI agents to provide real-time market data, financial analysis, analyst ratings, and sentiment analysis for NASDAQ stocks using LangChain/LangGraph architecture.

## 🏗️ Architecture

The system uses a **multi-agent architecture** built with LangChain/LangGraph where specialized agents work in parallel to gather different types of financial data:

```
┌─────────────────┐    ┌──────────────────┐
│   User Request  │    │   RESTful API    │
│   (Stock Symbol)│───▶│   (FastAPI)      │
└─────────────────┘    └────────┬─────────┘
                                │
                       ┌────────▼────────┐
                       │  Orchestrator   │
                       │     Agent       │
                       └────────┬────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
    ┌───────▼──────┐   ┌────────▼──────┐   ┌───────▼──────┐
    │ Price Agent  │   │Fundamentals   │   │ Sentiment    │
    │              │   │   Agent       │   │   Agent      │
    │• Real-time   │   │• Financial    │   │• News        │
    │  pricing     │   │  metrics      │   │  analysis    │
    │• Volume      │   │• Ratios       │   │• Social      │
    │• Changes     │   │• Balance      │   │  sentiment   │
    └──────────────┘   │  sheet data   │   │• AI analysis │
            │          └───────────────┘   └──────────────┘
            │                   │                   │
    ┌───────▼──────┐   ┌────────▼──────┐            │
    │ Analyst      │   │ Company Info  │            │
    │   Agent      │   │    Agent      │            │
    │              │   │               │            │
    │• Ratings     │   │• Company name │            │
    │• Price       │   │• Business     │            │
    │  targets     │   │  details      │            │
    │• Earnings    │   └───────────────┘            │
    └──────────────┘                                │
            │                                       │
            └──────────────────┬────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Response Formatter │
                    │                     │
                    │ • Aggregates data   │
                    │ • Calculates        │
                    │   derived metrics   │
                    │ • Formats JSON      │
                    └─────────────────────┘
```

## 🎯 Features

#### **1. Multi-Agent Chatbot**
- ✅ **LangChain/LangGraph Architecture**: StateGraph-based agent orchestration
- ✅ **Specialized Agents**: 5 dedicated agents for different data types
- ✅ **Agent Communication**: Results aggregated by coordinating agent
- ✅ **Real-time Streaming**: Server-Sent Events for live updates

#### **2. Knowledge Source Integration**
- ✅ **Real-time APIs**: Alpha Vantage, Yahoo Finance, Finnhub, NewsAPI
- ✅ **Fallback Chains**: Multiple sources per data type with automatic failover
- ✅ **Rate Limit Management**: Smart throttling and retry mechanisms
- ✅ **Data Validation**: Comprehensive validation for each data source

#### **3. RESTful API**
- ✅ **FastAPI Framework**: High-performance async API
- ✅ **Structured Responses**: JSON with complete financial data
- ✅ **Input Validation**: Pydantic models with regex validation
- ✅ **Error Handling**: Comprehensive error classification and responses

#### **4. Web Interface**
- ✅ **Streamlit UI**: Modern, responsive web interface
- ✅ **Real-time Updates**: Live data visualization
- ✅ **User-friendly Design**: Intuitive stock analysis display

#### **5. Advanced Features**
- ✅ **Fallback Logic**: Price data fallback (Alpha Vantage → Yahoo Finance)
- ✅ **Monitoring & Analytics**: Prometheus metrics and performance tracking
- ✅ **Rate Limiting**: Basic IP-based rate limiting
- ✅ **Error Handling**: Comprehensive retry mechanisms and graceful degradation

## 📊 Data Sources & APIs

### Primary Data Sources
- **Stock Prices**: Alpha Vantage (primary) → Yahoo Finance (fallback)
- **Financial Metrics**: Yahoo Finance
- **Analyst Ratings**: Finnhub
- **News Sentiment**: NewsAPI + RSS feeds + OpenAI GPT analysis
- **Company Info**: Yahoo Finance

### Sentiment Analysis Pipeline
1. **News Aggregation**: NewsAPI + RSS feeds from major financial sources
2. **Multi-method Analysis**:
   - VADER sentiment analyzer
   - Rule-based pattern matching
   - OpenAI GPT-4 analysis and summarization
3. **Confidence Scoring**: Weighted average with confidence intervals

## 📋 Requirements

### **Environment Setup**

```bash
# Python 3.11+
python --version

# Install dependencies
pip install -r requirements.txt
```

### **Required API Keys**

1. **Alpha Vantage** : [Get free key](https://www.alphavantage.co/support/#api-key)
2. **NewsAPI** : [Get free key](https://newsapi.org/register)
3. **OpenAI** : [Get API key](https://platform.openai.com/api-keys)
4. **Finnhub** : [Get free key](https://finnhub.io/register)

### **Optional Services**


- **Prometheus** (for metrics): Automatically started on port 9090

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd Multi-Agent-Stock-Screening-Chatbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy and edit environment file
cp .env.example .env
# Edit .env with your API keys
```

### 3. Start the API

```bash
# Start the FastAPI server
uvicorn app.main:app --reload

# API will be available at: http://localhost:8000
# Documentation at: http://localhost:8000/docs
```

### 4. Start the Web Interface

```bash
# In a new terminal
streamlit run frontend.py

# Web interface at: http://localhost:8501
```

## 📚 API Usage

### **Get Stock Analysis (Streaming)**

The API provides real-time streaming updates via Server-Sent Events (SSE):

```bash
curl -X POST "http://localhost:8000/analyze-stream" \
     -H "Content-Type: application/json" \
     -d '{"symbol": "AAPL"}'
```

**Final Response Example:**
```json
{
  "symbol": "AAPL",
  "company_name": "Apple Inc.",
  "price": 196.58,
  "currency": "USD",
  "change": 0.94,
  "change_percent": 0.48,
  "volume": 45394700,
  "financial_metrics": {
    "market_cap": 2936079646720.0,
    "pe_ratio": 30.57,
    "peg_ratio": null,
    "price_to_book": 43.97,
    "price_to_sales": null,
    "revenue_ttm": 400366010368.0,
    "gross_margin": null,
    "operating_margin": null,
    "profit_margin": 0.24,
    "return_on_equity": null,
    "return_on_assets": null,
    "debt_to_equity": null,
    "current_ratio": null,
    "quick_ratio": null,
    "dividend_yield": 0.53,
    "beta": 1.21,
    "fifty_two_week_high": 259.47,
    "fifty_two_week_low": 168.99
  },
  "analyst_ratings": [
    {
      "firm": "Consensus",
      "rating": "Buy: 25, Hold: 13, Sell: 3",
      "price_target": null,
      "date": "2025-06-01T00:00:00Z"
    }
  ],
  "consensus_rating": null,
  "average_price_target": null,
  "earnings_data": [
    {
      "eps_estimate": null,
      "eps_actual": 6.43,
      "revenue_estimate": null,
      "revenue_actual": null,
      "quarter": "TTM",
      "year": 2025
    },
    {
      "eps_estimate": 8.31,
      "eps_actual": null,
      "revenue_estimate": null,
      "revenue_actual": null,
      "quarter": "Forward",
      "year": 2026
    }
  ],
  "next_earnings_date": null,
  "sentiment_items": [],
  "sentiment_summary": {
    "overall_score": "positive",
    "confidence": 88.1,
    "positive_count": 8,
    "negative_count": 2,
    "neutral_count": 0,
    "summary_text": "AI Summary here"
  },
  "last_updated": "2025-06-20T01:17:42.200690Z",
  "data_sources": ["yfinance", "finnhub_analysts", "yfinance_fundamentals", "yfinance_earnings", "newsapi", "rss_feeds"]
}
```



### **Health Check**

```bash
curl http://localhost:8000/health
```

## 🔧 Configuration & Authentication

### External API Authentication

The system integrates with several external APIs to gather stock data, financial information, and sentiment analysis. Each service requires its own API key for authentication.

#### Required API Keys

1. **Alpha Vantage (Stock Data)**
   - **Purpose**: Real-time and historical stock prices, financial metrics
   - **Sign up**: https://www.alphavantage.co/support/#api-key
   - **Free tier**: 25 requests per day, 5 requests per minute
   - **Environment variable**: `ALPHA_VANTAGE_KEY`

2. **NewsAPI (News & Sentiment)**
   - **Purpose**: Financial news articles for sentiment analysis
   - **Sign up**: https://newsapi.org/register
   - **Free tier**: 1,000 requests per month (100 requests/day for Developers)
   - **Environment variable**: `NEWSAPI_KEY`

3. **OpenAI (AI Analysis)**
   - **Purpose**: AI-powered sentiment analysis and text processing
   - **Sign up**: https://platform.openai.com/api-keys
   - **Pricing**: Depends on the model
   - **Environment variable**: `OPENAI_API_KEY`

#### Optional API Keys

4. **Finnhub (Enhanced Financial Data)**
   - **Purpose**: Additional financial metrics, analyst ratings
   - **Sign up**: https://finnhub.io/register
   - **Free tier**: 60 requests per minute
   - **Environment variable**: `FINNHUB_KEY`

### Environment Configuration

The system is configurable through environment variables (see `.env.example`):

```bash
# Required API Keys for External Services
ALPHA_VANTAGE_KEY=your_alpha_vantage_key_here
NEWSAPI_KEY=your_newsapi_key_here
OPENAI_API_KEY=your_openai_key_here

# Optional API Keys
FINNHUB_KEY=your_finnhub_key_here

# Application Settings
LOG_LEVEL=INFO
CORS_ORIGINS=*

# HTTP Settings
HTTP_TIMEOUT=15
MAX_RETRIES=3
RETRY_DELAY=1.0

# Basic Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=3600

# AI Model Settings
USE_OPENAI_SENTIMENT=true
OPENAI_MODEL=gpt-4.1-nano-2025-04-14
SENTIMENT_TEMPERATURE=0.1

# News Settings
NEWS_DAYS_BACK=7
MAX_NEWS_ARTICLES=20

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090

# Application Metadata
APP_NAME=Multi-Agent Stock Screening API
VERSION=1.0.0
```

### Rate Limiting

The API includes basic rate limiting to prevent abuse and stay within external API limits:

- **100 requests per hour** per IP address by default
- **Window resets** every hour
- **Headers included** in responses showing current usage
- **Configurable limits** via environment variables

### Security Best Practices

1. **Never commit API keys** to version control
2. **Use environment variables** for all sensitive configuration
3. **Rotate API keys regularly** (recommended every 90 days)
4. **Monitor usage** to detect unusual activity
5. **Use HTTPS** in production deployments

## 📊 Monitoring & Analytics

### **Metrics Dashboard**

Access Prometheus metrics at: `http://localhost:9090/metrics`

**Available Metrics:**
- `stock_api_requests_total`: Total API requests by endpoint and status
- `stock_api_request_duration_seconds`: Request duration by endpoint
- `agent_execution_duration_seconds`: Agent execution time by agent name
- `agent_executions_total`: Total agent executions by agent and status
- `data_source_requests_total`: Total requests to data sources by source and status
- `data_source_latency_seconds`: Data source response latency by source
- `active_stock_symbols`: Number of unique symbols queried (24h window)


### **Logs**

Structured logs are written to `logs/api.log` with rotation and retention policies.

## 🧪 Testing

The project includes comprehensive unit tests covering all major functionality, including agent workflows, API endpoints, error handling, and performance benchmarking.

### **Running Tests**

```bash
# Run all tests
python -m pytest app/tests/ -v

# Run with coverage report
python -m pytest app/tests/ --cov=app --cov-report=html

# Run specific test categories
python -m pytest app/tests/test_agents.py -v     # Agent tests only
python -m pytest app/tests/test_api.py -v       # API tests only

# Run tests with detailed output
python -m pytest app/tests/ -v --tb=long
```

### **Test Structure**

#### **Agent Tests (`test_agents.py`)**
- `test_orchestration` - Basic multi-agent orchestration functionality
- `test_invalid_symbol` - Error handling for invalid stock symbols  
- `test_orchestration_data_completeness` - Validates complete data structure
- `test_orchestration_with_mocks` - Isolated testing with mocked external APIs
- `test_orchestration_fallback_logic` - Tests API fallback mechanisms
- `test_orchestration_performance` - Performance benchmarking (< 45 seconds)

#### **API Tests (`test_api.py`)**
- `test_analyze_stream_endpoint` - Main streaming endpoint functionality
- `test_health_endpoint` - Health check endpoint validation
- `test_invalid_symbol` - Schema validation and error responses
- `test_metrics_endpoint` - Prometheus metrics endpoint
- `test_metrics_collection` - Metrics collection functionality
### **Test Configuration**

The test suite includes:
- **Async Support**: Full async/await testing with pytest-asyncio
- **Mock Environment**: Isolated test environment with mock API keys
- **External API Mocking**: All external API calls are mocked to prevent rate limiting
- **Performance Testing**: Tests complete within reasonable time limits
- **Error Scenarios**: Comprehensive coverage of edge cases and error conditions

### **Test Environment Setup**

Tests automatically configure a mock environment with:
```bash
# Mock API keys (set automatically in tests)
ALPHA_VANTAGE_KEY=test_alpha_key
NEWSAPI_KEY=test_news_key
OPENAI_API_KEY=test_openai_key
FINNHUB_KEY=test_finnhub_key

# Test-specific settings
LOG_LEVEL=ERROR          # Reduce logging noise
ENABLE_METRICS=false     # Disable metrics collection
RATE_LIMIT_REQUESTS=1000 # High limit for tests
```

### **Continuous Integration**

The test suite is designed to run in CI/CD environments:
- **No External Dependencies**: All external APIs are mocked
- **Fast Execution**: Complete test suite runs in < 2 minutes
- **Deterministic Results**: Tests produce consistent results across environments
- **Comprehensive Coverage**: Tests cover all critical functionality

### **Test Results**
```
11 passed, 0 failed
✅ 6 agent tests (orchestration, validation, performance)
✅ 5 API tests (endpoints, streaming, validation)
✅ 100% core functionality coverage
✅ All external APIs properly mocked
✅ Error handling and edge cases covered
```

## 🆘 Troubleshooting

### **Common Issues**

1. **"API key not found" errors:**
   - Check that your `.env` file exists and contains the required keys
   - Verify there are no extra spaces or quotes around the keys
   - Ensure the application is reading from the correct `.env` file

2. **Rate limiting too aggressive:**
   - Increase `RATE_LIMIT_REQUESTS` in your `.env` file
   - Consider the limits of your external APIs when setting this value

3. **External API failures:**
   - Check your API key validity and quotas
   - Verify network connectivity
   - Review the logs for specific error messages

4. **OpenAI Costs**: OpenAI sentiment analysis is optional (set `USE_OPENAI_SENTIMENT=false`)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### **Debug Mode**
```bash
# Enable debug logging
LOG_LEVEL=DEBUG uvicorn app.main:app --reload

# Check logs
tail -f logs/api.log
```

### **Support**
- Review the API documentation at `/docs`
- Check logs in `logs/api.log`
- Enable debug logging for detailed troubleshooting

import httpx
from openai import AsyncOpenAI
import feedparser
from datetime import datetime, timedelta, timezone
import re
from typing import List, Dict, Any
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from loguru import logger
import statistics
from app.config import settings
from app.utils.error_handling import (
    handle_api_errors,
    create_retry_decorator,
    DataNotFoundError
)
from app.utils.monitoring import track_performance
from app.schemas import SentimentItem, SentimentSummary, SentimentScore

# Initialize clients
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
vader_analyzer = SentimentIntensityAnalyzer()

NEWS_URL = "https://newsapi.org/v2/everything"
RSS_FEEDS = [
    # Bloomberg Markets (working)
    "https://feeds.bloomberg.com/markets/news.rss",
    # NPR Business (working, good coverage)
    "https://feeds.npr.org/1006/rss.xml",
    # Wall Street Journal Markets (working)
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://feeds.bbci.co.uk/news/business/rss.xml",  # BBC Business (working)
    "https://feeds.skynews.com/feeds/rss/business.xml",  # Sky News Business
    # Investing.com Stock Market News (working)
    "https://www.investing.com/rss/news_285.rss",
    # ZeroHedge Financial News (working)
    "https://feeds.feedburner.com/zerohedge/feed",
    "https://www.benzinga.com/feed",  # Benzinga (working)
    "https://seekingalpha.com/market_currents.xml",  # Seeking Alpha (working)
]


@handle_api_errors
@create_retry_decorator()
@track_performance("source_newsapi")
async def fetch_news_articles(symbol: str, days_back: int = None) -> List[Dict[str, Any]]:
    """Fetch news articles from NewsAPI"""
    days_back = days_back or settings.news_days_back
    from_date = (datetime.now() - timedelta(days=days_back)).isoformat()

    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        response = await client.get(
            NEWS_URL,
            params={
                "q": f'"{symbol}" AND (stock OR shares OR earnings OR revenue OR financial OR investment OR market)',
                "from": from_date,
                "sortBy": "relevancy",
                "apiKey": settings.newsapi_key,
                "language": "en",
                "pageSize": settings.max_news_articles,
                "domains": "reuters.com,bloomberg.com,cnbc.com,marketwatch.com,yahoo.com,seekingalpha.com,wsj.com,ft.com,forbes.com,benzinga.com",
            },
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "error":
            raise DataNotFoundError(
                f"NewsAPI error: {data.get('message', 'Unknown error')}")

        articles = data.get("articles", [])
        return articles


@handle_api_errors
@create_retry_decorator()
@track_performance("source_rss_feeds")
async def fetch_rss_news(symbol: str) -> List[Dict[str, Any]]:
    """Fetch news from RSS feeds with improved relevance matching"""
    all_articles = []
    company_name, search_terms = await get_company_query_terms(symbol)

    logger.info(
        f"RSS search for {symbol} ({company_name}) using terms: {search_terms}")

    for feed_url in RSS_FEEDS:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(feed_url)

                if response.status_code != 200:
                    logger.warning(
                        f"RSS feed {feed_url} returned status {response.status_code}")
                    continue

                feed_content = response.text

            feed = feedparser.parse(feed_content)

            if not feed.entries:
                logger.warning(f"No entries found in RSS feed {feed_url}")
                continue

            feed_articles_found = 0
            for entry in feed.entries[:30]:  # Increased limit per feed
                title = entry.get("title", "")
                description = entry.get("description", "")
                summary = entry.get("summary", "")
                content = f"{title} {description} {summary}".lower()

                # Enhanced relevance checking with word boundaries
                is_relevant = False
                matched_terms = []

                for term in search_terms:
                    # Use word boundaries for better matching
                    if len(term) <= 4:  # Short terms like symbols need exact word match
                        pattern = r'\b' + re.escape(term) + r'\b'
                    else:  # Longer terms can be part of words
                        pattern = re.escape(term)

                    if re.search(pattern, content, re.IGNORECASE):
                        is_relevant = True
                        matched_terms.append(term)
                        break

                if is_relevant:
                    published = entry.get("published_parsed")
                    published_dt = None
                    if published:
                        try:
                            published_dt = datetime(
                                *published[:6], tzinfo=timezone.utc)
                        except:
                            pass

                    # Get feed title for source
                    feed_title = "RSS Feed"
                    if hasattr(feed, 'feed') and hasattr(feed.feed, 'title'):
                        feed_title = feed.feed.get('title', 'RSS Feed')

                    article = {
                        "title": title,
                        "description": description or summary,
                        "url": entry.get("link", ""),
                        "publishedAt": published_dt.isoformat() if published_dt else None,
                        "source": {"name": feed_title},
                        "matched_terms": matched_terms  # For debugging
                    }
                    all_articles.append(article)
                    feed_articles_found += 1

            if feed_articles_found > 0:
                logger.info(
                    f"Found {feed_articles_found} articles from {feed_url}")

        except Exception as e:
            logger.warning(f"Failed to fetch RSS feed {feed_url}: {e}")
            continue

    # Remove duplicates based on title similarity
    unique_articles = []
    seen_titles = set()
    for article in all_articles:
        # Create a normalized title for duplicate detection
        normalized_title = re.sub(r'[^\w\s]', '', article.get(
            "title", "")).lower().strip()[:100]
        if normalized_title and normalized_title not in seen_titles:
            seen_titles.add(normalized_title)
            unique_articles.append(article)

    # Sort by publication date (most recent first)
    unique_articles.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)

    logger.info(
        f"RSS news summary for {symbol}: {len(unique_articles)} unique articles from {len(RSS_FEEDS)} feeds")
    return unique_articles[:settings.max_news_articles]


# Common stock symbol to company name mappings
SYMBOL_TO_COMPANY = {
    'AAPL': 'Apple Inc.',
    'GOOGL': 'Alphabet Inc.',
    'GOOG': 'Alphabet Inc.',
    'MSFT': 'Microsoft Corporation',
    'AMZN': 'Amazon.com Inc.',
    'TSLA': 'Tesla Inc.',
    'META': 'Meta Platforms Inc.',
    'NVDA': 'NVIDIA Corporation',
    'NFLX': 'Netflix Inc.',
    'AMD': 'Advanced Micro Devices',
    'INTC': 'Intel Corporation',
    'ORCL': 'Oracle Corporation',
    'ADBE': 'Adobe Inc.',
    'CRM': 'Salesforce Inc.',
    'UBER': 'Uber Technologies',
    'LYFT': 'Lyft Inc.',
    'SPOT': 'Spotify Technology',
    'ZM': 'Zoom Video Communications',
    'PYPL': 'PayPal Holdings',
    'SQ': 'Block Inc.',
    'SHOP': 'Shopify Inc.',
    'TWTR': 'Twitter Inc.',
    'SNAP': 'Snap Inc.',
    'PINS': 'Pinterest Inc.',
    'ROKU': 'Roku Inc.',
    'DOCU': 'DocuSign Inc.',
    'OKTA': 'Okta Inc.',
    'SNOW': 'Snowflake Inc.',
    'PLTR': 'Palantir Technologies',
    'COIN': 'Coinbase Global',
    'RBLX': 'Roblox Corporation',
    'HOOD': 'Robinhood Markets',
    'RIVN': 'Rivian Automotive',
    'LCID': 'Lucid Group',
    'NIO': 'NIO Inc.',
    'XPEV': 'XPeng Inc.',
    'LI': 'Li Auto Inc.',
    'BABA': 'Alibaba Group',
    'JD': 'JD.com Inc.',
    'PDD': 'PDD Holdings',
    'BIDU': 'Baidu Inc.',
    'JPM': 'JPMorgan Chase',
    'BAC': 'Bank of America',
    'WFC': 'Wells Fargo',
    'GS': 'Goldman Sachs',
    'MS': 'Morgan Stanley',
    'C': 'Citigroup Inc.',
    'BRK.A': 'Berkshire Hathaway',
    'BRK.B': 'Berkshire Hathaway',
    'JNJ': 'Johnson & Johnson',
    'PFE': 'Pfizer Inc.',
    'ABBV': 'AbbVie Inc.',
    'MRK': 'Merck & Co.',
    'UNH': 'UnitedHealth Group',
    'LLY': 'Eli Lilly',
    'BMY': 'Bristol Myers Squibb',
    'AMGN': 'Amgen Inc.',
    'GILD': 'Gilead Sciences',
    'BIIB': 'Biogen Inc.',
    'V': 'Visa Inc.',
    'MA': 'Mastercard Inc.',
    'DIS': 'Walt Disney',
    'CMCSA': 'Comcast Corporation',
    'NFLX': 'Netflix Inc.',
    'T': 'AT&T Inc.',
    'VZ': 'Verizon Communications',
    'KO': 'Coca-Cola Company',
    'PEP': 'PepsiCo Inc.',
    'NKE': 'Nike Inc.',
    'MCD': 'McDonald\'s Corporation',
    'SBUX': 'Starbucks Corporation',
    'WMT': 'Walmart Inc.',
    'TGT': 'Target Corporation',
    'HD': 'Home Depot',
    'LOW': 'Lowe\'s Companies',
    'COST': 'Costco Wholesale',
    'CVS': 'CVS Health',
    'WBA': 'Walgreens Boots Alliance',
    'XOM': 'Exxon Mobil',
    'CVX': 'Chevron Corporation',
    'COP': 'ConocoPhillips',
    'SLB': 'Schlumberger',
    'BA': 'Boeing Company',
    'CAT': 'Caterpillar Inc.',
    'MMM': '3M Company',
    'GE': 'General Electric',
    'F': 'Ford Motor',
    'GM': 'General Motors',
    'TSLA': 'Tesla Inc.',
}


async def get_company_query_terms(symbol: str) -> tuple[str, List[str]]:
    """Get company name and comprehensive search terms"""
    try:
        # First try our static mapping
        company_name = SYMBOL_TO_COMPANY.get(symbol.upper())

        # If not found, try to get from market data service
        if not company_name:
            try:
                from app.services.market_data import get_company_name
                company_name = await get_company_name(symbol)
            except:
                pass

        # Generate comprehensive search terms
        search_terms = [symbol.lower(), symbol.upper()]

        if company_name:
            # Add full company name
            search_terms.append(company_name.lower())

            # Add company name without common suffixes
            clean_name = company_name.replace(' Inc.', '').replace(' Corp.', '').replace(' Corporation', '').replace(' Company', '').replace(
                ' Ltd.', '').replace(' Co.', '').replace(' Group', '').replace(' Holdings', '').replace(' Technologies', '').replace(' Systems', '').strip()
            if clean_name.lower() not in search_terms:
                search_terms.append(clean_name.lower())

            # Add first word of company name (for major brands)
            first_word = clean_name.split()[0].lower()
            if len(first_word) > 3 and first_word not in search_terms:
                search_terms.append(first_word)

        # Remove duplicates while preserving order
        unique_terms = []
        for term in search_terms:
            if term not in unique_terms:
                unique_terms.append(term)

        return company_name or symbol, unique_terms

    except Exception as e:
        logger.warning(f"Error getting company terms for {symbol}: {e}")
        return symbol, [symbol.lower()]


def analyze_polarity_vader(text: str) -> float:
    """Analyze sentiment polarity using VADER"""
    scores = vader_analyzer.polarity_scores(text)
    return scores['compound']  # Returns -1 to 1


def analyze_polarity_rule_based(text: str) -> float:
    """
    Enhanced rule-based polarity analysis
    """
    # Positive indicators
    positive_patterns = [
        r'\b(beat|beats|beating|exceeded?|outperformed?|surge|surged|surging|record|records|up|growth|grow|growing|gains?|rally|bullish|optimistic|positive|strong|strength|robust|solid|impressive|excellent|outstanding|breakthrough|success|profit|profits|revenue|earnings|buy|upgrade|target|raised?|increase|increased?|boost|boosted?)\b',
        r'\b(all.?time.?high|new.?high|higher|rising|climbed?|jumped?|soared?|rallied?|gained?|advanced?)\b'
    ]

    # Negative indicators
    negative_patterns = [
        r'\b(miss|missed?|missing|underperformed?|drop|dropped?|dropping|fell|fall|falling|decline|declined?|declining|crash|crashed?|plunge|plunged?|tumble|tumbled?|loss|losses|lawsuit|lawsuits?|down|bearish|pessimistic|negative|weak|weakness|poor|disappointing|concerning|worried?|fear|fears|sell|downgrade|lowered?|decrease|decreased?|cut|slashed?)\b',
        r'\b(all.?time.?low|new.?low|lower|sinking|slumped?|retreated?|lost|erased?)\b'
    ]

    text_lower = text.lower()

    positive_score = 0
    negative_score = 0

    for pattern in positive_patterns:
        positive_score += len(re.findall(pattern, text_lower))

    for pattern in negative_patterns:
        negative_score += len(re.findall(pattern, text_lower))

    total = positive_score + negative_score
    if total == 0:
        return 0.0

    return (positive_score - negative_score) / total


@handle_api_errors
@create_retry_decorator()
@track_performance("source_openai_summary")
async def generate_ai_summary(symbol: str, sentiment_items: List[SentimentItem], avg_polarity: float) -> str:
    """Generate comprehensive AI summary of sentiment data"""
    if not settings.use_openai_sentiment or not settings.openai_api_key:
        raise DataNotFoundError("OpenAI summarization not configured")

    # Prepare article summaries for AI processing
    articles_text = []
    for item in sentiment_items[:10]:  # Limit to top 10 articles
        article_summary = f"Title: {item.title}\nSource: {item.source}\nSentiment: {item.polarity:.2f}"
        articles_text.append(article_summary)

    articles_combined = "\n\n".join(articles_text)

    prompt = f"""
    As a financial analyst, provide a comprehensive summary of market sentiment for {symbol} based on the following news articles.
    
    Overall sentiment score: {avg_polarity:.3f} (range: -1.0 to 1.0)
    
    Articles:
    {articles_combined}
    
    Please provide:
    1. A 2-3 sentence summary of the key themes and sentiment drivers
    2. Notable trends or patterns in the coverage
    3. Potential implications for investors
    
    Keep the response concise but insightful (max 150 words).
    """

    try:
        response = await openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # Lower temperature for more consistent summaries
            max_tokens=200
        )

        summary = response.choices[0].message.content.strip()
        return summary

    except Exception as e:
        error_msg = str(e)
        if any(keyword in error_msg.lower() for keyword in ["disconnected", "cancelled", "closed", "connection"]):
            logger.info(
                f"🛑 Client disconnection detected during OpenAI summarization: {e}")
        else:
            logger.error(f"OpenAI summarization failed: {e}")
        raise DataNotFoundError("OpenAI summarization failed")


@handle_api_errors
@create_retry_decorator()
@track_performance("source_openai_sentiment")
async def analyze_sentiment_openai(text: str) -> Dict[str, Any]:
    """Analyze sentiment using OpenAI GPT"""
    if not settings.use_openai_sentiment or not settings.openai_api_key:
        raise DataNotFoundError("OpenAI sentiment analysis not configured")

    prompt = f"""
    Analyze the sentiment of this financial news text and provide:
    1. Overall sentiment score (-1 to 1, where -1 is very negative, 0 is neutral, 1 is very positive)
    2. Confidence score (0 to 1)
    3. Brief explanation (max 50 words)
    
    Text: "{text}"
    
    Respond in JSON format:
    {{
        "sentiment_score": <float>,
        "confidence": <float>,
        "explanation": "<string>"
    }}
    """

    try:
        response = await openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.sentiment_temperature,
            max_tokens=200
        )

        result_text = response.choices[0].message.content.strip()
        # Parse JSON response
        import json
        result = json.loads(result_text)
        return result

    except Exception as e:
        error_msg = str(e)
        if any(keyword in error_msg.lower() for keyword in ["disconnected", "cancelled", "closed", "connection"]):
            logger.info(
                f"🛑 Client disconnection detected during OpenAI sentiment analysis: {e}")
        else:
            logger.error(f"OpenAI sentiment analysis failed: {e}")
        raise DataNotFoundError("OpenAI sentiment analysis failed")


def sentiment_score_to_enum(score: float) -> SentimentScore:
    """Convert numerical sentiment score to enum"""
    if score >= 0.5:
        return SentimentScore.VERY_POSITIVE
    elif score >= 0.15:
        return SentimentScore.POSITIVE
    elif score <= -0.5:
        return SentimentScore.VERY_NEGATIVE
    elif score <= -0.15:
        return SentimentScore.NEGATIVE
    else:
        return SentimentScore.NEUTRAL


async def analyze_article_sentiment(article: Dict[str, Any]) -> SentimentItem:
    """Analyze sentiment for a single article"""
    title = article.get("title", "")
    description = article.get("description", "")
    text = f"{title} {description}"

    # Try multiple sentiment analysis methods
    polarity_scores = []

    # VADER sentiment
    try:
        vader_score = analyze_polarity_vader(text)
        polarity_scores.append(vader_score)
    except:
        pass

    # Rule-based sentiment
    try:
        rule_score = analyze_polarity_rule_based(text)
        polarity_scores.append(rule_score)
    except:
        pass

    # OpenAI sentiment (if enabled and available)
    # Only for substantial text
    if settings.use_openai_sentiment and len(text) > 20:
        try:
            openai_result = await analyze_sentiment_openai(text)
            polarity_scores.append(openai_result.get("sentiment_score", 0))
        except:
            pass

    # Calculate average polarity
    final_polarity = statistics.mean(
        polarity_scores) if polarity_scores else 0.0

    # Parse published date
    published_at = None
    if article.get("publishedAt"):
        try:
            published_at = datetime.fromisoformat(
                article["publishedAt"].replace("Z", "+00:00"))
        except:
            pass

    return SentimentItem(
        source=article.get("source", {}).get("name", "Unknown"),
        title=title,
        polarity=final_polarity,
        sentiment_score=sentiment_score_to_enum(final_polarity),
        published_at=published_at,
        url=article.get("url")
    )


async def fetch_comprehensive_sentiment(symbol: str) -> tuple[List[SentimentItem], SentimentSummary]:
    """Fetch comprehensive sentiment analysis from multiple sources"""
    all_articles = []

    # Fetch from NewsAPI
    try:
        news_articles = await fetch_news_articles(symbol)
        all_articles.extend(news_articles)
    except Exception as e:
        logger.warning(f"Failed to fetch NewsAPI articles: {e}")

    # Fetch from RSS feeds
    try:
        rss_articles = await fetch_rss_news(symbol)
        all_articles.extend(rss_articles)
    except Exception as e:
        logger.warning(f"Failed to fetch RSS articles: {e}")

    if not all_articles:
        return [], SentimentSummary(
            overall_score=SentimentScore.NEUTRAL,
            confidence=0.0,
            positive_count=0,
            negative_count=0,
            neutral_count=0,
            summary_text="No sentiment data available"
        )

    # Remove duplicates based on title similarity
    unique_articles = []
    seen_titles = set()
    for article in all_articles:
        title_key = re.sub(r'[^\w\s]', '', article.get(
            "title", "")).lower()[:50]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_articles.append(article)

    # Analyze sentiment for each article
    sentiment_items = []
    for article in unique_articles[:settings.max_news_articles]:
        try:
            sentiment_item = await analyze_article_sentiment(article)
            sentiment_items.append(sentiment_item)
        except Exception as e:
            logger.warning(f"Failed to analyze sentiment for article: {e}")
            continue

    if not sentiment_items:
        return [], SentimentSummary(
            overall_score=SentimentScore.NEUTRAL,
            confidence=0.0,
            positive_count=0,
            negative_count=0,
            neutral_count=0,
            summary_text="Failed to analyze sentiment"
        )

    # Calculate overall sentiment summary
    polarities = [item.polarity for item in sentiment_items]
    avg_polarity = statistics.mean(polarities)

    positive_count = sum(1 for p in polarities if p > 0.15)
    negative_count = sum(1 for p in polarities if p < -0.15)
    neutral_count = len(polarities) - positive_count - negative_count

    # Calculate confidence based on agreement between sources
    polarity_std = statistics.stdev(polarities) if len(polarities) > 1 else 0
    # Lower std dev = higher confidence
    confidence = max(0, 1 - (polarity_std / 2))

    overall_score = sentiment_score_to_enum(avg_polarity)

    # Generate enhanced summary text with AI summarization
    try:
        if settings.use_openai_sentiment and len(sentiment_items) > 3:
            summary_text = await generate_ai_summary(symbol, sentiment_items, avg_polarity)
        else:
            # Fallback to basic summary
            summary_text = f"Based on {len(sentiment_items)} articles: "
            if positive_count > negative_count:
                summary_text += f"Generally positive sentiment ({positive_count} positive, {negative_count} negative)"
            elif negative_count > positive_count:
                summary_text += f"Generally negative sentiment ({negative_count} negative, {positive_count} positive)"
            else:
                summary_text += f"Mixed sentiment ({positive_count} positive, {negative_count} negative, {neutral_count} neutral)"
    except Exception as e:
        logger.warning(f"AI summarization failed: {e}")
        # Fallback to basic summary
        summary_text = f"Based on {len(sentiment_items)} articles: "
        if positive_count > negative_count:
            summary_text += f"Generally positive sentiment ({positive_count} positive, {negative_count} negative)"
        elif negative_count > positive_count:
            summary_text += f"Generally negative sentiment ({negative_count} negative, {positive_count} positive)"
        else:
            summary_text += f"Mixed sentiment ({positive_count} positive, {negative_count} negative, {neutral_count} neutral)"

    sentiment_summary = SentimentSummary(
        overall_score=overall_score,
        confidence=confidence,
        positive_count=positive_count,
        negative_count=negative_count,
        neutral_count=neutral_count,
        summary_text=summary_text
    )

    return sentiment_items, sentiment_summary


# Legacy function for backward compatibility
async def fetch_sentiment(symbol: str) -> tuple[List[Dict[str, Any]], str]:
    """Legacy function for backward compatibility"""
    sentiment_items, sentiment_summary = await fetch_comprehensive_sentiment(symbol)

    # Convert to legacy format
    legacy_items = [
        {
            "source": item.source,
            "title": item.title,
            "polarity": item.polarity,
            "sentiment_score": item.sentiment_score.value,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "url": item.url
        }
        for item in sentiment_items
    ]

    return legacy_items, sentiment_summary.summary_text

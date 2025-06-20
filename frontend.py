import streamlit as st
import httpx
import json
from datetime import datetime

# Configure page
st.set_page_config(
    page_title="Stock Screening Bot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    /* Main app styling */
    .main-header {
        font-size: 3rem;
        color: #2E86AB;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: 700;
        text-shadow: 0 2px 4px rgba(46, 134, 171, 0.3);
    }
    
    /* Unified color palette */
    :root {
        --primary-blue: #2E86AB;
        --secondary-blue: #A23B72;
        --accent-blue: #F18F01;
        --light-bg: #F8F9FA;
        --medium-bg: #E3F2FD;
        --dark-text: #2C3E50;
        --success-green: #27AE60;
        --warning-orange: #F39C12;
        --error-red: #E74C3C;
        --card-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }

    /* Hide Streamlit default white containers */
    .stContainer > div {
        background: transparent !important;
    }
    
    .stContainer {
        background: transparent !important;
    }

    /* Input styling */
    .stTextInput label {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        color: var(--primary-blue) !important;
        
    }
    
    .stTextInput input {
        font-size: 1.1rem !important;
        font-weight: 500 !important;
        text-align: center !important;
        border: 2px solid var(--primary-blue) !important;
        border-radius: 8px !important;
        transition: all 0.3s ease !important;
    }
    
    .stTextInput input:focus {
        border-color: var(--secondary-blue) !important;
        box-shadow: 0 0 0 2px rgba(162, 59, 114, 0.2) !important;
    }
    
    /* Button styling */
    .stButton button {
        background: linear-gradient(135deg, var(--primary-blue) 0%, var(--secondary-blue) 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        height: 44px !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton button:hover {
        background: linear-gradient(135deg, var(--primary-blue) 20%, var(--secondary-blue) 80%) !important;
        transform: translateY(-2px) !important;
        box-shadow: var(--card-shadow) !important;
    }
    
    .stButton button[kind="secondary"] {
        background: linear-gradient(135deg, var(--error-red) 0%, #C0392B 100%) !important;
    }
    
    .stButton button[kind="secondary"]:hover {
        background: linear-gradient(135deg, var(--error-red) 20%, #C0392B 80%) !important;
    }

    /* Unified section containers */
    .info-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1.5rem 0;
        border-left: 4px solid var(--primary-blue);
        box-shadow: var(--card-shadow);
        transition: all 0.3s ease;
    }
    
    .info-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
    }

    .info-card h3 {
        color: var(--primary-blue) !important;
        margin-top: 0 !important;
        margin-bottom: 1rem !important;
        font-weight: 700 !important;
        font-size: 1.4rem !important;
    }

    /* Enhanced metric cards */
    .metric-card {
        background: linear-gradient(135deg, var(--light-bg) 0%, white 100%);
        padding: 1.2rem;
        border-radius: 10px;
        border-left: 4px solid var(--accent-blue);
        margin: 0.8rem 0;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        transition: all 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    }

    /* Earnings card styling */
    .earnings-card {
        background: linear-gradient(135deg, white 0%, var(--light-bg) 100%);
        padding: 1.2rem;
        border-radius: 12px;
        margin: 0.8rem 0;
        border: 1px solid rgba(46, 134, 171, 0.2);
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
        transition: all 0.2s ease;
    }
    
    .earnings-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.15);
        border-color: var(--primary-blue);
    }
    
    .earnings-quarter {
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--primary-blue);
        margin-bottom: 0.5rem;
    }
    
    .earnings-metric {
        display: flex;
        justify-content: space-between;
        margin: 0.3rem 0;
        font-size: 0.95rem;
    }
    
    .earnings-label {
        color: var(--dark-text);
        font-weight: 500;
    }
    
    .earnings-value {
        font-weight: 600;
        color: var(--secondary-blue);
    }

    /* Sentiment styling */
    .sentiment-positive {
        color: var(--success-green) !important;
        font-weight: 600 !important;
    }
    
    .sentiment-negative {
        color: var(--error-red) !important;
        font-weight: 600 !important;
    }
    
    .sentiment-neutral {
        color: var(--warning-orange) !important;
        font-weight: 600 !important;
    }

    .stExpander a {
        color: var(--primary-blue) !important;
        text-decoration: none !important;
        transition: all 0.2s ease !important;
    }
    
    .stExpander a:hover {
        color: var(--primary-blue)   !important;
        text-decoration: underline !important;
    }

    /* Data source badges */
    .data-source-badge {
        background: linear-gradient(135deg, var(--primary-blue) 0%, var(--secondary-blue) 100%);
        color: white;
        padding: 0.4rem 1rem;
        border-radius: 20px;
        font-size: 0.85rem;
        margin: 0.3rem;
        display: inline-block;
        font-weight: 500;
        box-shadow: 0 2px 6px rgba(46, 134, 171, 0.3);
    }

    /* Analyst ratings - FIXED: Dark text on light background */
    .analyst-rating {
        background: linear-gradient(135deg, white 0%, var(--light-bg) 100%);
        padding: 1rem;
        margin: 0.75rem 0;
        border-radius: 10px;
        border: 1px solid rgba(46, 134, 171, 0.15);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        transition: all 0.2s ease;
        color: var(--dark-text) !important;
    }
    
    .analyst-rating:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        border-color: var(--primary-blue);
    }
    
    .analyst-rating strong {
        color: var(--dark-text) !important;
        font-weight: 600 !important;
    }
    
    .analyst-rating * {
        color: var(--dark-text) !important;
    }
            
    [data-testid="stContainer"] > div:first-child {
        background: white !important;
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1.5rem 0;
        border-left: 4px solid var(--primary-blue);
        box-shadow: var(--card-shadow);
    }

    /* AI summary box */
    .ai-summary-box {
        background: linear-gradient(135deg, var(--primary-blue) 0%, var(--secondary-blue) 100%);
        border: 1px solid var(--primary-blue);
        border-left: 4px solid var(--primary-blue);
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 12px rgba(46, 134, 171, 0.3);
    }
    
    .ai-summary-box p {
        margin: 0.5rem 0;
        color: white !important;
        line-height: 1.6;
    }
    
    .ai-summary-box strong {
        color: white !important;
        font-weight: 700 !important;
    }

    /* Company header */
    .company-header {
        color: var(--primary-blue) !important;
        font-weight: 700 !important;
        margin: 1rem 0 !important;
        font-size: 2.2rem; 
        line-height: 1.2;  
    }
    
    .symbol-display {
        background: linear-gradient(135deg, var(--primary-blue) 0%, var(--secondary-blue) 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 12px;
        font-size: 2.2rem; 
        font-weight: 700;
        text-align: center;
        margin: 1rem 0;
        box-shadow: 0 4px 12px rgba(46, 134, 171, 0.3);
    }

    /* Progress and status styling */
    .status-container {
        background: var(--light-bg);
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        border-left: 4px solid var(--primary-blue);
    }

    /* Sidebar styling */
    .css-1d391kg {
        background: linear-gradient(180deg, var(--light-bg) 0%, white 100%);
    }
            
""", unsafe_allow_html=True)

# Header
st.markdown('<h1 class="main-header">📈 Multi-Agent Stock Screening Chatbot</h1>',
            unsafe_allow_html=True)

# Sidebar configuration - simplified
with st.sidebar:
    st.header("📊 Analysis Options")
    show_price_overview = st.checkbox("Show Price Overview", value=True)
    show_detailed_metrics = st.checkbox(
        "Show Detailed Financial Metrics", value=True)
    show_analyst_ratings = st.checkbox("Show Analyst Ratings", value=True)
    show_earnings_data = st.checkbox("Show Earnings Data", value=True)
    show_market_sentiment = st.checkbox("Show Market Sentiment", value=True)
    show_sentiment_details = st.checkbox("Show Detailed Sentiment", value=True)
    show_data_sources = st.checkbox("Show Data Sources", value=True)
    show_date_completed = st.checkbox("Show Date Completed", value=True)


if "phase" not in st.session_state:        # "idle", "loading"
    st.session_state.phase = "idle"
if "progress" not in st.session_state:     # remember last %
    st.session_state.progress = 0
if "stop_requested" not in st.session_state:   # <— NEW
    st.session_state.stop_requested = False

# Hardcoded timeout
TIMEOUT_SECONDS = 60

# Input section with proper alignment
st.markdown("---")


# Input and button layout
col1, col2 = st.columns([4, 1])

with col1:
    symbol = st.text_input(
        "📈 Enter Stock Symbol:",
        value="AAPL",
        placeholder="e.g., AAPL, MSFT, GOOGL",
        disabled=(st.session_state.phase == "loading"),
        key="symbol_input"
    ).upper()

with col2:
    st.markdown("<br>", unsafe_allow_html=True)

    if st.session_state.phase in ("prebar", "loading"):
        # Show STOP
        if st.button("⏹️ Stop", key="stop_btn",
                     type="secondary", use_container_width=True):
            st.session_state.stop_requested = True      # flag
            st.session_state.phase = "idle"     # reset UI
            st.session_state.progress = 0
            st.rerun()                                   # refresh page
    else:
        # Show ANALYZE (for idle, error, or any other phase)
        if st.button("🚀 Analyze", key="analyze_btn",
                     type="primary", use_container_width=True):
            # Clear previous UI and data FIRST before changing phase
            if "main_content" in st.session_state:
                try:
                    st.session_state.main_content.empty()
                except Exception:
                    pass  # placeholder may not yet exist

            if "final_data" in st.session_state:
                del st.session_state.final_data
            # Clear error state if coming from error phase
            if 'error_message' in st.session_state:
                del st.session_state.error_message
            st.session_state.phase = "prebar"
            st.session_state.progress = 0
            st.session_state.stop_requested = False
            st.rerun()

st.markdown("---")

# Function to display results


def display_stock_analysis(data):
    # Company Header with bigger symbol display
    header_col1, header_col2 = st.columns(
        [3, 2])
    with header_col1:
        st.markdown(f'<h2 class="company-header">🏢 {data.get("company_name", data["symbol"])}</h2>',
                    unsafe_allow_html=True)
    with header_col2:
        st.markdown(
            f'<div class="symbol-display">{data["symbol"]}</div>', unsafe_allow_html=True)

    # 1. PRICE OVERVIEW - Most important information first
    if show_price_overview and data.get('price'):
        with st.container():
            st.markdown("---")
            st.markdown("### 💰 Price Overview")

            if data.get('price') is not None:
                price_col1, price_col2, price_col3, price_col4 = st.columns(4)

                with price_col1:
                    st.metric(
                        "Current Price",
                        f"${data['price']:.2f}",
                        delta=f"{data.get('change', 0):.2f}" if data.get(
                            'change') is not None else None
                    )

                with price_col2:
                    if data.get('change_percent') is not None:
                        st.metric("Daily Change",
                                  f"{data['change_percent']:.2f}%")

                with price_col3:
                    if data.get('volume') is not None:
                        st.metric("Volume", f"{data['volume']:,}")

                with price_col4:
                    st.metric("Currency", data.get('currency', 'USD'))
            else:
                st.warning(
                    "⚠️ Price data temporarily unavailable due to API rate limits.")

    # 2. FINANCIAL OVERVIEW - Key metrics
    if show_detailed_metrics and data.get('financial_metrics'):
        st.markdown("---")
        with st.container():
            st.markdown("### 📊 Financial Overview")
            metrics = data['financial_metrics']

            has_data = any(metrics.get(
                key) is not None for key in metrics.keys())

            if has_data:
                # Valuation Metrics
                st.markdown("**Valuation Metrics**")
                val_col1, val_col2, val_col3, val_col4 = st.columns(4)

                with val_col1:
                    if metrics.get('market_cap'):
                        st.metric("Market Cap",
                                  f"${metrics['market_cap']:,.0f}")
                with val_col2:
                    if metrics.get('pe_ratio'):
                        st.metric("P/E Ratio", f"{metrics['pe_ratio']:.2f}")
                with val_col3:
                    if metrics.get('price_to_book'):
                        st.metric(
                            "P/B Ratio", f"{metrics['price_to_book']:.2f}")
                with val_col4:
                    if metrics.get('beta'):
                        st.metric("Beta", f"{metrics['beta']:.2f}")

                # Performance Metrics
                st.markdown("**Performance & Returns**")
                perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)

                with perf_col1:
                    if metrics.get('profit_margin'):
                        st.metric("Profit Margin",
                                  f"{metrics['profit_margin']:.2%}")
                with perf_col2:
                    if metrics.get('dividend_yield'):
                        st.metric("Dividend Yield",
                                  f"{metrics['dividend_yield']:.2%}")
                with perf_col3:
                    if metrics.get('revenue_ttm'):
                        st.metric("Revenue TTM",
                                  f"${metrics['revenue_ttm']:,.0f}")

                # Price Range
                if metrics.get('fifty_two_week_high') or metrics.get('fifty_two_week_low'):
                    st.markdown("**52-Week Range**")
                    range_col1, range_col2, range_col3, range_col4 = st.columns(
                        4)

                    with range_col1:
                        if metrics.get('fifty_two_week_low'):
                            st.metric(
                                "52W Low", f"${metrics['fifty_two_week_low']:.2f}")
                    with range_col2:
                        if metrics.get('fifty_two_week_high'):
                            st.metric(
                                "52W High", f"${metrics['fifty_two_week_high']:.2f}")
            else:
                st.info(
                    "📊 Financial metrics temporarily unavailable due to API rate limits.")

    # 3. ANALYST INSIGHTS - Professional opinions
    if show_analyst_ratings and data.get('analyst_ratings'):
        st.markdown("---")
        with st.container():
            st.markdown("### 🎯 Analyst Insights")
            ratings = data['analyst_ratings']

            if ratings:
                cons1, cons2 = st.columns(2)
                with cons1:
                    if data.get('average_price_target'):
                        st.metric("Consensus", data["consensus_rating"])
                with cons2:
                    if data.get('average_price_target'):
                        st.metric("Avg. Price Target",
                                  f'${data["average_price_target"]:.2f}')

                st.markdown("**Recent Recommendations**")
                rec_cols = st.columns(min(len(ratings[:4]), 4))
                for col, rating in zip(rec_cols, ratings[:4]):
                    if hasattr(rating, 'firm'):
                        firm = rating.firm or 'Unknown'
                        rating_text = rating.rating or 'N/A'
                        date = rating.date or 'N/A'
                    else:
                        firm = rating.get('firm', 'Unknown')
                        rating_text = rating.get('rating', 'N/A')
                        date = rating.get('date', 'N/A')

                    if date and date != 'N/A':
                        try:
                            if 'T' in str(date):
                                parsed_date = datetime.fromisoformat(
                                    str(date).replace('Z', '+00:00'))
                                date = parsed_date.strftime('%B %Y')
                        except:
                            pass

                    with col:
                        st.markdown(f"""
                        <div class="earnings-card">
                        <div class="earnings-quarter">{firm}</div>
                        <div class="earnings-metric">
                            <span class="earnings-label">Rating:</span>
                            <span class="earnings-value">{rating_text}</span>
                        </div>
                        <div class="earnings-metric">
                            <span class="earnings-label">Date:</span>
                            <span class="earnings-value">{date}</span>
                        </div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("No analyst ratings available")

    # 4. EARNINGS PERFORMANCE
    if show_earnings_data and data.get('earnings_data'):
        st.markdown("---")
        with st.container():
            st.markdown("### 📅 Earnings Performance")
            earnings = data['earnings_data']

            if earnings:
                if data.get('next_earnings_date'):
                    st.info(f"**Next Earnings:** {data['next_earnings_date']}")

                st.markdown("**Recent Quarterly Results**")

                earnings_cols = st.columns(min(len(earnings[:4]), 4))

                for i, earning in enumerate(earnings[:4]):
                    with earnings_cols[i]:
                        quarter_text = f"{earning.get('quarter', 'N/A')} {earning.get('year', 'N/A')}"

                        eps_actual = earning.get('eps_actual')
                        eps_estimate = earning.get('eps_estimate')
                        revenue_actual = earning.get('revenue_actual')

                        eps_actual_str = f"${eps_actual:.2f}" if eps_actual is not None else "N/A"
                        eps_estimate_str = f"${eps_estimate:.2f}" if eps_estimate is not None else "N/A"
                        revenue_str = f"${revenue_actual:,.0f}M" if revenue_actual is not None else "N/A"

                        st.markdown(f"""
                        <div class="earnings-card">
                            <div class="earnings-quarter">{quarter_text}</div>
                            <div class="earnings-metric">
                                <span class="earnings-label">EPS Actual:</span>
                                <span class="earnings-value">{eps_actual_str}</span>
                            </div>
                            <div class="earnings-metric">
                                <span class="earnings-label">EPS Estimate:</span>
                                <span class="earnings-value">{eps_estimate_str}</span>
                            </div>
                            <div class="earnings-metric">
                                <span class="earnings-label">Revenue:</span>
                                <span class="earnings-value">{revenue_str}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("No earnings data available")

    # 5. SENTIMENT ANALYSIS - Market sentiment and news
    if show_market_sentiment and data.get('sentiment_summary'):
        st.markdown("---")
        with st.container():
            st.markdown("### 📰 Market Sentiment")

            if data.get('sentiment_summary'):
                sentiment = data['sentiment_summary']

                sentiment_score = sentiment.get(
                    'overall_score', 'NEUTRAL').upper()
                confidence = sentiment.get('confidence', 0)

                if sentiment_score == 'POSITIVE':
                    sentiment_class = "sentiment-positive"
                    sentiment_emoji = "🟢"
                elif sentiment_score == 'NEGATIVE':
                    sentiment_class = "sentiment-negative"
                    sentiment_emoji = "🔴"
                else:
                    sentiment_class = "sentiment-neutral"
                    sentiment_emoji = "🟡"

                # Sentiment overview
                sent_overview_col1, sent_overview_col2 = st.columns(2)
                colA, colB, colC, colD, colE = st.columns([2, 1, 1, 1, 1])
                colA.markdown(f"**Overall Sentiment:** <span class='{sentiment_class}'>{sentiment_emoji} {sentiment_score}</span>",
                              unsafe_allow_html=True)
                colB.markdown(f"**Confidence:** {confidence:.1%}")
                colC.metric("Positive", sentiment["positive_count"])
                colD.metric("Neutral",  sentiment["neutral_count"])
                colE.metric("Negative", sentiment["negative_count"])
                # AI Summary
                if sentiment.get('summary_text'):
                    summary_text = sentiment['summary_text']
                    st.markdown("**AI-Powered Analysis**")
                    if len(summary_text) > 100:
                        st.markdown(f"""
                        <div class="ai-summary-box">
                            <p><strong>AI Analysis:</strong></p>
                            <p>{summary_text}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info(f"**Summary:** {summary_text}")

        # Detailed sentiment items
        if show_sentiment_details and data.get('sentiment_items'):
            st.markdown("**Recent News Articles**")
            sentiment_items = data['sentiment_items']

            if sentiment_items:
                for item in sentiment_items[:6]:
                    polarity = item.get('polarity', 0)
                    if polarity > 0.1:
                        sentiment_icon = "🟢"
                        sentiment_text = "Positive"
                    elif polarity < -0.1:
                        sentiment_icon = "🔴"
                        sentiment_text = "Negative"
                    else:
                        sentiment_icon = "🟡"
                        sentiment_text = "Neutral"

                    with st.expander(f"{sentiment_icon} {item.get('title', 'Unknown Title')}"):
                        st.write(
                            f"**Source:** {item.get('source', 'Unknown')}")
                        st.write(
                            f"**Sentiment:** {sentiment_text} (Score: {polarity:.2f})")
                        if item.get('url'):
                            st.write(
                                f"**Link:** [Read Full Article]({item['url']})")
                        if item.get('published_at'):
                            st.write(f"**Published:** {item['published_at']}")
            else:
                st.info("No recent news articles found")

    if show_data_sources and data.get('data_sources'):
        # Data Sources
        st.markdown("---")
        with st.container():
            st.markdown("### 🔗 Data Sources")
            if data.get('data_sources'):
                sources_html = ""
                for source in data['data_sources']:
                    sources_html += f'<span class="data-source-badge">{source}</span> '
                st.markdown(sources_html, unsafe_allow_html=True)
            else:
                st.info("Data sources information not available")

    if show_date_completed:
        # Footer
        st.markdown("---")
        st.markdown(
            f"*Analysis completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")


# Create main content area that we can completely control
# Ensure persistent placeholder across reruns
if 'main_content' not in st.session_state:
    st.session_state.main_content = st.empty()
main_content = st.session_state.main_content

# Analysis execution - IMMEDIATE UI UPDATE
if st.session_state.phase == "prebar":
    main_content.empty()
    with main_content.container():
        st.info("🔄 Starting new analysis...")
        st.progress(0)
    st.session_state.phase = "loading"
    st.rerun()

elif st.session_state.phase == "loading":
    main_content.empty()

    with main_content.container():
        progress_bar = st.progress(st.session_state.progress)
        status_text = st.empty()
        agent_status = st.empty()

    try:
        status_text.text("🔍 Connecting to multi-agent system...")
        progress_bar.progress(5)
        st.session_state.progress = 5

        import json
        final_data = None
        stopped_by_user = False

        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            with client.stream(
                "POST",
                "http://127.0.0.1:8000/analyze-stream",
                json={"symbol": symbol.upper()}
            ) as response:
                response.raise_for_status()

                agent_results = {}

                for line in response.iter_lines():
                    if st.session_state.stop_requested:     # <— NEW
                        status_text.text("⏹️ Analysis stopped by user")
                        progress_bar.progress(0)
                        agent_status.text("Request cancelled")
                        st.session_state.phase = "idle"
                        st.session_state.stop_requested = False
                        stopped_by_user = True
                        st.info("🛑 Analysis was stopped by user request")
                        try:
                            response.close()
                        except:
                            pass
                        break

                    if line.startswith("data: "):
                        try:
                            data_str = line[6:]  # Remove "data: " prefix
                            if data_str.strip():
                                update = json.loads(data_str)

                                # Update progress
                                progress = update.get('progress', 0)
                                progress_bar.progress(progress)
                                st.session_state.progress = progress

                                # Update status
                                message = update.get('message', '')
                                status_text.text(message)

                                # Show agent completion status
                                if update.get('status') == 'agent_complete':
                                    agent_name = update.get('agent', '')
                                    agent_status_text = update.get(
                                        'agent_status', 'success')

                                    if agent_status_text == 'success':
                                        emoji = "✅"
                                    else:
                                        emoji = "⚠️"

                                    agent_results[agent_name] = {
                                        'status': agent_status_text,
                                        'emoji': emoji
                                    }

                                    # Display agent status
                                    status_summary = " | ".join([
                                        f"{result['emoji']} {name.title()}"
                                        for name, result in agent_results.items()
                                    ])
                                    agent_status.text(
                                        f"Agents: {status_summary}")

                                # Handle completion
                                elif update.get('status') == 'complete':
                                    final_data = update.get('data')
                                    status_text.text("✅ Analysis complete!")
                                    progress_bar.progress(100)
                                    st.session_state.progress = 100
                                    break

                                # Handle cancellation (from backend when client disconnects)
                                elif update.get('status') == 'cancelled':
                                    cancel_msg = update.get(
                                        'message', 'Analysis cancelled')
                                    status_text.text(f"🛑 {cancel_msg}")
                                    st.session_state.phase = "idle"
                                    stopped_by_user = True
                                    break

                                # Handle errors
                                elif update.get('status') == 'error':
                                    error_msg = update.get(
                                        'message', 'Unknown error')
                                    st.session_state.phase = "error"
                                    st.session_state.stop_requested = False
                                    st.session_state.error_message = f"❌ Analysis failed: {error_msg}"
                                    # Clear any stored results
                                    if 'final_data' in st.session_state:
                                        del st.session_state.final_data
                                    st.rerun()  # Exit loading phase immediately

                        except json.JSONDecodeError:
                            continue

        # Reset analysis state and store results
        st.session_state.phase = "idle"
        st.session_state.stop_requested = False

        if final_data:
            st.session_state.final_data = final_data
            st.rerun()
        elif not stopped_by_user:
            st.error("❌ No data received from analysis")

    except httpx.TimeoutException:
        st.session_state.phase = "error"
        st.session_state.stop_requested = False
        st.session_state.error_message = f"⏰ Request timed out after {TIMEOUT_SECONDS} seconds. Try again in a moment."
        # Clear any stored results
        if 'final_data' in st.session_state:
            del st.session_state.final_data
        st.rerun()  # Exit loading phase immediately
    except httpx.HTTPStatusError as e:
        st.session_state.phase = "error"
        st.session_state.stop_requested = False
        # Clear any stored results
        if 'final_data' in st.session_state:
            del st.session_state.final_data

        if e.response.status_code == 400:
            st.session_state.error_message = "❌ Invalid stock ticker. Please enter a valid ticker symbol (e.g., AAPL, GOOGL, TSLA)"
        elif e.response.status_code == 404:
            st.session_state.error_message = "❌ Stock ticker not found. Please verify the symbol is correct and try again."
        elif e.response.status_code == 422:
            st.session_state.error_message = "❌ Invalid stock ticker. Please enter a valid ticker symbol (e.g., AAPL, GOOGL, TSLA)"
        else:
            try:
                error_text = e.response.text
                st.session_state.error_message = f"❌ HTTP Error {e.response.status_code}: {error_text}"
            except:
                st.session_state.error_message = f"❌ HTTP Error {e.response.status_code}: Unable to retrieve details"
        st.rerun()  # Exit loading phase immediately
    except httpx.RequestError as e:
        st.session_state.phase = "error"
        st.session_state.stop_requested = False
        st.session_state.error_message = f"🔌 Connection Error: {str(e)}. Make sure your backend is running at http://127.0.0.1:8000"
        # Clear any stored results
        if 'final_data' in st.session_state:
            del st.session_state.final_data
        st.rerun()  # Exit loading phase immediately
    except Exception as e:
        st.session_state.phase = "error"
        st.session_state.stop_requested = False
        st.session_state.error_message = f"💥 {e}"
        # Clear any stored results
        if 'final_data' in st.session_state:
            del st.session_state.final_data
        st.rerun()  # Exit loading phase immediately

# Display error state
if st.session_state.phase == "error" and "error_message" in st.session_state:
    main_content.empty()
    with main_content.container():
        st.error(st.session_state.error_message)

# Display stored results ONLY when completely idle (not loading or preparing)
if st.session_state.phase == "idle" and "final_data" in st.session_state:
    main_content.empty()
    with main_content.container():
        display_stock_analysis(st.session_state.final_data)


# Only show instructions when idle and no results stored
if st.session_state.phase == "idle" and 'final_data' not in st.session_state:
    main_content.empty()
    with main_content.container():
        st.markdown("### 🚀 Ready to Analyze")
        st.info("💡 Enter a stock symbol above and click 'Analyze' to get comprehensive stock analysis from our multi-agent system.")

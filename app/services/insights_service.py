#!/usr/bin/env python3
"""
Insights Service - Business logic for AI-generated reports and newsletters
Generates airline/industry reports and weekly newsletters using Gemini AI
"""

import logging
import markdown
import pytz
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Use Eastern Time for all date operations (TSA and aviation industry uses ET)
EASTERN_TZ = pytz.timezone('US/Eastern')


class InsightsService:
    """Service for generating AI-powered insights, reports, and newsletters"""

    def __init__(self, gemini_service, database_service, stock_service=None, sec_service=None, bts_service=None, financial_service=None, fred_service=None):
        """
        Initialize insights service

        Args:
            gemini_service: GeminiService instance for AI generation
            database_service: DatabaseService instance for data retrieval
            stock_service: StockDataService instance for stock data (optional)
            sec_service: SECFilingsService instance for SEC filings (optional)
            bts_service: BTSService instance for carrier financials (optional)
            financial_service: FinancialDataService for balance sheet data (optional)
            fred_service: FREDCreditSpreadsFinal for credit spread benchmarks (optional)
        """
        self.gemini = gemini_service
        self.db = database_service
        self.stock_service = stock_service
        self.sec_service = sec_service
        self.bts_service = bts_service
        self.financial_service = financial_service
        self.fred_service = fred_service
        logger.info("✅ Insights service initialized")

    def generate_airline_report(
        self,
        subject: str,
        report_type: str = "airline",
        days: int = 30
    ) -> Optional[Dict]:
        """
        Generate an airline or industry sector report

        Args:
            subject: Airline name (e.g., "Delta Air Lines") or sector (e.g., "Aircraft Leasing")
            report_type: Either "airline" or "sector"
            days: Number of days of historical data to analyze (default: 30)

        Returns:
            Dictionary with report data or None if generation failed
        """
        try:
            logger.info(f"📊 Generating {report_type} report for: {subject}")

            # Check for cached report (within 24 hours)
            cached_report = self.db.get_cached_report(subject, report_type)
            if cached_report:
                logger.info(f"✅ Using cached report for {subject}")
                return cached_report

            # Calculate date range using Eastern Time (aviation industry standard)
            end_date = datetime.now(EASTERN_TZ).replace(tzinfo=None)
            start_date = end_date - timedelta(days=days)

            # Gather data from database with smart filtering
            # Use hybrid approach: airline-specific + industry-wide articles
            airline_keywords = self._extract_airline_keywords(subject)

            # Get airline-specific articles (70% of total)
            airline_articles = self.db.get_articles(
                start_date=start_date,
                end_date=end_date,
                keywords=airline_keywords,
                limit=70
            )

            # Get industry-wide articles (30% of total)
            industry_articles = self.db.get_articles(
                start_date=start_date,
                end_date=end_date,
                limit=30
            )

            # Combine and deduplicate articles
            seen_ids = set()
            news_articles = []

            # Prioritize airline-specific articles
            for article in (airline_articles or []):
                article_id = article.get('id') or article.get('title')
                if article_id not in seen_ids:
                    seen_ids.add(article_id)
                    news_articles.append(article)

            # Add industry-wide articles
            for article in (industry_articles or []):
                article_id = article.get('id') or article.get('title')
                if article_id not in seen_ids:
                    seen_ids.add(article_id)
                    news_articles.append(article)

            tsa_data = self.db.get_tsa_data(
                start_date=start_date,
                end_date=end_date
            )

            fred_records = self.db.get_fred_data(limit=1)
            fred_data = {'data': fred_records[0]} if fred_records else None

            # Get stock data if service is available and this is an airline report
            stock_data = None
            if self.stock_service and report_type == 'airline':
                stock_data = self.stock_service.get_stock_data(
                    airline_name=subject,
                    period='1mo',
                    include_history=True
                )

            # Get SEC filings if service is available and this is an airline report
            sec_filings = None
            if self.sec_service and report_type == 'airline':
                sec_filings = self.sec_service.get_recent_filings(
                    airline_name=subject,
                    filing_types=['10-K', '10-Q', '8-K'],
                    max_results=5
                )

            # Get BTS carrier financials if service is available
            carrier_financials = None
            if self.bts_service and report_type in ['airline', 'credit_analysis', 'comprehensive']:
                carrier_code = self.bts_service.get_carrier_by_name(subject)
                if carrier_code:
                    carrier_financials = self.bts_service.get_carrier_financials(carrier_code)
                    if carrier_financials:
                        logger.info(f"✅ Retrieved BTS financials for {carrier_code}")
                else:
                    logger.warning(f"⚠️ Could not match airline name '{subject}' to carrier code")

            # Get balance sheet data from Yahoo Finance for credit analysis
            balance_sheet_data = None
            if self.financial_service and report_type in ['credit_analysis', 'comprehensive']:
                balance_sheet_data = self.financial_service.get_balance_sheet_data(subject)
                if balance_sheet_data:
                    logger.info(f"✅ Retrieved balance sheet data for {subject}")
                else:
                    logger.warning(f"⚠️ Could not fetch balance sheet data for '{subject}'")

            # Get credit spread benchmarks (multi-tier) for credit analysis
            credit_benchmarks = None
            if self.fred_service and report_type in ['credit_analysis', 'comprehensive']:
                credit_benchmarks = self.fred_service.get_credit_spread_benchmarks()
                if credit_benchmarks and credit_benchmarks.get('success'):
                    logger.info(f"✅ Retrieved credit spread benchmarks")
                else:
                    logger.warning(f"⚠️ Could not fetch credit spread benchmarks")

            # Log data availability for debugging
            if not news_articles:
                logger.warning(f"⚠️ No news articles found for {subject} from {start_date.date()} to {end_date.date()}")
            if not tsa_data:
                logger.warning(f"⚠️ No TSA data found from {start_date.date()} to {end_date.date()}")
            if not fred_data:
                logger.warning(f"⚠️ No FRED data available")
            if report_type == 'airline' and not stock_data:
                logger.warning(f"⚠️ No stock data available for {subject}")
            if report_type == 'airline' and not sec_filings:
                logger.warning(f"⚠️ No SEC filings available for {subject}")

            logger.info(f"📊 Data collected for {subject}: {len(news_articles) if news_articles else 0} articles, "
                       f"{len(tsa_data) if tsa_data else 0} TSA records, "
                       f"FRED: {'Yes' if fred_data else 'No'}, "
                       f"Stock: {'Yes' if stock_data else 'No'}, "
                       f"SEC: {'Yes' if sec_filings else 'No'}, "
                       f"BTS: {'Yes' if carrier_financials else 'No'}, "
                       f"BalanceSheet: {'Yes' if balance_sheet_data else 'No'}, "
                       f"CreditBenchmarks: {'Yes' if credit_benchmarks else 'No'}")

            # Build prompt based on report type
            if report_type == 'credit_analysis':
                prompt = self._build_credit_analysis_prompt(
                    subject=subject,
                    news_articles=news_articles,
                    tsa_data=tsa_data,
                    fred_data=fred_data,
                    stock_data=stock_data,
                    sec_filings=sec_filings,
                    carrier_financials=carrier_financials,
                    balance_sheet_data=balance_sheet_data,
                    credit_benchmarks=credit_benchmarks,
                    period_start=start_date,
                    period_end=end_date
                )
            elif report_type == 'leasing_recommendation':
                prompt = self._build_leasing_recommendation_prompt(
                    subject=subject,
                    news_articles=news_articles,
                    stock_data=stock_data,
                    period_start=start_date,
                    period_end=end_date
                )
            elif report_type == 'comprehensive':
                prompt = self._build_comprehensive_report_prompt(
                    subject=subject,
                    news_articles=news_articles,
                    tsa_data=tsa_data,
                    fred_data=fred_data,
                    stock_data=stock_data,
                    sec_filings=sec_filings,
                    period_start=start_date,
                    period_end=end_date
                )
            else:
                # Default for 'airline' or 'sector'
                prompt = self._build_report_prompt(
                    subject=subject,
                    report_type=report_type,
                    news_articles=news_articles,
                    tsa_data=tsa_data,
                    fred_data=fred_data,
                    stock_data=stock_data,
                    sec_filings=sec_filings,
                    period_start=start_date,
                    period_end=end_date
                )

            # Generate content using Gemini
            markdown_content = self.gemini.generate_content(prompt, temperature=0.7)

            if not markdown_content:
                logger.error(f"❌ Failed to generate report for {subject}")
                return None

            # Convert markdown to HTML
            html_content = markdown.markdown(
                markdown_content,
                extensions=['extra', 'nl2br', 'sane_lists']
            )

            # Parse sections from markdown
            sections = self._parse_sections(markdown_content)

            # Calculate cache expiry (24 hours)
            cached_until = datetime.now() + timedelta(hours=24)

            # Prepare report document
            report_data = {
                'report_type': report_type,
                'subject': subject,
                'generated_at': datetime.now(),
                'period_start': start_date,
                'period_end': end_date,
                'markdown_content': markdown_content,
                'html_content': html_content,
                'sections': sections,
                'metadata': {
                    'articles_analyzed': len(news_articles) if news_articles else 0,
                    'tsa_days': len(tsa_data) if tsa_data else 0,
                    'fred_included': fred_data is not None,
                    'stock_included': stock_data is not None,
                    'sec_filings_included': sec_filings is not None,
                    'bts_included': carrier_financials is not None,
                    'balance_sheet_included': balance_sheet_data is not None,
                    'credit_benchmarks_included': credit_benchmarks is not None,
                    'model': 'gemini-2.0-flash-exp'
                },
                'cached_until': cached_until
            }

            # Save to database
            report_id = self.db.save_airline_report(report_data)
            report_data['id'] = report_id

            logger.info(f"✅ Report generated successfully for {subject} (ID: {report_id})")
            return report_data

        except Exception as e:
            logger.error(f"❌ Error generating airline report: {e}")
            return None

    def generate_weekly_newsletter(
        self,
        week_offset: int = 0,
        frequency: str = 'weekly',
        format_type: str = 'html',
        sections: Dict[str, bool] = None
    ) -> Optional[Dict]:
        """
        Generate a weekly newsletter covering the previous week's aviation industry developments

        Args:
            week_offset: Number of weeks back to generate (0 = last week, 1 = 2 weeks ago, etc.)
            frequency: Newsletter frequency ('weekly', 'monthly' - future)
            format_type: Output format ('html', 'pdf', 'both')
            sections: Dict of section flags (executive_summary, market_indicators, etc.)

        Returns:
            Dictionary with newsletter data or None if generation failed
        """
        if sections is None:
            sections = {
                'executive_summary': True,
                'market_indicators': True,
                'industry_news': True,
                'risk_analysis': True,
                'outlook': True
            }
        try:
            logger.info(f"📰 Generating weekly newsletter (offset: {week_offset})")

            # Calculate week boundaries (Monday to Sunday) using Eastern Time
            today = datetime.now(EASTERN_TZ)
            days_since_monday = today.weekday()
            last_monday = today - timedelta(days=days_since_monday + 7 + (week_offset * 7))
            last_sunday = last_monday + timedelta(days=6)

            week_start = last_monday.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
            week_end = last_sunday.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=None)

            logger.info(f"📅 Newsletter period: {week_start.date()} to {week_end.date()}")

            # Get previous newsletter for historical context
            previous_newsletter = self.db.get_latest_newsletter()

            # Gather data from database
            news_articles = self.db.get_articles(
                start_date=week_start,  # Pass datetime object, not string
                end_date=week_end,      # Pass datetime object, not string
                limit=200
            )

            tsa_data = self.db.get_tsa_data(
                start_date=week_start.strftime('%Y-%m-%d'),
                end_date=week_end.strftime('%Y-%m-%d')
            )

            # get_fred_data() returns List[Dict], but _format_fred_data() expects Dict with 'data' key
            fred_records = self.db.get_fred_data(limit=1)
            fred_data = {'data': fred_records[0]} if fred_records else None

            # Log data availability
            if not news_articles:
                logger.warning(f"⚠️ No news articles found for week {week_start.date()} to {week_end.date()}")
            if not tsa_data:
                logger.warning(f"⚠️ No TSA data found for week {week_start.date()} to {week_end.date()}")
            if not fred_data:
                logger.warning(f"⚠️ No FRED data available")

            logger.info(f"📊 Data collected: {len(news_articles) if news_articles else 0} articles, "
                       f"{len(tsa_data) if tsa_data else 0} TSA records, "
                       f"FRED: {'Yes' if fred_data else 'No'}")

            # Build comprehensive newsletter prompt
            prompt = self._build_newsletter_prompt(
                week_start=week_start,
                week_end=week_end,
                news_articles=news_articles,
                tsa_data=tsa_data,
                fred_data=fred_data,
                previous_newsletter=previous_newsletter,
                sections=sections
            )

            # Generate content using Gemini
            markdown_content = self.gemini.generate_content(prompt, temperature=0.8)

            if not markdown_content:
                logger.error(f"❌ Failed to generate newsletter")
                return None

            # Convert markdown to HTML
            html_content = markdown.markdown(
                markdown_content,
                extensions=['extra', 'nl2br', 'sane_lists']
            )

            # Parse sections from markdown
            parsed_sections = self._parse_sections(markdown_content)

            # Extract predictions from last week if available
            predictions_from_last_week = None
            if previous_newsletter and 'sections' in previous_newsletter:
                predictions_from_last_week = previous_newsletter['sections'].get('week_ahead')

            # Prepare newsletter document
            newsletter_data = {
                'week_start': week_start,
                'week_end': week_end,
                'generated_at': datetime.now(),
                'markdown_content': markdown_content,
                'html_content': html_content,
                'sections': parsed_sections,
                'articles_analyzed': len(news_articles) if news_articles else 0,
                'previous_newsletter_id': previous_newsletter.get('id') if previous_newsletter else None,
                'predictions_from_last_week': predictions_from_last_week,
                'frequency': frequency,
                'format': format_type,
                'metadata': {
                    'tsa_days': len(tsa_data) if tsa_data else 0,
                    'fred_included': fred_data is not None,
                    'model': 'gemini-2.0-flash-exp'
                }
            }

            # Save to database
            newsletter_id = self.db.save_weekly_newsletter(newsletter_data)
            newsletter_data['id'] = newsletter_id

            logger.info(f"✅ Newsletter generated successfully (ID: {newsletter_id})")
            return newsletter_data

        except Exception as e:
            logger.error(f"❌ Error generating weekly newsletter: {e}")
            return None

    def _build_report_prompt(
        self,
        subject: str,
        report_type: str,
        news_articles: List[Dict],
        tsa_data: List[Dict],
        fred_data: Optional[Dict],
        stock_data: Optional[Dict] = None,
        sec_filings: Optional[Dict] = None,
        period_start: datetime = None,
        period_end: datetime = None
    ) -> str:
        """Build comprehensive prompt for airline/sector report"""

        # Format news articles
        news_summary = self._format_news_articles(news_articles)

        # Format TSA data
        tsa_summary = self._format_tsa_data(tsa_data)

        # Format FRED data
        fred_summary = self._format_fred_data(fred_data)

        # Format stock data
        stock_summary = self._format_stock_data(stock_data)

        # Format SEC filings
        sec_summary = self._format_sec_filings(sec_filings)

        prompt = f"""You are an expert aviation industry analyst. Generate a comprehensive intelligence report about {subject}.

**Report Type**: {report_type.title()}
**Subject**: {subject}
**Period**: {period_start.strftime('%B %d, %Y') if period_start else 'Recent'} to {period_end.strftime('%B %d, %Y') if period_end else 'Current'}

**Available Data**:

{news_summary}

{tsa_summary}

{fred_summary}

{stock_summary}

{sec_summary}

**Instructions**:
Generate a professional, data-driven report in Markdown format with the following sections:

## Executive Summary
- 2-3 paragraph overview of key findings
- Highlight most significant developments
- Include stock performance summary if available

## News Analysis
- Analyze major news stories and their implications
- Identify trends and patterns
- Quote specific articles when relevant

## Financial Performance
- Analyze stock price performance and volatility (if available)
- Review recent SEC filings and their implications (if available)
- Compare performance to sector benchmarks

## Market Data Insights
- Analyze TSA passenger data trends
- Interpret credit spread data and financial conditions
- Connect market data to news developments and stock performance

## Key Developments
- List and analyze the most important events
- Include recent SEC filings (10-K, 10-Q, 8-K)
- Provide context and industry implications

## Risk Assessment
- Identify potential risks and challenges
- Consider financial metrics and stock volatility
- Rate overall risk level (Low/Moderate/High)

## Outlook & Recommendations
- Forward-looking analysis
- Strategic recommendations based on all available data
- Investment positioning considerations

**Style Guidelines**:
- Professional, analytical tone
- Use data to support all claims
- Include specific numbers and percentages
- Cite news sources when quoting
- Be objective and balanced
- Use markdown formatting (headers, lists, bold, etc.)

Generate the report now:"""

        return prompt

    def _build_credit_analysis_prompt(
        self,
        subject: str,
        news_articles: List[Dict],
        tsa_data: List[Dict],
        fred_data: Optional[Dict],
        stock_data: Optional[Dict],
        sec_filings: Optional[Dict],
        carrier_financials: Optional[Dict],
        balance_sheet_data: Optional[Dict] = None,
        credit_benchmarks: Optional[Dict] = None,
        period_start: datetime = None,
        period_end: datetime = None
    ) -> str:
        """Build specialized credit analysis prompt from lender/bondholder perspective"""

        # Format data sources
        news_summary = self._format_news_articles(news_articles)
        tsa_summary = self._format_tsa_data(tsa_data)
        fred_summary = self._format_fred_data(fred_data)
        stock_summary = self._format_stock_data(stock_data)
        sec_summary = self._format_sec_filings(sec_filings)
        carrier_summary = self._format_carrier_financials(carrier_financials)
        balance_sheet_summary = self._format_balance_sheet_data(balance_sheet_data)

        # Format comprehensive credit analysis section (new)
        credit_analysis_summary = self._format_credit_analysis(
            balance_sheet_data=balance_sheet_data,
            credit_benchmarks=credit_benchmarks
        )

        prompt = f"""You are a senior airline credit analyst. Generate a comprehensive credit analysis report for {subject} covering {period_start.strftime('%B %d, %Y')} to {period_end.strftime('%B %d, %Y')}.

**Perspective**: Analyze from a lender/bondholder perspective, focusing on creditworthiness and financial risk.

**Available Data**:

{credit_analysis_summary}

{balance_sheet_summary}

{carrier_summary}

{news_summary}

{tsa_summary}

{fred_summary}

{stock_summary}

{sec_summary}

**Required Report Sections** (use these exact H2 headers):

## Executive Summary
Provide a 3-4 paragraph overview of the credit profile, key risks, and rating outlook. Include the estimated credit rating from the data.

## Credit Rating & Spread Analysis
Use the provided credit rating estimation and spread benchmarks to:
- Present the estimated credit rating based on financial metrics
- Compare company's credit profile to AA, A, BBB, and BB benchmarks
- Analyze where the airline falls in the rating spectrum
- Discuss spread levels relative to each rating tier
- Assess market stress conditions

## Financial Health Metrics
- Debt-to-EBITDA ratio trends
- Liquidity position (cash, available credit)
- Interest coverage ratios
- Free cash flow analysis
- Leverage metrics

## Revenue & Profitability Trends
- Revenue trends from TSA data and financial statements
- Operating margin analysis
- Unit revenue (RASM) performance
- Cost structure efficiency

## Risk Assessment
- Operational risks (labor, fuel, competition)
- Market risks (economic downturn, demand shocks)
- Regulatory and legal risks
- Covenant compliance status
- **Risk Level: High/Medium/Low** (use this exact format)

## Credit Outlook & Recommendation
- 12-month credit outlook
- Probability of rating changes
- Recommendation for bondholders/lenders
- Key metrics to monitor

**Formatting Requirements**:
- Use markdown formatting
- Include specific data points and percentages where available
- Use bullet points for clarity
- Highlight risk levels using: **Risk Level: High/Medium/Low**
- Include specific metrics and numbers from the data provided
- Reference the estimated credit rating and spread benchmarks
- Be analytical and data-driven

Generate the credit analysis report now:"""

        return prompt

    def _build_leasing_recommendation_prompt(
        self,
        subject: str,
        news_articles: List[Dict],
        stock_data: Optional[Dict],
        period_start: datetime,
        period_end: datetime
    ) -> str:
        """Build specialized leasing recommendation prompt from aircraft lessor perspective"""

        # Format data sources
        news_summary = self._format_news_articles(news_articles)
        stock_summary = self._format_stock_data(stock_data)

        prompt = f"""You are a senior aircraft leasing analyst. Generate a comprehensive leasing recommendation report for {subject} covering {period_start.strftime('%B %d, %Y')} to {period_end.strftime('%B %d, %Y')}.

**Perspective**: Analyze from an aircraft lessor perspective, focusing on lease rates, fleet strategy, and market conditions.

**Available Data**:

{news_summary}

{stock_summary}

**Note**: Since proprietary lease rate databases are not available, provide qualitative analysis based on industry trends, news reports, and financial data.

**Required Report Sections** (use these exact H2 headers):

## Executive Summary
Provide a 3-4 paragraph overview of the airline's attractiveness as a lessee, key opportunities, and risks.

## Fleet Composition & Strategy
- Current fleet breakdown (aircraft types, ages) based on news and public data
- Recent aircraft orders and deliveries
- Fleet modernization initiatives
- Narrowbody vs. widebody mix

## Market Conditions & Lease Rate Trends
- Current lease rate environment for key aircraft types
- Supply/demand dynamics in aircraft leasing market
- Industry-wide trends affecting lease rates
- Airline's historical lease vs. own strategy

## Lessee Credit Profile
- Financial stability as a lessee
- On-time lease payment history (based on news/reports)
- Debt levels and ability to meet obligations
- Stock performance trends

## Route Network & Capacity Trends
- Network expansion or contraction
- Utilization rates and productivity
- International vs. domestic exposure
- Competitive position in key markets

## Leasing Recommendation
- **Recommendation**: Favorable / Neutral / Cautious (use this exact format)
- Preferred aircraft types to lease to this airline
- Recommended lease structure (operating vs. finance)
- Suggested lease terms and conditions
- Key risk mitigations
- **Risk Level: High/Medium/Low** (use this exact format)

**Formatting Requirements**:
- Use markdown formatting
- Include specific fleet data where available
- Use bullet points for clarity
- Highlight risk levels using: **Risk Level: High/Medium/Low**
- Provide actionable recommendations
- Be practical and market-focused

Generate the leasing recommendation report now:"""

        return prompt

    def _build_comprehensive_report_prompt(
        self,
        subject: str,
        news_articles: List[Dict],
        tsa_data: List[Dict],
        fred_data: Optional[Dict],
        stock_data: Optional[Dict],
        sec_filings: Optional[Dict],
        period_start: datetime,
        period_end: datetime
    ) -> str:
        """Build comprehensive report combining credit, leasing, and market analysis"""

        # Format data sources
        news_summary = self._format_news_articles(news_articles)
        tsa_summary = self._format_tsa_data(tsa_data)
        fred_summary = self._format_fred_data(fred_data)
        stock_summary = self._format_stock_data(stock_data)
        sec_summary = self._format_sec_filings(sec_filings)

        prompt = f"""You are a senior aviation intelligence analyst. Generate a comprehensive multi-perspective report for {subject} covering {period_start.strftime('%B %d, %Y')} to {period_end.strftime('%B %d, %Y')}.

**Perspective**: Provide integrated analysis from three perspectives: credit/bondholder, aircraft lessor, and market analyst.

**Available Data**:

{news_summary}

{tsa_summary}

{fred_summary}

{stock_summary}

{sec_summary}

**Required Report Sections** (use these exact H2 headers):

## Executive Summary
Provide a 4-5 paragraph overview integrating credit, leasing, and market perspectives.

## Credit Analysis
### Credit Rating & Financial Health
- Credit rating trends and bond spreads
- Key financial metrics (leverage, liquidity, profitability)
- Debt structure and covenant compliance

### Credit Risk Assessment
- Operational and market risks
- 12-month credit outlook
- **Credit Risk Level: High/Medium/Low** (use this exact format)

## Leasing Analysis
### Fleet Strategy & Composition
- Current fleet breakdown and modernization plans
- Recent orders and lease commitments
- Fleet age and efficiency

### Lessee Attractiveness
- Financial stability as a lessee
- Lease vs. own strategy
- Recommended aircraft types and lease structures
- **Leasing Risk Level: High/Medium/Low** (use this exact format)

## Market & Operational Analysis
### Revenue & Capacity Trends
- TSA passenger data trends
- Load factor and yield performance
- Route network developments

### Competitive Position
- Market share in key segments
- Pricing power and competitive advantages
- Industry positioning

## Integrated Risk Assessment
- Combined risk view across credit, leasing, and operational dimensions
- Interconnected risk factors
- Scenario analysis (best/base/worst case)
- **Overall Risk Level: High/Medium/Low** (use this exact format)

## Strategic Recommendations
- For bondholders/lenders
- For aircraft lessors
- For equity investors
- Key metrics to monitor

**Formatting Requirements**:
- Use markdown formatting with clear section hierarchy
- Include specific data points and percentages
- Use bullet points for clarity
- Highlight risk levels using: **Risk Level: High/Medium/Low**
- Integrate perspectives across sections
- Be comprehensive yet concise

Generate the comprehensive report now:"""

        return prompt

    def _build_newsletter_prompt(
        self,
        week_start: datetime,
        week_end: datetime,
        news_articles: List[Dict],
        tsa_data: List[Dict],
        fred_data: Optional[Dict],
        previous_newsletter: Optional[Dict],
        sections: Dict[str, bool] = None
    ) -> str:
        """Build comprehensive prompt for weekly newsletter"""

        if sections is None:
            sections = {
                'executive_summary': True,
                'market_indicators': True,
                'industry_news': True,
                'risk_analysis': True,
                'outlook': True
            }

        # Format news articles
        news_summary = self._format_news_articles(news_articles)

        # Format TSA data
        tsa_summary = self._format_tsa_data(tsa_data)

        # Format FRED data
        fred_summary = self._format_fred_data(fred_data)

        # Format previous newsletter context
        previous_context = ""
        if previous_newsletter:
            prev_start = previous_newsletter.get('week_start', 'Unknown')
            prev_end = previous_newsletter.get('week_end', 'Unknown')
            previous_context = f"""
**Previous Week's Newsletter** ({prev_start} to {prev_end}):
- Use this for historical context and ongoing story tracking
- Reference any predictions made last week and verify against this week's data
"""

        # Build sections list based on configuration
        sections_text = []

        if sections.get('executive_summary', True):
            sections_text.append("""## Week in Review
- Engaging opening paragraph summarizing the week
- Highlight the top 3-5 stories with context
- Connect related developments""")

        if sections.get('industry_news', True):
            sections_text.append("""## Industry Spotlight
- Deep dive into the most significant story of the week
- Provide expert analysis and implications
- Include relevant data points""")

        if sections.get('market_indicators', True):
            sections_text.append("""## By The Numbers
- Present key statistics from TSA and FRED data
- Compare to previous periods
- Identify notable trends
- Use bullet points and percentages""")

        if sections.get('risk_analysis', True):
            sections_text.append("""## Ongoing Developments
- Update on continuing stories from previous weeks
- Track how situations have evolved
- Note any predictions that materialized or didn't""")

        if sections.get('outlook', True):
            sections_text.append("""## Week Ahead
- Forward-looking analysis
- Upcoming events or developments to watch
- Predictions based on current trends
- Potential market movers

## Bottom Line
- Concise 2-3 sentence summary
- Key takeaway for industry professionals""")

        sections_instructions = "\n\n".join(sections_text)

        prompt = f"""You are the editor of a premium aviation industry newsletter. Generate an engaging, informative weekly newsletter.

**Newsletter Period**: Week of {week_start.strftime('%B %d, %Y')} to {week_end.strftime('%B %d, %Y')}

**Available Data**:

{news_summary}

{tsa_summary}

{fred_summary}

{previous_context}

**Instructions**:
Generate a professional newsletter in Markdown format with the following sections:

{sections_instructions}

**Style Guidelines**:
- Engaging, newsletter-style writing (not overly formal)
- Clear, scannable structure with headers
- Use specific data points and numbers
- Include context for non-expert readers
- Balance detail with readability
- Use markdown formatting effectively

Generate the newsletter now:"""

        return prompt

    def _extract_airline_keywords(self, subject: str) -> List[str]:
        """
        Extract airline name variations and ticker symbols for filtering

        Args:
            subject: Airline name or subject string

        Returns:
            List of keyword variations (full name, short name, ticker symbols)
        """
        # Comprehensive airline keyword mapping
        airline_map = {
            'United Airlines': ['United Airlines', 'United', 'UAL', 'UA'],
            'Delta Air Lines': ['Delta Air Lines', 'Delta', 'DAL', 'DL'],
            'American Airlines': ['American Airlines', 'American', 'AAL', 'AA'],
            'Southwest Airlines': ['Southwest Airlines', 'Southwest', 'LUV', 'WN'],
            'JetBlue Airways': ['JetBlue Airways', 'JetBlue', 'JBLU', 'B6'],
            'Alaska Airlines': ['Alaska Airlines', 'Alaska', 'ALK', 'AS'],
            'Spirit Airlines': ['Spirit Airlines', 'Spirit', 'SAVE', 'NK'],
            'Frontier Airlines': ['Frontier Airlines', 'Frontier', 'ULCC', 'F9'],
            'Hawaiian Airlines': ['Hawaiian Airlines', 'Hawaiian', 'HA'],
            'Allegiant Air': ['Allegiant Air', 'Allegiant', 'ALGT', 'G4'],
            'Sun Country': ['Sun Country', 'Sun Country Airlines', 'SNCY', 'SY']
        }

        # Try to find exact match or partial match
        for full_name, keywords in airline_map.items():
            if subject in full_name or full_name in subject:
                logger.info(f"📍 Matched '{subject}' to airline keywords: {keywords}")
                return keywords

        # Fallback: generate generic keywords from subject
        fallback_keywords = [
            subject,
            subject.replace(' Airlines', ''),
            subject.replace(' Airways', ''),
            subject.replace(' Air', '')
        ]

        logger.info(f"📍 Using fallback keywords for '{subject}': {fallback_keywords}")
        return fallback_keywords

    def _format_news_articles(self, articles: List[Dict]) -> str:
        """Format news articles for prompt inclusion"""
        if not articles:
            return "**News Articles**: No recent articles available."

        formatted = f"**News Articles** ({len(articles)} articles):\n\n"
        for i, article in enumerate(articles[:50], 1):  # Limit to 50 most recent
            title = article.get('title', 'Untitled')
            summary = article.get('summary', 'No summary')
            source = article.get('source', 'Unknown')
            published = article.get('published_date', 'Unknown date')

            formatted += f"{i}. **{title}** ({source}, {published})\n"
            formatted += f"   {summary}\n\n"

        return formatted

    def _format_tsa_data(self, tsa_data: List[Dict]) -> str:
        """Format TSA data for prompt inclusion"""
        if not tsa_data:
            return "**TSA Passenger Data**: No recent data available."

        formatted = f"**TSA Passenger Screening Data** ({len(tsa_data)} days):\n\n"

        # Calculate aggregates - handle both field name formats
        total_current = sum(day.get('current_throughput', day.get('current_year', 0)) for day in tsa_data)

        # Show comparison to 2019 if available
        avg_comparison = sum(day.get('compared_to_2019', 0) for day in tsa_data if day.get('compared_to_2019')) / len(tsa_data) if tsa_data else 0

        if total_current > 0:
            formatted += f"- Total Passengers (Period): {total_current:,}\n"
            if avg_comparison > 0:
                formatted += f"- Average vs 2019: {avg_comparison:.1f}%\n"
            formatted += f"- Period: {tsa_data[-1].get('date')} to {tsa_data[0].get('date')}\n\n"

        # Show recent days (last 7 days or all available)
        formatted += "Recent Daily Data:\n"
        for day in sorted(tsa_data, key=lambda x: x.get('date', ''), reverse=True)[:7]:
            date = day.get('date', 'Unknown')
            current = day.get('current_throughput', day.get('current_year', 0))
            formatted += f"- {date}: {current:,} passengers\n"

        return formatted

    def _format_fred_data(self, fred_data: Optional[Dict]) -> str:
        """Format FRED credit spread data for prompt inclusion"""
        if not fred_data:
            return "**Credit Spread Data**: Not available."

        data = fred_data.get('data', {})
        spread = data.get('credit_spread_bps', 'N/A')
        condition = data.get('spread_description', 'N/A')
        risk_level = data.get('risk_level', 'N/A')
        trend = data.get('trend', 'N/A')
        data_date = data.get('data_date', 'Unknown')

        formatted = f"""**Credit Spread Data** (as of {data_date}):
- Credit Spread: {spread} basis points
- Market Condition: {condition}
- Risk Level: {risk_level}
- Trend: {trend}
"""

        return formatted

    def _format_stock_data(self, stock_data: Optional[Dict]) -> str:
        """Format stock data for prompt inclusion"""
        if not stock_data:
            return "**Stock Data**: Not available."

        ticker = stock_data.get('ticker', 'N/A')
        current_price = stock_data.get('current_price')
        day_change_pct = stock_data.get('day_change_percent')
        performance = stock_data.get('performance', {})

        day_change_str = f"{day_change_pct:+.2f}%" if day_change_pct else "N/A"

        formatted = f"""**Stock Data** ({ticker}):
- Current Price: ${current_price:.2f} USD
- Day Change: {day_change_str}
- Market Cap: ${stock_data.get('market_cap', 0):,.0f}
- P/E Ratio: {stock_data.get('pe_ratio', 'N/A')}
- 52-Week High: ${stock_data.get('fifty_two_week_high', 'N/A')}
- 52-Week Low: ${stock_data.get('fifty_two_week_low', 'N/A')}
- Beta: {stock_data.get('beta', 'N/A')}
"""

        # Add performance metrics if available
        if performance:
            formatted += f"""
**Recent Performance** ({performance.get('days_analyzed', 30)} days):
- Period Return: {performance.get('period_return_pct', 'N/A'):+.2f}%
- Period High: ${performance.get('period_high', 'N/A')}
- Period Low: ${performance.get('period_low', 'N/A')}
- Volatility: {performance.get('volatility_pct', 'N/A'):.2f}%
"""

        return formatted

    def _format_sec_filings(self, sec_filings: Optional[Dict]) -> str:
        """Format SEC filings for prompt inclusion"""
        if not sec_filings or not sec_filings.get('filings'):
            return "**SEC Filings**: Not available."

        filings = sec_filings.get('filings', [])
        company_name = sec_filings.get('company_name', 'Unknown')

        formatted = f"""**Recent SEC Filings** ({company_name}):

"""

        for filing in filings[:5]:  # Limit to 5 most recent
            filing_type = filing.get('filing_type', 'Unknown')
            filing_date = filing.get('filing_date', 'Unknown')
            description = filing.get('description', 'No description')

            formatted += f"- **{filing_type}** (Filed: {filing_date})\n"
            if description:
                formatted += f"  {description}\n"

        return formatted

    def _format_carrier_financials(self, carrier_financials: Optional[Dict]) -> str:
        """Format BTS Form 41 carrier financials for prompt inclusion"""
        if not carrier_financials:
            return "**Carrier Financial Data (BTS Form 41)**: Not available."

        # Format revenue in billions
        revenue_b = carrier_financials.get('operating_revenue', 0) / 1_000_000_000
        expenses_b = carrier_financials.get('operating_expenses', 0) / 1_000_000_000
        op_income_m = carrier_financials.get('operating_income', 0) / 1_000_000
        net_income_m = carrier_financials.get('net_income', 0) / 1_000_000
        fuel_m = carrier_financials.get('fuel_expense', 0) / 1_000_000
        labor_m = carrier_financials.get('labor_expense', 0) / 1_000_000
        asm_b = carrier_financials.get('asm', 0) / 1_000_000_000
        rpm_b = carrier_financials.get('rpm', 0) / 1_000_000_000

        formatted = f"""**Carrier Financial Data** (BTS Form 41 - {carrier_financials.get('period', 'Unknown')}):
Carrier: {carrier_financials.get('carrier_name', 'Unknown')} ({carrier_financials.get('carrier_code', '??')}) | Ticker: {carrier_financials.get('ticker', '??')}
Period Ending: {carrier_financials.get('period_end_date', 'Unknown')}

**Income Statement:**
- Operating Revenue: ${revenue_b:.2f}B
- Operating Expenses: ${expenses_b:.2f}B
- Operating Income: ${op_income_m:.0f}M
- Net Income: ${net_income_m:.0f}M
- Operating Margin: {carrier_financials.get('operating_margin_pct', 0):.1f}%

**Expense Breakdown:**
- Fuel Expense: ${fuel_m:.0f}M ({fuel_m/(expenses_b*1000)*100:.1f}% of OpEx)
- Labor Expense: ${labor_m:.0f}M ({labor_m/(expenses_b*1000)*100:.1f}% of OpEx)

**Traffic Metrics:**
- Available Seat Miles (ASM): {asm_b:.1f}B
- Revenue Passenger Miles (RPM): {rpm_b:.1f}B
- Load Factor: {carrier_financials.get('load_factor_pct', 0):.1f}%
- RASM (Revenue/ASM): {carrier_financials.get('rasm_cents', 0):.2f}¢
- CASM (Cost/ASM): {carrier_financials.get('casm_cents', 0):.2f}¢
- RASM-CASM Spread: {(carrier_financials.get('rasm_cents', 0) - carrier_financials.get('casm_cents', 0)):.2f}¢

Source: DOT Bureau of Transportation Statistics Form 41
"""
        return formatted

    def _format_balance_sheet_data(self, balance_sheet_data: Optional[Dict]) -> str:
        """Format Yahoo Finance balance sheet data for prompt inclusion"""
        if not balance_sheet_data:
            return "**Balance Sheet & Credit Metrics**: Not available."

        # Format values
        total_debt_b = balance_sheet_data.get('total_debt', 0) / 1e9
        net_debt_b = balance_sheet_data.get('net_debt', 0) / 1e9
        cash_b = balance_sheet_data.get('cash_and_equivalents', 0) / 1e9
        equity_b = balance_sheet_data.get('stockholders_equity', 0) / 1e9
        ebitda_b = balance_sheet_data.get('ebitda', 0) / 1e9
        ebit_b = balance_sheet_data.get('ebit', 0) / 1e9
        fcf_b = balance_sheet_data.get('free_cash_flow', 0) / 1e9
        ocf_b = balance_sheet_data.get('operating_cash_flow', 0) / 1e9
        int_exp_m = balance_sheet_data.get('interest_expense', 0) / 1e6
        net_income_b = balance_sheet_data.get('net_income', 0) / 1e9
        working_cap_b = balance_sheet_data.get('working_capital', 0) / 1e9

        formatted = f"""**Balance Sheet & Credit Metrics** ({balance_sheet_data.get('ticker', 'N/A')} - {balance_sheet_data.get('period', 'Annual')}):

**Debt & Capital Structure:**
- Total Debt: ${total_debt_b:.2f}B
- Net Debt: ${net_debt_b:.2f}B
- Stockholders' Equity: ${equity_b:.2f}B
- Working Capital: ${working_cap_b:.2f}B

**Liquidity:**
- Cash & Equivalents: ${cash_b:.2f}B

**Profitability & Cash Flow:**
- EBITDA: ${ebitda_b:.2f}B
- EBIT: ${ebit_b:.2f}B
- Net Income: ${net_income_b:.2f}B
- Free Cash Flow: ${fcf_b:.2f}B
- Operating Cash Flow: ${ocf_b:.2f}B

**Key Credit Ratios:**
- Debt-to-EBITDA: {balance_sheet_data.get('debt_to_ebitda', 'N/A')}x
- Interest Coverage (EBIT/Interest): {balance_sheet_data.get('interest_coverage', 'N/A')}x
- Debt-to-Equity: {balance_sheet_data.get('debt_to_equity', 'N/A')}x
- Annual Interest Expense: ${int_exp_m:.0f}M

Source: Yahoo Finance (Latest Annual/Quarterly Filing)
"""
        return formatted

    def _format_credit_analysis(
        self,
        balance_sheet_data: Optional[Dict],
        credit_benchmarks: Optional[Dict]
    ) -> str:
        """
        Format comprehensive credit analysis data including:
        1. Synthetic credit rating estimation from financial metrics
        2. Multi-tier credit spread benchmarks
        3. Market stress assessment
        """
        sections = []

        # 1. Synthetic Rating Estimation
        if balance_sheet_data and self.financial_service:
            debt_to_ebitda = balance_sheet_data.get('debt_to_ebitda')
            interest_coverage = balance_sheet_data.get('interest_coverage')

            if debt_to_ebitda is not None and interest_coverage is not None:
                rating_estimate = self.financial_service.estimate_credit_rating(
                    debt_to_ebitda=debt_to_ebitda,
                    interest_coverage=interest_coverage
                )

                sections.append(f"""**ESTIMATED CREDIT RATING**:
- **Rating: {rating_estimate.get('estimated_rating', 'N/A')}**
- Outlook: {rating_estimate.get('rating_outlook', 'N/A')}
- Confidence: {rating_estimate.get('confidence', 'N/A')}
- Key Metrics Used:
  - Debt-to-EBITDA: {rating_estimate.get('debt_to_ebitda', 'N/A')}x
  - Interest Coverage: {rating_estimate.get('interest_coverage', 'N/A')}x
- Methodology: {rating_estimate.get('methodology', 'N/A')}
- Note: {rating_estimate.get('note', '')}
""")
            else:
                sections.append("**ESTIMATED CREDIT RATING**: Unable to calculate - missing Debt/EBITDA or Interest Coverage data.")
        else:
            sections.append("**ESTIMATED CREDIT RATING**: Not available - balance sheet data required.")

        # 2. Credit Spread Benchmarks
        if credit_benchmarks and credit_benchmarks.get('success'):
            spreads = credit_benchmarks.get('spreads', {})
            data_date = credit_benchmarks.get('data_date', 'Unknown')
            market_stress = credit_benchmarks.get('market_stress', 'unknown')
            stress_desc = credit_benchmarks.get('stress_description', '')

            sections.append(f"""**CREDIT SPREAD BENCHMARKS** (as of {data_date}):
Current option-adjusted spreads by rating tier:
- AA Corporate Spreads: {spreads.get('aa_spread_bps', 'N/A')} bps (highest investment grade)
- A Corporate Spreads: {spreads.get('a_spread_bps', 'N/A')} bps
- BBB Corporate Spreads: {spreads.get('bbb_spread_bps', 'N/A')} bps (typical airline rating)
- BB High Yield Spreads: {spreads.get('bb_spread_bps', 'N/A')} bps (speculative grade)
- Overall Market Spreads: {spreads.get('market_spread_bps', 'N/A')} bps

**Market Stress Level**: {market_stress.upper()}
{stress_desc}

Source: Federal Reserve Economic Data (FRED) - ICE BofA Indices
""")
        elif credit_benchmarks and not credit_benchmarks.get('success'):
            # Fallback data
            spreads = credit_benchmarks.get('spreads', {})
            sections.append(f"""**CREDIT SPREAD BENCHMARKS** (fallback estimates):
- AA Corporate Spreads: ~{spreads.get('aa_spread_bps', 85)} bps
- A Corporate Spreads: ~{spreads.get('a_spread_bps', 120)} bps
- BBB Corporate Spreads: ~{spreads.get('bbb_spread_bps', 165)} bps
- BB High Yield Spreads: ~{spreads.get('bb_spread_bps', 350)} bps

Note: Using estimated spreads (FRED API temporarily unavailable)
""")
        else:
            sections.append("**CREDIT SPREAD BENCHMARKS**: Not available.")

        # 3. Rating-Spread Comparison Context
        if balance_sheet_data and credit_benchmarks:
            sections.append("""**RATING-SPREAD INTERPRETATION GUIDE**:
- If estimated rating is BBB: Compare company to BBB benchmark spreads
- If estimated rating is BB: Company has higher credit risk, monitor BB spread levels
- Widening spreads vs benchmark = deteriorating credit perception
- Tightening spreads vs benchmark = improving credit perception
""")

        return "\n".join(sections) if sections else "**Credit Analysis Data**: Not available."

    def _parse_sections(self, markdown_content: str) -> Dict[str, str]:
        """
        Parse markdown content into sections based on headers

        Returns a dictionary mapping section names to content
        """
        sections = {}
        current_section = None
        current_content = []

        for line in markdown_content.split('\n'):
            # Check for H2 headers (##)
            if line.startswith('## '):
                # Save previous section
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()

                # Start new section
                current_section = line[3:].strip().lower().replace(' ', '_')
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()

        return sections

    # =================================================================
    # WEEKLY OUTLOOK INSIGHTS (Investment Themes, Recommendations, Executive Summary)
    # =================================================================

    def generate_investment_themes(self, use_cache: bool = True) -> Optional[List[str]]:
        """
        Generate 3-5 investment themes using Gemini AI

        Args:
            use_cache: Whether to use cached themes (24-hour cache)

        Returns:
            List of investment theme strings (one sentence each)
        """
        try:
            logger.info("📊 Generating investment themes...")

            # Check cache if enabled
            if use_cache:
                cached = self._get_cached_weekly_insight('investment_themes')
                if cached:
                    logger.info("✅ Using cached investment themes")
                    return cached.get('themes', [])

            # Get market context
            context = self._get_weekly_market_context()

            # Build Gemini prompt
            prompt = f"""Based on current aviation industry data, identify 3-5 key investment themes.

CURRENT MARKET CONTEXT (Last 7 Days):

MAJOR HEADLINES:
{chr(10).join(context['headlines']) if context['headlines'] else '• No major headlines this week'}

OPERATIONAL RISKS:
{chr(10).join(f"• {r}" for r in context['operational_risks']) if context['operational_risks'] else '• No significant operational risks'}

FINANCIAL RISKS:
{chr(10).join(f"• {r}" for r in context['financial_risks']) if context['financial_risks'] else '• No significant financial risks'}

Generate 3-5 investment themes (one sentence each) that:
1. Reflect current market dynamics and trends
2. Highlight opportunities or positioning strategies
3. Use professional, analytical language suitable for institutional investors
4. Focus on actionable insights

Format your response as a simple list without numbers:
- [Theme 1]
- [Theme 2]
- [Theme 3]

Investment Themes:"""

            # Generate with Gemini
            response = self.gemini.generate_content(prompt, temperature=0.7)

            if not response:
                logger.warning("⚠️ Gemini returned empty response for investment themes")
                return None

            # Parse response into list
            themes = self._parse_bullet_list(response)

            if themes:
                # Cache the result
                self._cache_weekly_insight('investment_themes', {'themes': themes})
                logger.info(f"✅ Generated {len(themes)} investment themes")
                return themes
            else:
                logger.warning("⚠️ Failed to parse investment themes from Gemini response")
                return None

        except Exception as e:
            logger.error(f"❌ Error generating investment themes: {e}")
            return None

    def generate_strategic_recommendations(self, use_cache: bool = True) -> Optional[str]:
        """
        Generate strategic recommendations using Gemini AI

        Args:
            use_cache: Whether to use cached recommendations (24-hour cache)

        Returns:
            Strategic recommendation paragraph (2-3 sentences)
        """
        try:
            logger.info("💡 Generating strategic recommendations...")

            # Check cache if enabled
            if use_cache:
                cached = self._get_cached_weekly_insight('strategic_recommendations')
                if cached:
                    logger.info("✅ Using cached strategic recommendations")
                    return cached.get('recommendation', '')

            # Get market context
            context = self._get_weekly_market_context()

            # Get investment themes (will use cache if available)
            themes = self.generate_investment_themes(use_cache=True)
            themes_text = '\n'.join(f"• {t}" for t in themes) if themes else "• No specific themes identified"

            # Build Gemini prompt
            prompt = f"""Generate strategic investment recommendation for the aviation sector.

CONTEXT:

INVESTMENT THEMES:
{themes_text}

KEY RISKS:
Operational: {', '.join(context['operational_risks'][:2]) if context['operational_risks'] else 'None identified'}
Financial: {', '.join(context['financial_risks'][:2]) if context['financial_risks'] else 'None identified'}

RECENT DEVELOPMENTS:
{chr(10).join(context['headlines'][:3]) if context['headlines'] else '• Market conditions stable'}

Provide a 2-3 sentence strategic recommendation addressing:
1. Overall sector positioning (overweight/neutral/underweight or maintain/increase/reduce exposure)
2. Specific focus areas or segments (e.g., premium carriers, international routes, etc.)
3. Key variables or metrics to monitor going forward

Use professional language suitable for institutional investors. Be specific and actionable.

Strategic Recommendation:"""

            # Generate with Gemini
            response = self.gemini.generate_content(prompt, temperature=0.7)

            if not response:
                logger.warning("⚠️ Gemini returned empty response for strategic recommendations")
                return None

            # Clean up response
            recommendation = response.strip()

            # Cache the result
            self._cache_weekly_insight('strategic_recommendations', {'recommendation': recommendation})
            logger.info("✅ Generated strategic recommendations")
            return recommendation

        except Exception as e:
            logger.error(f"❌ Error generating strategic recommendations: {e}")
            return None

    def generate_executive_summary(self, use_cache: bool = True) -> Optional[str]:
        """
        Generate executive summary using Gemini AI

        Args:
            use_cache: Whether to use cached summary (24-hour cache)

        Returns:
            Executive summary paragraph (2-3 sentences)
        """
        try:
            logger.info("📋 Generating executive summary...")

            # Check cache if enabled
            if use_cache:
                cached = self._get_cached_weekly_insight('executive_summary')
                if cached:
                    logger.info("✅ Using cached executive summary")
                    return cached.get('summary', '')

            # Get market context
            context = self._get_weekly_market_context()

            # Build Gemini prompt
            prompt = f"""Generate a professional 2-3 sentence executive summary for aviation industry weekly outlook.

CURRENT CONTEXT (Last 7 Days):

MAJOR HEADLINES:
{chr(10).join(context['headlines'][:5]) if context['headlines'] else '• Market activity moderate this week'}

KEY RISKS:
Operational: {', '.join(context['operational_risks'][:2]) if context['operational_risks'] else 'Limited operational concerns'}
Financial: {', '.join(context['financial_risks'][:2]) if context['financial_risks'] else 'Stable financial environment'}

Create a concise, analytical summary (2-3 sentences) highlighting:
1. Overall sector health and momentum (resilient/strong/challenged/mixed)
2. Key trends or developments from the headlines
3. Notable risk factors or opportunities

Use professional language suitable for institutional investors. Focus on synthesis rather than listing.

Executive Summary:"""

            # Generate with Gemini
            response = self.gemini.generate_content(prompt, temperature=0.7)

            if not response:
                logger.warning("⚠️ Gemini returned empty response for executive summary")
                return None

            # Clean up response
            summary = response.strip()

            # Cache the result
            self._cache_weekly_insight('executive_summary', {'summary': summary})
            logger.info("✅ Generated executive summary")
            return summary

        except Exception as e:
            logger.error(f"❌ Error generating executive summary: {e}")
            return None

    def generate_catalysts(self, use_cache: bool = True) -> Optional[List[Dict[str, str]]]:
        """
        Generate upcoming catalysts/events using Gemini AI

        Args:
            use_cache: Whether to use cached catalysts (7-day cache)

        Returns:
            List of catalyst dictionaries with 'date' and 'description' keys
        """
        try:
            logger.info("📅 Generating upcoming catalysts...")

            # Check cache if enabled
            if use_cache:
                cached = self._get_cached_weekly_insight('catalysts')
                if cached:
                    logger.info("✅ Using cached catalysts")
                    return cached.get('catalysts', [])

            # Get current date for context
            from datetime import datetime
            current_date = datetime.now().strftime('%B %d, %Y')

            # Get market context for relevance
            context = self._get_weekly_market_context()

            # Build Gemini prompt
            prompt = f"""Generate 5-7 likely upcoming industry catalysts/events for the aviation sector over the next 4 weeks.

CURRENT DATE: {current_date}

RECENT CONTEXT:
{chr(10).join(context['headlines'][:3]) if context['headlines'] else '• Normal market conditions'}

Generate realistic, sector-relevant catalysts including:
1. Earnings reports (major carriers like Delta, United, American, Southwest typically report quarterly)
2. Economic data releases (DOT traffic data, BTS statistics - released monthly)
3. Regulatory events (FAA announcements, DOT rulemakings)
4. Industry conferences or events
5. Known recurring events (e.g., monthly data releases)

Format each catalyst as:
- [Date Range or Specific Date]: [Event Description]

Example format:
- Feb 5-9: Major carrier Q4 earnings week (DAL, UAL, AAL)
- Feb 12: DOT monthly traffic data release
- Feb 15: FAA operational update expected

Provide 5-7 catalysts, ordered chronologically. Use realistic dates relative to {current_date}.

Catalysts:"""

            # Generate with Gemini
            response = self.gemini.generate_content(prompt, temperature=0.7)

            if not response:
                logger.warning("⚠️ Gemini returned empty response for catalysts")
                return None

            # Parse response into list of dicts
            catalysts = []
            lines = response.strip().split('\n')

            for line in lines:
                line = line.strip()
                # Match patterns like "- Date: Description" or "• Date: Description"
                if line and (':' in line):
                    # Remove bullet if present
                    if line.startswith('-') or line.startswith('•'):
                        line = line[1:].strip()

                    # Split on first colon
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        date_range = parts[0].strip()
                        description = parts[1].strip()

                        # Remove markdown formatting (**, *, etc.)
                        import re
                        date_range = re.sub(r'\*\*', '', date_range).strip()
                        description = re.sub(r'\*\*', '', description).strip()

                        if date_range and description:
                            catalysts.append({
                                'date': date_range,
                                'description': description
                            })

            if catalysts:
                # Cache the result (7-day cache for catalysts)
                self._cache_weekly_insight('catalysts', {'catalysts': catalysts}, cache_days=7)
                logger.info(f"✅ Generated {len(catalysts)} catalysts")
                return catalysts
            else:
                logger.warning("⚠️ Failed to parse catalysts from Gemini response")
                return None

        except Exception as e:
            logger.error(f"❌ Error generating catalysts: {e}")
            return None

    def _get_weekly_market_context(self) -> Dict[str, Any]:
        """
        Aggregate current market metrics and news for weekly outlook AI context

        Returns:
            Dictionary with market metrics, news headlines, and risk factors
        """
        try:
            # Get recent news articles (last 7 days) using Eastern Time
            start_date = datetime.now(EASTERN_TZ).replace(tzinfo=None) - timedelta(days=7)
            recent_news = self.db.get_articles(
                start_date=start_date,
                limit=10
            )

            # Extract headlines and AI summaries
            headlines = []
            for article in recent_news[:5]:
                title = article.get('title', '')
                impact = article.get('impact_statement', '')
                if title:
                    headlines.append(f"• {title}" + (f" - {impact}" if impact else ""))

            # Get risk factors
            operational_risks = self.db.get_articles(
                tags=['operational_risk'],
                start_date=start_date,
                limit=3
            )

            financial_risks = self.db.get_articles(
                tags=['financial_risk'],
                start_date=start_date,
                limit=3
            )

            # Extract risk summaries
            op_risks = [r.get('impact_statement', r.get('title', '')) for r in operational_risks]
            fin_risks = [r.get('impact_statement', r.get('title', '')) for r in financial_risks]

            return {
                'headlines': headlines,
                'operational_risks': op_risks,
                'financial_risks': fin_risks,
                'article_count': len(recent_news)
            }

        except Exception as e:
            logger.error(f"❌ Error getting market context: {e}")
            return {
                'headlines': [],
                'operational_risks': [],
                'financial_risks': [],
                'article_count': 0
            }

    def _parse_bullet_list(self, text: str) -> List[str]:
        """
        Parse bullet list from Gemini response

        Args:
            text: Response text with bullet items

        Returns:
            List of items (without bullets)
        """
        items = []
        lines = text.strip().split('\n')

        for line in lines:
            line = line.strip()
            # Match patterns like "- ", "• ", or numbers like "1. "
            if line and (line.startswith('-') or line.startswith('•') or (line[0].isdigit() and '. ' in line)):
                # Remove bullets/numbering
                cleaned = line
                if cleaned.startswith('-'):
                    cleaned = cleaned[1:].strip()
                elif cleaned.startswith('•'):
                    cleaned = cleaned[1:].strip()
                elif cleaned[0].isdigit():
                    # Remove number and period
                    parts = cleaned.split('. ', 1)
                    if len(parts) > 1:
                        cleaned = parts[1].strip()

                if cleaned:
                    items.append(cleaned)

        return items

    def _get_cached_weekly_insight(self, insight_type: str) -> Optional[Dict[str, Any]]:
        """
        Get cached weekly outlook insights from Firestore

        Args:
            insight_type: Type of insight (investment_themes, strategic_recommendations, executive_summary, catalysts)

        Returns:
            Cached data if available and not expired
        """
        try:
            # Get latest insight of this type
            latest = self.db.get_latest_insight(timeframe=insight_type)

            if not latest:
                return None

            # Check if cache is still valid using valid_until timestamp
            valid_until = latest.get('valid_until')
            if valid_until:
                if datetime.now() < valid_until:
                    return latest.get('data', {})

            return None

        except Exception as e:
            logger.error(f"❌ Error getting cached insights: {e}")
            return None

    def _cache_weekly_insight(self, insight_type: str, data: Dict[str, Any], cache_days: int = 1) -> None:
        """
        Cache weekly outlook insights to Firestore

        Args:
            insight_type: Type of insight
            data: Insight data to cache
            cache_days: Number of days to cache (default 1 day)
        """
        try:
            insight_data = {
                'timeframe': insight_type,
                'data': data,
                'generated_at': datetime.now(),
                'valid_until': datetime.now() + timedelta(days=cache_days)
            }

            self.db.save_insight(insight_data)
            logger.info(f"✅ Cached {insight_type} insights (valid for {cache_days} days)")

        except Exception as e:
            logger.error(f"❌ Error caching insights: {e}")

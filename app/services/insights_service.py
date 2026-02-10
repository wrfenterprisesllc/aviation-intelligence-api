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

    # =================================================================
    # CACHED DATA RETRIEVAL (Pre-loaded data from daily ingestion)
    # =================================================================

    def _get_fred_data_cached(self) -> Optional[Dict]:
        """
        Get FRED credit spread data - prefer cached from daily ingestion, fallback to live API

        Returns:
            FRED credit spread benchmark data or None
        """
        from datetime import timezone

        # Try Firestore cache first (from daily financial ingestion)
        try:
            cached = self.db.get_latest_financial_snapshot('fred_spreads')
            if cached:
                stored_at = cached.get('stored_at')
                if stored_at:
                    # Check if less than 24 hours old
                    if hasattr(stored_at, 'replace'):
                        stored_at = stored_at.replace(tzinfo=timezone.utc)
                    age_seconds = (datetime.now(timezone.utc) - stored_at).total_seconds()
                    if age_seconds < 86400:  # 24 hours
                        logger.info("📊 Using cached FRED data from daily ingestion")
                        return cached
        except Exception as e:
            logger.warning(f"⚠️ Error checking cached FRED data: {e}")

        # Fallback to live API
        if self.fred_service:
            logger.info("📊 Fetching live FRED data (cache miss or stale)")
            return self.fred_service.get_credit_spread_benchmarks()

        return None

    def _get_carrier_financials_cached(self, airline: str) -> Optional[Dict]:
        """
        Get carrier financial data - prefer cached from daily ingestion, fallback to live API

        Args:
            airline: Airline name (e.g., 'United Airlines')

        Returns:
            Balance sheet and financial data or None
        """
        from datetime import timezone

        # Try Firestore cache first (from daily financial ingestion)
        try:
            cached = self.db.get_latest_carrier_financial_snapshot(airline)
            if cached:
                stored_at = cached.get('stored_at')
                if stored_at:
                    if hasattr(stored_at, 'replace'):
                        stored_at = stored_at.replace(tzinfo=timezone.utc)
                    age_seconds = (datetime.now(timezone.utc) - stored_at).total_seconds()
                    if age_seconds < 86400:  # 24 hours
                        logger.info(f"💰 Using cached financials for {airline} from daily ingestion")
                        return cached
        except Exception as e:
            logger.warning(f"⚠️ Error checking cached financials for {airline}: {e}")

        # Fallback to live API
        if self.financial_service:
            logger.info(f"💰 Fetching live financials for {airline} (cache miss or stale)")
            return self.financial_service.get_balance_sheet_data(airline)

        return None

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

            # Get balance sheet data - prefer cached from daily ingestion
            balance_sheet_data = None
            if report_type in ['airline', 'credit_analysis', 'comprehensive']:
                # Try cached data first (from daily financial ingestion)
                balance_sheet_data = self._get_carrier_financials_cached(subject)
                if balance_sheet_data:
                    logger.info(f"✅ Retrieved balance sheet data for {subject}")
                else:
                    logger.warning(f"⚠️ Could not fetch balance sheet data for '{subject}'")

            # Get credit spread benchmarks - prefer cached from daily ingestion
            credit_benchmarks = None
            if report_type in ['airline', 'credit_analysis', 'comprehensive']:
                # Try cached data first (from daily financial ingestion)
                credit_benchmarks = self._get_fred_data_cached()
                if credit_benchmarks and credit_benchmarks.get('success'):
                    logger.info(f"✅ Retrieved credit spread benchmarks")
                else:
                    logger.warning(f"⚠️ Could not fetch credit spread benchmarks")

            # Get defense contracts for this subject
            defense_contracts = None
            if report_type in ['airline', 'credit_analysis', 'comprehensive', 'leasing_recommendation']:
                try:
                    defense_contracts = self.db.get_defense_contracts(
                        start_date=start_date,
                        end_date=end_date,
                        contractor=subject,  # Match by company name
                        limit=15
                    )
                    if defense_contracts:
                        logger.info(f"✅ Retrieved {len(defense_contracts)} defense contracts for {subject}")
                    else:
                        logger.debug(f"No defense contracts found for {subject}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not fetch defense contracts: {e}")

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
                       f"CreditBenchmarks: {'Yes' if credit_benchmarks else 'No'}, "
                       f"DefenseContracts: {len(defense_contracts) if defense_contracts else 0}")

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
                    defense_contracts=defense_contracts,
                    period_start=start_date,
                    period_end=end_date
                )
            elif report_type == 'leasing_recommendation':
                prompt = self._build_leasing_recommendation_prompt(
                    subject=subject,
                    news_articles=news_articles,
                    tsa_data=tsa_data,
                    fred_data=fred_data,
                    stock_data=stock_data,
                    sec_filings=sec_filings,
                    carrier_financials=carrier_financials,
                    balance_sheet_data=balance_sheet_data,
                    defense_contracts=defense_contracts,
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
                    carrier_financials=carrier_financials,
                    balance_sheet_data=balance_sheet_data,
                    credit_benchmarks=credit_benchmarks,
                    defense_contracts=defense_contracts,
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
                    carrier_financials=carrier_financials,
                    balance_sheet_data=balance_sheet_data,
                    defense_contracts=defense_contracts,
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
            # week_offset=0 means current week, week_offset=1 means last week, etc.
            today = datetime.now(EASTERN_TZ)
            days_since_monday = today.weekday()
            # Get Monday of current week, then adjust by week_offset
            this_monday = today - timedelta(days=days_since_monday)
            target_monday = this_monday - timedelta(weeks=week_offset)
            target_sunday = target_monday + timedelta(days=6)

            week_start = target_monday.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
            week_end = target_sunday.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=None)

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

            # Get stock data for major carriers
            stock_data = None
            if self.stock_service:
                try:
                    major_carriers = ['United Airlines', 'Delta Air Lines', 'American Airlines', 'Southwest Airlines']
                    stock_data = {}
                    for carrier in major_carriers:
                        carrier_stock = self.stock_service.get_stock_data(carrier, period='1wk')
                        if carrier_stock:
                            stock_data[carrier] = carrier_stock
                    logger.info(f"✅ Retrieved stock data for {len(stock_data)} carriers")
                except Exception as e:
                    logger.warning(f"⚠️ Could not fetch stock data: {e}")

            # Get notable SEC filings from the week
            sec_filings = []
            if self.sec_service:
                try:
                    for carrier in ['United Airlines', 'Delta Air Lines', 'American Airlines']:
                        filings = self.sec_service.get_recent_filings(
                            airline_name=carrier,
                            filing_types=['8-K', '10-Q', '10-K'],
                            max_results=3
                        )
                        if filings and filings.get('filings'):
                            for filing in filings['filings']:
                                # Check if filed this week
                                filing_date = filing.get('filing_date', '')
                                if filing_date >= week_start.strftime('%Y-%m-%d'):
                                    sec_filings.append({
                                        **filing,
                                        'company_name': carrier
                                    })
                    logger.info(f"✅ Retrieved {len(sec_filings)} SEC filings for the week")
                except Exception as e:
                    logger.warning(f"⚠️ Could not fetch SEC filings: {e}")

            # Get defense contracts for the week (industry-wide aviation contracts)
            defense_contracts = []
            try:
                defense_contracts = self.db.get_defense_contracts(
                    start_date=week_start,
                    end_date=week_end,
                    aviation_only=True,  # Only aviation-related contracts
                    limit=20
                )
                if defense_contracts:
                    logger.info(f"✅ Retrieved {len(defense_contracts)} defense contracts for newsletter")
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch defense contracts: {e}")

            # Log data availability
            if not news_articles:
                logger.warning(f"⚠️ No news articles found for week {week_start.date()} to {week_end.date()}")
            if not tsa_data:
                logger.warning(f"⚠️ No TSA data found for week {week_start.date()} to {week_end.date()}")
            if not fred_data:
                logger.warning(f"⚠️ No FRED data available")

            logger.info(f"📊 Data collected: {len(news_articles) if news_articles else 0} articles, "
                       f"{len(tsa_data) if tsa_data else 0} TSA records, "
                       f"FRED: {'Yes' if fred_data else 'No'}, "
                       f"Stocks: {len(stock_data) if stock_data else 0} carriers, "
                       f"SEC: {len(sec_filings) if sec_filings else 0} filings, "
                       f"Defense: {len(defense_contracts) if defense_contracts else 0} contracts")

            # Build comprehensive newsletter prompt
            prompt = self._build_newsletter_prompt(
                week_start=week_start,
                week_end=week_end,
                news_articles=news_articles,
                tsa_data=tsa_data,
                fred_data=fred_data,
                stock_data=stock_data,
                sec_filings=sec_filings,
                defense_contracts=defense_contracts,
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
                    'stock_carriers': len(stock_data) if stock_data else 0,
                    'sec_filings': len(sec_filings) if sec_filings else 0,
                    'defense_contracts': len(defense_contracts) if defense_contracts else 0,
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
        carrier_financials: Optional[Dict] = None,
        balance_sheet_data: Optional[Dict] = None,
        defense_contracts: Optional[List[Dict]] = None,
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

        # Format BTS carrier financials
        carrier_summary = self._format_carrier_financials(carrier_financials)

        # Format balance sheet data
        balance_sheet_summary = self._format_balance_sheet_data(balance_sheet_data)

        # Format defense contracts
        defense_contracts_summary = self._format_defense_contracts(defense_contracts)

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

{carrier_summary}

{balance_sheet_summary}

{defense_contracts_summary}

**Instructions**:
Generate a professional, data-driven report in Markdown format with the following sections:

## Executive Summary
- 2-3 paragraph overview of key findings
- Highlight most significant developments
- Include stock performance and key financial metrics if available

## News Analysis
- Analyze major news stories and their implications
- Identify trends and patterns
- Quote specific articles when relevant

## Financial Performance
- Analyze stock price performance and volatility (if available)
- Review recent SEC filings and their implications (if available)
- Include key balance sheet metrics (debt, cash, EBITDA) if available
- Compare performance to sector benchmarks

## Operational Metrics
- Analyze BTS Form 41 carrier financials if available (revenue, margins, load factor)
- Evaluate RASM/CASM spread and operational efficiency
- Compare operational performance to peers

## Market Data Insights
- Analyze TSA passenger data trends
- Interpret credit spread data and financial conditions
- Connect market data to news developments and stock performance

## Key Developments
- List and analyze the most important events
- Include recent SEC filings (10-K, 10-Q, 8-K)
- Include significant defense contract awards or losses if available
- Note government program participation and revenue implications
- Provide context and industry implications

## Risk Assessment
- Identify potential risks and challenges
- Consider financial metrics, leverage ratios, and stock volatility
- Rate overall risk level (Low/Moderate/High)

## Outlook & Recommendations
- Forward-looking analysis
- Consider defense segment outlook and government spending trends if applicable
- Evaluate revenue diversification between commercial and government
- Strategic recommendations based on all available data
- Investment positioning considerations

**Style Guidelines**:
- Professional, analytical tone
- Use data to support all claims
- Include specific numbers and percentages from carrier financials and balance sheet
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
        defense_contracts: Optional[List[Dict]] = None,
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
        defense_contracts_summary = self._format_defense_contracts(defense_contracts)

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

{defense_contracts_summary}

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

## Defense Segment Credit Impact (if applicable)
- Evaluate contribution of defense contracts to revenue stability
- Assess multi-year government contract visibility
- Consider how government revenue reduces overall default risk
- Compare commercial vs. defense segment volatility

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
        tsa_data: List[Dict],
        fred_data: Optional[Dict],
        stock_data: Optional[Dict],
        sec_filings: Optional[Dict],
        carrier_financials: Optional[Dict],
        balance_sheet_data: Optional[Dict],
        defense_contracts: Optional[List[Dict]] = None,
        period_start: datetime = None,
        period_end: datetime = None
    ) -> str:
        """Build specialized leasing recommendation prompt from aircraft lessor perspective"""

        # Format data sources
        news_summary = self._format_news_articles(news_articles)
        tsa_summary = self._format_tsa_data(tsa_data)
        fred_summary = self._format_fred_data(fred_data)
        stock_summary = self._format_stock_data(stock_data)
        sec_summary = self._format_sec_filings(sec_filings)
        carrier_summary = self._format_carrier_financials(carrier_financials)
        defense_contracts_summary = self._format_defense_contracts(defense_contracts)
        balance_sheet_summary = self._format_balance_sheet_data(balance_sheet_data)

        prompt = f"""You are a senior aircraft leasing analyst. Generate a comprehensive leasing recommendation report for {subject} covering {period_start.strftime('%B %d, %Y')} to {period_end.strftime('%B %d, %Y')}.

**Perspective**: Analyze from an aircraft lessor perspective, focusing on lease rates, fleet strategy, lessee creditworthiness, and market conditions.

**Available Data**:

{news_summary}

{stock_summary}

{tsa_summary}

{fred_summary}

{sec_summary}

{carrier_summary}

{balance_sheet_summary}

{defense_contracts_summary}

**Required Report Sections** (use these exact H2 headers):

## Executive Summary
Provide a 3-4 paragraph overview of the airline's attractiveness as a lessee, key opportunities, and risks. Reference specific financial metrics.

## Fleet Composition & Strategy
- Current fleet breakdown (aircraft types, ages) based on news and public data
- Recent aircraft orders and deliveries
- Fleet modernization initiatives
- Narrowbody vs. widebody mix

## Market Conditions & Lease Rate Trends
- Current lease rate environment for key aircraft types
- Supply/demand dynamics in aircraft leasing market
- Industry-wide trends affecting lease rates
- Credit spread environment and financing cost implications (use FRED data)
- Airline's historical lease vs. own strategy

## Lessee Credit Profile
- Financial stability as a lessee (use balance sheet metrics)
- Debt-to-EBITDA ratio and interest coverage
- Liquidity position (cash, available credit)
- On-time lease payment history (based on news/reports)
- Stock performance trends
- **Credit Assessment**: Investment Grade / Crossover / Speculative (based on financial ratios)

## Operational Performance
- Operating revenue and margin trends (from BTS data if available)
- Load factor and RASM/CASM spread
- Fuel and labor cost efficiency
- Passenger demand trends (from TSA data)

## Route Network & Capacity Trends
- Network expansion or contraction
- Utilization rates and productivity
- International vs. domestic exposure
- Competitive position in key markets

## Government Aircraft Programs (if applicable)
- Defense contract awards for military aircraft variants
- Implications for commercial aircraft production timelines
- Shared supply chain benefits between defense and commercial
- Government fleet orders affecting lessor inventory

## Leasing Recommendation
- **Recommendation**: Favorable / Neutral / Cautious (use this exact format)
- Preferred aircraft types to lease to this airline
- Recommended lease structure (operating vs. finance)
- Suggested lease terms and conditions
- Key risk mitigations
- Security deposits or maintenance reserve requirements
- **Risk Level: High/Medium/Low** (use this exact format)

**Formatting Requirements**:
- Use markdown formatting
- Include specific fleet data and financial metrics where available
- Reference balance sheet ratios (Debt/EBITDA, interest coverage) in credit assessment
- Use bullet points for clarity
- Highlight risk levels using: **Risk Level: High/Medium/Low**
- Provide actionable recommendations with specific terms
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
        carrier_financials: Optional[Dict],
        balance_sheet_data: Optional[Dict],
        credit_benchmarks: Optional[Dict],
        defense_contracts: Optional[List[Dict]] = None,
        period_start: datetime = None,
        period_end: datetime = None
    ) -> str:
        """Build comprehensive report combining credit, leasing, and market analysis"""

        # Format data sources
        news_summary = self._format_news_articles(news_articles)
        tsa_summary = self._format_tsa_data(tsa_data)
        fred_summary = self._format_fred_data(fred_data)
        stock_summary = self._format_stock_data(stock_data)
        sec_summary = self._format_sec_filings(sec_filings)
        carrier_summary = self._format_carrier_financials(carrier_financials)
        balance_sheet_summary = self._format_balance_sheet_data(balance_sheet_data)
        credit_analysis_summary = self._format_credit_analysis(balance_sheet_data, credit_benchmarks)
        defense_contracts_summary = self._format_defense_contracts(defense_contracts)

        prompt = f"""You are a senior aviation intelligence analyst. Generate a comprehensive multi-perspective report for {subject} covering {period_start.strftime('%B %d, %Y')} to {period_end.strftime('%B %d, %Y')}.

**Perspective**: Provide integrated analysis from three perspectives: credit/bondholder, aircraft lessor, and market analyst.

**Available Data**:

{news_summary}

{tsa_summary}

{fred_summary}

{stock_summary}

{sec_summary}

{carrier_summary}

{balance_sheet_summary}

{credit_analysis_summary}

{defense_contracts_summary}

**Required Report Sections** (use these exact H2 headers):

## Executive Summary
Provide a 4-5 paragraph overview integrating credit, leasing, and market perspectives. Include the estimated credit rating, key financial metrics, and defense segment highlights if applicable.

## Credit Analysis
### Credit Rating & Financial Health
- Present the estimated credit rating from financial metrics
- Compare to benchmark spreads (AA, A, BBB, BB tiers)
- Key financial metrics (Debt/EBITDA, interest coverage, liquidity)
- Debt structure and covenant compliance

### Credit Risk Assessment
- Operational and market risks
- 12-month credit outlook
- Defense segment revenue stability contribution (if applicable)
- **Credit Risk Level: High/Medium/Low** (use this exact format)

## Leasing Analysis
### Fleet Strategy & Composition
- Current fleet breakdown and modernization plans
- Recent orders and lease commitments
- Fleet age and efficiency

### Lessee Attractiveness
- Financial stability as a lessee (reference balance sheet metrics)
- Operating margins and cash flow (from BTS data)
- Lease vs. own strategy
- Government aircraft program impacts on commercial fleet (if applicable)
- Recommended aircraft types and lease structures
- **Leasing Risk Level: High/Medium/Low** (use this exact format)

## Market & Operational Analysis
### Revenue & Capacity Trends
- TSA passenger data trends and demand analysis
- Load factor, RASM, and yield performance (from BTS data)
- Route network developments

### Competitive Position
- Operating margin vs. peers
- CASM competitiveness
- Market share in key segments
- Industry positioning

## Integrated Risk Assessment
- Combined risk view across credit, leasing, and operational dimensions
- How credit spreads correlate with operational performance
- Interconnected risk factors
- Scenario analysis (best/base/worst case)
- **Overall Risk Level: High/Medium/Low** (use this exact format)

## Strategic Recommendations
- For bondholders/lenders (reference credit rating and spreads)
- For aircraft lessors (reference balance sheet strength)
- For equity investors
- Key metrics to monitor

**Formatting Requirements**:
- Use markdown formatting with clear section hierarchy
- Include specific data points and percentages from all data sources
- Reference the estimated credit rating and spread benchmarks
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
        stock_data: Optional[Dict],
        sec_filings: Optional[List[Dict]],
        defense_contracts: Optional[List[Dict]] = None,
        previous_newsletter: Optional[Dict] = None,
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

        # Format stock data for major carriers
        stock_summary = self._format_newsletter_stock_summary(stock_data)

        # Format SEC filings
        sec_summary = self._format_newsletter_sec_summary(sec_filings)

        # Format defense contracts
        defense_summary = self._format_newsletter_defense_summary(defense_contracts)

        # Format previous newsletter context
        previous_context = ""
        if previous_newsletter:
            prev_start = previous_newsletter.get('week_start', 'Unknown')
            prev_end = previous_newsletter.get('week_end', 'Unknown')
            prev_predictions = previous_newsletter.get('sections', {}).get('week_ahead', '')
            previous_context = f"""
**Previous Week's Newsletter** ({prev_start} to {prev_end}):
- Use this for historical context and ongoing story tracking
- Reference any predictions made last week and verify against this week's data
"""
            if prev_predictions:
                previous_context += f"\nLast week's predictions to verify:\n{prev_predictions[:500]}\n"

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

{stock_summary}

{sec_summary}

{defense_summary}

{previous_context}

**Instructions**:
Generate a professional newsletter in Markdown format with the following sections:

{sections_instructions}

**Style Guidelines**:
- Engaging, newsletter-style writing (not overly formal)
- Clear, scannable structure with headers
- Use specific data points and numbers (stock prices, TSA throughput, credit spreads)
- Include stock performance in "By The Numbers" section
- Mention notable SEC filings if material
- Highlight significant defense contract awards in "By The Numbers" or "Industry Spotlight"
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

    def _format_newsletter_stock_summary(self, stock_data: Optional[Dict]) -> str:
        """Format major carrier stock performance for newsletter"""
        if not stock_data:
            return "**Sector Stock Performance**: Not available this week."

        formatted = "**Sector Stock Performance** (Major Carriers):\n\n"

        # Handle both single stock dict and multi-carrier dict
        if 'ticker' in stock_data:
            # Single stock
            ticker = stock_data.get('ticker', 'N/A')
            price = stock_data.get('current_price', 0)
            change = stock_data.get('day_change_percent', 0)
            change_str = f"{change:+.1f}%" if change else "N/A"
            formatted += f"- {ticker}: ${price:.2f} ({change_str})\n"
        else:
            # Multi-carrier dict
            for carrier, data in stock_data.items():
                if data and isinstance(data, dict):
                    ticker = data.get('ticker', carrier[:3].upper())
                    price = data.get('current_price', 0)
                    change = data.get('day_change_percent', 0)
                    change_str = f"{change:+.1f}%" if change else "N/A"
                    formatted += f"- {ticker}: ${price:.2f} ({change_str})\n"

        return formatted

    def _format_newsletter_sec_summary(self, sec_filings: Optional[List[Dict]]) -> str:
        """Format notable SEC filings for newsletter"""
        if not sec_filings:
            return "**Notable SEC Filings**: None this week."

        formatted = "**Notable SEC Filings** (Past Week):\n\n"
        for filing in sec_filings[:5]:
            company = filing.get('company_name', 'Unknown')
            filing_type = filing.get('filing_type', 'N/A')
            filing_date = filing.get('filing_date', 'N/A')
            description = filing.get('description', '')

            formatted += f"- **{company}**: {filing_type} ({filing_date})"
            if description:
                formatted += f" - {description}"
            formatted += "\n"

        return formatted

    def _format_defense_contracts(self, contracts: Optional[List[Dict]]) -> str:
        """Format defense contracts for prompt inclusion"""
        if not contracts:
            return "**Defense Contracts**: No recent contracts available for this entity."

        total_value = sum(c.get('contract_value', 0) for c in contracts)

        # Group by branch
        by_branch = {}
        for c in contracts:
            branch = c.get('branch', 'Unknown')
            if branch not in by_branch:
                by_branch[branch] = {'count': 0, 'value': 0}
            by_branch[branch]['count'] += 1
            by_branch[branch]['value'] += c.get('contract_value', 0)

        # Format value
        if total_value >= 1_000_000_000:
            total_formatted = f"${total_value/1_000_000_000:.2f}B"
        else:
            total_formatted = f"${total_value/1_000_000:.1f}M"

        formatted = f"""**Defense Contracts** ({len(contracts)} contracts, {total_formatted} total):

By Military Branch:
"""
        for branch, data in by_branch.items():
            value_fmt = f"${data['value']/1_000_000:.1f}M" if data['value'] < 1_000_000_000 else f"${data['value']/1_000_000_000:.2f}B"
            formatted += f"- {branch}: {data['count']} contracts, {value_fmt}\n"

        formatted += "\nRecent Notable Contracts:\n"
        for c in contracts[:5]:
            formatted += f"- {c.get('contractor', 'Unknown')}: {c.get('contract_value_formatted', 'N/A')} ({c.get('branch', 'N/A')})\n"
            desc = c.get('description', '')
            if desc:
                formatted += f"  {desc[:150]}...\n"

        return formatted

    def _format_newsletter_defense_summary(self, contracts: Optional[List[Dict]]) -> str:
        """Condensed defense contracts summary for newsletter"""
        if not contracts:
            return "**Government Contracts**: No significant aviation-related awards this week."

        total_value = sum(c.get('contract_value', 0) for c in contracts)
        total_fmt = f"${total_value/1_000_000_000:.1f}B" if total_value >= 1_000_000_000 else f"${total_value/1_000_000:.0f}M"

        # Top contractor
        contractors = {}
        for c in contracts:
            name = c.get('contractor', 'Unknown')
            contractors[name] = contractors.get(name, 0) + c.get('contract_value', 0)
        top_contractor = max(contractors.items(), key=lambda x: x[1]) if contractors else ('N/A', 0)

        # Get unique branches
        branches = list(set(c.get('branch', 'Unknown') for c in contracts if c.get('branch')))[:3]

        formatted = f"""**Defense Contract Awards** (Aviation-Related):
- Total Value This Week: {total_fmt} ({len(contracts)} contracts)
- Top Contractor: {top_contractor[0]}
- Key Branches: {', '.join(branches) if branches else 'N/A'}
"""
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

            # Format quantitative sections
            tsa_text = ""
            if context.get('tsa_summary'):
                tsa = context['tsa_summary']
                tsa_text = f"""TSA PASSENGER DATA (Last 7 Days):
- 7-Day Total: {tsa['total_passengers_7d']:,} passengers
- vs 2019 Baseline: {tsa['avg_vs_2019']}%
- Trend: {tsa['trend']}"""

            fred_text = ""
            if context.get('fred_summary'):
                fred = context['fred_summary']
                fred_text = f"""CREDIT MARKET CONDITIONS:
- BBB Credit Spread: {fred['spread_bps']} bps
- Risk Level: {fred['risk_level']}
- Condition: {fred['condition']}"""

            stock_text = ""
            if context.get('stock_summary'):
                stock = context['stock_summary']
                stock_text = f"""SECTOR STOCK PERFORMANCE (5 Days):
- Average Return: {stock['avg_sector_return']:+.1f}%
- Positive Movers: {stock['positive_count']}/{stock['total_carriers']} carriers"""

            defense_text = ""
            if context.get('defense_summary'):
                defense = context['defense_summary']
                total_fmt = f"${defense['total_value']/1_000_000_000:.1f}B" if defense['total_value'] >= 1_000_000_000 else f"${defense['total_value']/1_000_000:.0f}M"
                top_names = ', '.join([c['name'] for c in defense['top_contractors'][:3]]) if defense.get('top_contractors') else 'N/A'
                defense_text = f"""DEFENSE CONTRACTS (Last 7 Days):
- Total Value: {total_fmt} ({defense['count']} contracts)
- Top Contractors: {top_names}"""

            # Build Gemini prompt
            prompt = f"""Based on current aviation industry data, identify 3-5 key investment themes.

CURRENT MARKET CONTEXT (Last 7 Days):

{tsa_text}

{fred_text}

{stock_text}

{defense_text}

MAJOR HEADLINES:
{chr(10).join(context['headlines']) if context['headlines'] else '• No major headlines this week'}

OPERATIONAL RISKS:
{chr(10).join(f"• {r}" for r in context['operational_risks']) if context['operational_risks'] else '• No significant operational risks'}

FINANCIAL RISKS:
{chr(10).join(f"• {r}" for r in context['financial_risks']) if context['financial_risks'] else '• No significant financial risks'}

Generate 3-5 investment themes (one sentence each) that:
1. Incorporate the quantitative data (passenger trends, credit conditions, stock performance)
2. Reflect current market dynamics and trends
3. Highlight opportunities or positioning strategies
4. Use professional, analytical language suitable for institutional investors
5. Focus on actionable insights

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

            # Build quantitative summary
            quant_summary = ""
            if context.get('tsa_summary') or context.get('fred_summary') or context.get('stock_summary') or context.get('defense_summary'):
                quant_summary = "QUANTITATIVE INDICATORS:\n"
                if context.get('tsa_summary'):
                    tsa = context['tsa_summary']
                    quant_summary += f"- Passenger Traffic vs 2019: {tsa['avg_vs_2019']}%\n"
                if context.get('fred_summary'):
                    fred = context['fred_summary']
                    quant_summary += f"- Credit Spreads: {fred['spread_bps']}bps ({fred['risk_level']})\n"
                if context.get('stock_summary'):
                    stock = context['stock_summary']
                    quant_summary += f"- Sector Performance (5D): {stock['avg_sector_return']:+.1f}%\n"
                if context.get('defense_summary'):
                    defense = context['defense_summary']
                    total_fmt = f"${defense['total_value']/1_000_000_000:.1f}B" if defense['total_value'] >= 1_000_000_000 else f"${defense['total_value']/1_000_000:.0f}M"
                    quant_summary += f"- Defense Contracts (7D): {total_fmt} ({defense['count']} awards)\n"

            # Build Gemini prompt
            prompt = f"""Generate strategic investment recommendation for the aviation sector.

CONTEXT:

{quant_summary}

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
Reference the quantitative data where relevant.

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

            # Build market indicators section
            indicators_text = ""
            if context.get('tsa_summary') or context.get('fred_summary') or context.get('stock_summary') or context.get('defense_summary'):
                indicators_text = "MARKET INDICATORS:\n"
                if context.get('tsa_summary'):
                    tsa = context['tsa_summary']
                    indicators_text += f"- Passenger demand at {tsa['avg_vs_2019']}% of 2019 levels, trend: {tsa['trend']}\n"
                if context.get('fred_summary'):
                    fred = context['fred_summary']
                    indicators_text += f"- Credit spreads at {fred['spread_bps']}bps indicating {fred['condition'].lower()}\n"
                if context.get('stock_summary'):
                    stock = context['stock_summary']
                    sentiment = "positive" if stock['avg_sector_return'] > 0 else "negative" if stock['avg_sector_return'] < 0 else "neutral"
                    indicators_text += f"- Sector sentiment: {sentiment} ({stock['avg_sector_return']:+.1f}% average return)\n"
                if context.get('defense_summary'):
                    defense = context['defense_summary']
                    total_fmt = f"${defense['total_value']/1_000_000_000:.1f}B" if defense['total_value'] >= 1_000_000_000 else f"${defense['total_value']/1_000_000:.0f}M"
                    indicators_text += f"- Defense contract awards: {total_fmt} this week\n"

            # Build Gemini prompt
            prompt = f"""Generate a professional 2-3 sentence executive summary for aviation industry weekly outlook.

CURRENT CONTEXT (Last 7 Days):

{indicators_text}

MAJOR HEADLINES:
{chr(10).join(context['headlines'][:5]) if context['headlines'] else '• Market activity moderate this week'}

KEY RISKS:
Operational: {', '.join(context['operational_risks'][:2]) if context['operational_risks'] else 'Limited operational concerns'}
Financial: {', '.join(context['financial_risks'][:2]) if context['financial_risks'] else 'Stable financial environment'}

Create a concise, analytical summary (2-3 sentences) highlighting:
1. Overall sector health and momentum (resilient/strong/challenged/mixed)
2. Key trends or developments from the headlines
3. Notable risk factors or opportunities
4. Reference specific metrics where available (passenger demand, spreads, stock performance)

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
            Dictionary with market metrics, news headlines, risk factors, and quantitative data
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

            # Extract risk summaries (filter out None/empty values)
            op_risks = [r.get('impact_statement') or r.get('title') or '' for r in operational_risks]
            op_risks = [r for r in op_risks if r]  # Remove empty strings
            fin_risks = [r.get('impact_statement') or r.get('title') or '' for r in financial_risks]
            fin_risks = [r for r in fin_risks if r]  # Remove empty strings

            # NEW: Get TSA summary
            tsa_summary = None
            try:
                tsa_records = self.db.get_tsa_data(start_date=start_date, limit=7)
                if tsa_records:
                    total_passengers = sum(r.get('current_throughput', r.get('current_year', 0)) for r in tsa_records)
                    avg_vs_2019 = sum(r.get('compared_to_2019', 95) for r in tsa_records if r.get('compared_to_2019')) / max(1, len([r for r in tsa_records if r.get('compared_to_2019')]))
                    trend = tsa_records[0].get('trend_analysis', 'stable') if tsa_records else 'stable'
                    tsa_summary = {
                        'total_passengers_7d': total_passengers,
                        'avg_vs_2019': round(avg_vs_2019, 1),
                        'trend': trend
                    }
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch TSA data for market context: {e}")

            # NEW: Get FRED credit spreads
            fred_summary = None
            try:
                fred_records = self.db.get_fred_data(limit=1)
                if fred_records:
                    data = fred_records[0]
                    fred_summary = {
                        'spread_bps': data.get('credit_spread_bps', 150),
                        'risk_level': data.get('risk_level', 'moderate'),
                        'condition': data.get('spread_description', 'Normal conditions')
                    }
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch FRED data for market context: {e}")

            # NEW: Get sector stock performance
            stock_summary = None
            if self.stock_service:
                try:
                    carriers = ['United Airlines', 'Delta Air Lines', 'American Airlines', 'Southwest Airlines']
                    returns = []
                    for carrier in carriers:
                        stock = self.stock_service.get_stock_data(carrier, period='5d')
                        if stock and stock.get('day_change_percent') is not None:
                            returns.append(stock.get('day_change_percent', 0))
                    if returns:
                        avg_return = sum(returns) / len(returns)
                        stock_summary = {
                            'avg_sector_return': round(avg_return, 2),
                            'positive_count': sum(1 for r in returns if r > 0),
                            'total_carriers': len(returns)
                        }
                except Exception as e:
                    logger.warning(f"⚠️ Could not fetch stock data for market context: {e}")

            # NEW: Get defense contracts summary
            defense_summary = None
            try:
                defense_contracts = self.db.get_defense_contracts(
                    start_date=start_date,
                    limit=30
                )
                if defense_contracts:
                    total_value = sum(c.get('contract_value', 0) for c in defense_contracts)
                    # Get top contractors by value
                    contractors = {}
                    for c in defense_contracts:
                        name = c.get('contractor', 'Unknown')
                        contractors[name] = contractors.get(name, 0) + c.get('contract_value', 0)
                    top_contractors = sorted(contractors.items(), key=lambda x: x[1], reverse=True)[:3]
                    defense_summary = {
                        'total_value': total_value,
                        'count': len(defense_contracts),
                        'top_contractors': [{'name': name, 'value': value} for name, value in top_contractors]
                    }
                    logger.info(f"✅ Retrieved {len(defense_contracts)} defense contracts for market context")
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch defense contracts for market context: {e}")

            return {
                'headlines': headlines,
                'operational_risks': op_risks,
                'financial_risks': fin_risks,
                'article_count': len(recent_news),
                'tsa_summary': tsa_summary,
                'fred_summary': fred_summary,
                'stock_summary': stock_summary,
                'defense_summary': defense_summary
            }

        except Exception as e:
            logger.error(f"❌ Error getting market context: {e}")
            return {
                'headlines': [],
                'operational_risks': [],
                'financial_risks': [],
                'article_count': 0,
                'tsa_summary': None,
                'fred_summary': None,
                'stock_summary': None
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

            # Check if cache is still valid using cached_until timestamp
            cached_until = latest.get('cached_until')
            if cached_until:
                if datetime.now() < cached_until:
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
                'cached_until': datetime.now() + timedelta(days=cache_days)
            }

            self.db.save_insight(insight_data)
            logger.info(f"✅ Cached {insight_type} insights (valid for {cache_days} days)")

        except Exception as e:
            logger.error(f"❌ Error caching insights: {e}")

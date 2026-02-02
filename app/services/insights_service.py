#!/usr/bin/env python3
"""
Insights Service - Business logic for AI-generated reports and newsletters
Generates airline/industry reports and weekly newsletters using Gemini AI
"""

import logging
import markdown
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class InsightsService:
    """Service for generating AI-powered insights, reports, and newsletters"""

    def __init__(self, gemini_service, database_service):
        """
        Initialize insights service

        Args:
            gemini_service: GeminiService instance for AI generation
            database_service: DatabaseService instance for data retrieval
        """
        self.gemini = gemini_service
        self.db = database_service
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

            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Gather data from database
            news_articles = self.db.get_news_articles(
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                limit=100
            )

            tsa_data = self.db.get_tsa_data(
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )

            fred_data = self.db.get_latest_fred_data()

            # Build comprehensive prompt
            prompt = self._build_report_prompt(
                subject=subject,
                report_type=report_type,
                news_articles=news_articles,
                tsa_data=tsa_data,
                fred_data=fred_data,
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

            # Calculate week boundaries (Monday to Sunday)
            today = datetime.now()
            days_since_monday = today.weekday()
            last_monday = today - timedelta(days=days_since_monday + 7 + (week_offset * 7))
            last_sunday = last_monday + timedelta(days=6)

            week_start = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = last_sunday.replace(hour=23, minute=59, second=59, microsecond=999999)

            logger.info(f"📅 Newsletter period: {week_start.date()} to {week_end.date()}")

            # Get previous newsletter for historical context
            previous_newsletter = self.db.get_latest_newsletter()

            # Gather data from database
            news_articles = self.db.get_news_articles(
                start_date=week_start.isoformat(),
                end_date=week_end.isoformat(),
                limit=200
            )

            tsa_data = self.db.get_tsa_data(
                start_date=week_start.strftime('%Y-%m-%d'),
                end_date=week_end.strftime('%Y-%m-%d')
            )

            fred_data = self.db.get_latest_fred_data()

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
            sections = self._parse_sections(markdown_content)

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
                'sections': sections,
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
        period_start: datetime,
        period_end: datetime
    ) -> str:
        """Build comprehensive prompt for airline/sector report"""

        # Format news articles
        news_summary = self._format_news_articles(news_articles)

        # Format TSA data
        tsa_summary = self._format_tsa_data(tsa_data)

        # Format FRED data
        fred_summary = self._format_fred_data(fred_data)

        prompt = f"""You are an expert aviation industry analyst. Generate a comprehensive intelligence report about {subject}.

**Report Type**: {report_type.title()}
**Subject**: {subject}
**Period**: {period_start.strftime('%B %d, %Y')} to {period_end.strftime('%B %d, %Y')}

**Available Data**:

{news_summary}

{tsa_summary}

{fred_summary}

**Instructions**:
Generate a professional, data-driven report in Markdown format with the following sections:

## Executive Summary
- 2-3 paragraph overview of key findings
- Highlight most significant developments

## News Analysis
- Analyze major news stories and their implications
- Identify trends and patterns
- Quote specific articles when relevant

## Market Data Insights
- Analyze TSA passenger data trends
- Interpret credit spread data and financial conditions
- Connect market data to news developments

## Key Developments
- List and analyze the most important events
- Provide context and industry implications

## Risk Assessment
- Identify potential risks and challenges
- Rate overall risk level (Low/Moderate/High)

## Outlook & Recommendations
- Forward-looking analysis
- Strategic recommendations based on data

**Style Guidelines**:
- Professional, analytical tone
- Use data to support all claims
- Include specific numbers and percentages
- Cite news sources when quoting
- Be objective and balanced
- Use markdown formatting (headers, lists, bold, etc.)

Generate the report now:"""

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

        # Calculate aggregates
        total_current = sum(day.get('current_year', 0) for day in tsa_data)
        total_previous = sum(day.get('previous_year', 0) for day in tsa_data)

        if total_previous > 0:
            yoy_change = ((total_current - total_previous) / total_previous) * 100
            formatted += f"- Total Passengers: {total_current:,}\n"
            formatted += f"- Year-over-Year Change: {yoy_change:+.1f}%\n"
            formatted += f"- Period: {tsa_data[0].get('date')} to {tsa_data[-1].get('date')}\n\n"

        # Show recent days
        formatted += "Recent Daily Data:\n"
        for day in tsa_data[-7:]:  # Last 7 days
            date = day.get('date', 'Unknown')
            current = day.get('current_year', 0)
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
            # Get recent news articles (last 7 days)
            start_date = datetime.now() - timedelta(days=7)
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

#!/usr/bin/env python3
"""
Credit Qualitative Service - AI-Powered Credit Analysis
Uses Gemini 2.0 Flash to generate qualitative credit assessments
from quantitative inputs and recent news context.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List

logger = logging.getLogger(__name__)


class CreditQualitativeService:
    """Service for AI-generated qualitative credit analysis"""

    def __init__(self, gemini_service, db_service=None):
        """
        Initialize Credit Qualitative service.

        Args:
            gemini_service: GeminiService for AI generation
            db_service: DatabaseService for news/filings context
        """
        self.gemini = gemini_service
        self.db_service = db_service
        logger.info("✅ Credit Qualitative service initialized")

    def generate_qualitative_assessment(
        self,
        airline_code: str,
        airline_name: str,
        financial_score: float,
        signals_score: float,
        operational_score: float,
        financial_breakdown: Dict[str, Any],
        signals_breakdown: Dict[str, Any],
        operational_breakdown: Dict[str, Any],
        skip_in_backtest: bool = False
    ) -> Dict[str, Any]:
        """
        Generate qualitative credit assessment using Gemini.

        Args:
            airline_code: Ticker symbol
            airline_name: Full airline name
            financial_score: 0-100 score from XBRL analysis
            signals_score: 0-100 score from ratings/momentum
            operational_score: 0-100 score from ops metrics
            financial_breakdown: Detailed financial metrics
            signals_breakdown: Rating and momentum details
            operational_breakdown: Operational metrics
            skip_in_backtest: If True, return default values (for backtesting)

        Returns:
            Dict with qualitative_score, key_risks, key_strengths,
            sentiment_summary, outlook, narrative
        """
        if skip_in_backtest:
            logger.info(f"📊 Skipping Gemini assessment for {airline_code} (backtest mode)")
            return self._get_default_qualitative(airline_code, reason='Backtest mode - AI skipped')

        if not self.gemini:
            logger.warning(f"⚠️ Gemini service not available for {airline_code}")
            return self._get_default_qualitative(airline_code, reason='Gemini service not available')

        try:
            # Gather recent news context
            news_context = self._get_news_context(airline_code, airline_name)

            # Build prompt
            prompt = self._build_assessment_prompt(
                airline_code, airline_name,
                financial_score, signals_score, operational_score,
                financial_breakdown, signals_breakdown, operational_breakdown,
                news_context
            )

            # Call Gemini with low temperature for consistency
            logger.info(f"🤖 Generating Gemini assessment for {airline_code}...")
            response = self.gemini.generate_content(prompt, temperature=0.3)

            if not response:
                logger.warning(f"⚠️ Empty Gemini response for {airline_code}")
                return self._get_default_qualitative(airline_code, reason='Empty AI response')

            # Parse structured response
            result = self._parse_assessment_response(response, airline_code)

            logger.info(f"✅ Generated qualitative assessment for {airline_code}: score {result.get('qualitative_score', 'N/A')}")
            return result

        except Exception as e:
            logger.error(f"❌ Error generating qualitative assessment for {airline_code}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._get_default_qualitative(airline_code, reason=f'Error: {str(e)}')

    def _get_news_context(
        self,
        airline_code: str,
        airline_name: str,
        days: int = 30
    ) -> str:
        """Gather recent news articles for context."""
        if not self.db_service:
            return "No recent news available (database not connected)."

        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Search for airline-specific articles
            articles = self.db_service.get_articles(
                keywords=[airline_code, airline_name],
                start_date=start_date,
                end_date=end_date,
                limit=15
            )

            if not articles:
                return "No recent news articles found for this airline."

            # Format articles for prompt (limit to 5 most relevant)
            news_summaries = []
            for article in articles[:5]:
                title = article.get('title', 'Untitled')
                summary = article.get('summary', '')[:250]
                date = article.get('published_at', '')
                if hasattr(date, 'strftime'):
                    date = date.strftime('%Y-%m-%d')
                tags = ', '.join(article.get('tags', [])[:3])

                news_item = f"- [{date}] {title}"
                if summary:
                    news_item += f"\n  Summary: {summary}"
                if tags:
                    news_item += f"\n  Tags: {tags}"
                news_summaries.append(news_item)

            return "\n".join(news_summaries)

        except Exception as e:
            logger.warning(f"⚠️ Error fetching news context: {e}")
            return "Error fetching recent news."

    def _build_assessment_prompt(
        self,
        airline_code: str,
        airline_name: str,
        financial_score: float,
        signals_score: float,
        operational_score: float,
        financial_breakdown: Dict[str, Any],
        signals_breakdown: Dict[str, Any],
        operational_breakdown: Dict[str, Any],
        news_context: str
    ) -> str:
        """Build the Gemini prompt for qualitative assessment."""

        # Extract metrics for the prompt
        fin_metrics = financial_breakdown.get('metrics_used', {}) if financial_breakdown else {}
        sig_ratings = signals_breakdown.get('rating_component', {}).get('ratings', {}) if signals_breakdown else {}
        sig_trend = signals_breakdown.get('rating_component', {}).get('trend_direction', 'stable') if signals_breakdown else 'stable'
        sig_momentum = signals_breakdown.get('momentum_component', {}).get('price_change_pct', 'N/A') if signals_breakdown else 'N/A'
        ops_metrics = operational_breakdown.get('metrics', {}) if operational_breakdown else {}

        return f"""You are a senior credit analyst specializing in aviation finance at a major aircraft leasing company. Generate a qualitative credit assessment for {airline_name} ({airline_code}).

## QUANTITATIVE SCORES (0-100 scale, higher = better)
- **Financial Health Score**: {financial_score:.1f}/100
- **Credit Signals Score**: {signals_score:.1f}/100
- **Operational Score**: {operational_score:.1f}/100

## FINANCIAL METRICS (from SEC filings)
- Debt-to-Equity: {fin_metrics.get('debt_to_equity', 'N/A')}
- Interest Coverage: {fin_metrics.get('interest_coverage', 'N/A')}x
- Operating Margin: {fin_metrics.get('operating_margin', 'N/A')}%
- Current Ratio: {fin_metrics.get('current_ratio', 'N/A')}
- Cash Position: ${fin_metrics.get('cash_millions', 'N/A')}M
- Total Debt: ${fin_metrics.get('total_debt_millions', 'N/A')}M

## CREDIT SIGNALS
- Published Ratings: {sig_ratings}
- Rating Outlook/Trend: {sig_trend}
- 90-Day Stock Momentum: {sig_momentum}%

## OPERATIONAL METRICS
- Load Factor: {ops_metrics.get('load_factor', 'N/A')}%
- Fleet Average Age: {ops_metrics.get('fleet_age_years', 'N/A')} years
- Fleet Size: {ops_metrics.get('fleet_size', 'N/A')} aircraft
- RASM: {ops_metrics.get('rasm_cents', 'N/A')}¢
- CASM: {ops_metrics.get('casm_cents', 'N/A')}¢
- RASM-CASM Spread: {ops_metrics.get('rasm_spread', 'N/A')}¢

## RECENT NEWS (last 30 days)
{news_context}

## YOUR TASK
Based on the quantitative data and news context above, provide a qualitative credit assessment.

Generate a JSON response with EXACTLY this structure (no markdown code blocks, just raw JSON):

{{
  "qualitative_score": <integer 0-100>,
  "key_risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "key_strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "sentiment_summary": "<one sentence summarizing overall credit sentiment>",
  "outlook": "<positive|stable|negative>",
  "narrative": "<2-3 paragraph analysis of credit quality, key factors driving the assessment, and forward-looking view. Be specific to {airline_name} and reference actual data points.>"
}}

## SCORING GUIDELINES
- 80-100: Strong fundamentals, positive momentum, minimal near-term risks
- 60-79: Solid with some concerns, stable outlook
- 40-59: Notable risks or deteriorating trends
- 20-39: Significant concerns, negative momentum
- 0-19: Severe distress, imminent restructuring risk

Be specific and reference actual metrics. Focus on factors relevant to aircraft lessors: ability to make lease payments, fleet strategy, liquidity, and bankruptcy risk."""

    def _parse_assessment_response(
        self,
        response: str,
        airline_code: str
    ) -> Dict[str, Any]:
        """Parse Gemini response into structured format."""
        try:
            # Clean response (remove markdown code blocks if present)
            cleaned = response.strip()
            if cleaned.startswith('```'):
                # Remove code block markers
                lines = cleaned.split('\n')
                lines = [l for l in lines if not l.startswith('```')]
                cleaned = '\n'.join(lines)

            # Find JSON in response (sometimes Gemini adds text before/after)
            json_start = cleaned.find('{')
            json_end = cleaned.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                cleaned = cleaned[json_start:json_end]

            # Parse JSON
            result = json.loads(cleaned)

            # Validate required fields
            required = ['qualitative_score', 'key_risks', 'key_strengths',
                       'sentiment_summary', 'outlook', 'narrative']
            for field in required:
                if field not in result:
                    logger.warning(f"⚠️ Missing field in Gemini response: {field}")
                    result[field] = self._get_default_field(field)

            # Validate and clamp score range
            score = result.get('qualitative_score', 50)
            try:
                score = float(score)
                if not 0 <= score <= 100:
                    score = max(0, min(100, score))
            except (ValueError, TypeError):
                score = 50
            result['qualitative_score'] = round(score, 1)

            # Validate outlook
            if result.get('outlook') not in ['positive', 'stable', 'negative']:
                result['outlook'] = 'stable'

            # Ensure lists are lists
            for list_field in ['key_risks', 'key_strengths']:
                if not isinstance(result.get(list_field), list):
                    result[list_field] = [str(result.get(list_field, 'N/A'))]

            result['generated_at'] = datetime.utcnow().isoformat()
            result['is_ai_generated'] = True

            return result

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse error for {airline_code}: {e}")
            logger.debug(f"Raw response (first 500 chars): {response[:500]}")
            return self._get_default_qualitative(airline_code, reason=f'JSON parse error: {str(e)}')
        except Exception as e:
            logger.error(f"❌ Parse error for {airline_code}: {e}")
            return self._get_default_qualitative(airline_code, reason=f'Parse error: {str(e)}')

    def _get_default_field(self, field: str) -> Any:
        """Get default value for a missing field."""
        defaults = {
            'qualitative_score': 50,
            'key_risks': ['Assessment data incomplete'],
            'key_strengths': ['Quantitative scores available'],
            'sentiment_summary': 'Unable to generate complete assessment.',
            'outlook': 'stable',
            'narrative': 'Complete qualitative assessment could not be generated. Please review quantitative scores.'
        }
        return defaults.get(field, None)

    def _get_default_qualitative(
        self,
        airline_code: str,
        reason: str = 'AI assessment unavailable'
    ) -> Dict[str, Any]:
        """Return default qualitative assessment when AI fails or is skipped."""
        return {
            'qualitative_score': 50.0,
            'key_risks': [reason, 'Manual review recommended'],
            'key_strengths': ['Quantitative scores available', 'Historical data accessible'],
            'sentiment_summary': f'{reason} - using neutral default score.',
            'outlook': 'stable',
            'narrative': f'Qualitative assessment for {airline_code} could not be generated ({reason}). The default score of 50 has been applied. Please review the quantitative scores and conduct manual analysis as needed.',
            'is_default': True,
            'default_reason': reason,
            'generated_at': datetime.utcnow().isoformat()
        }

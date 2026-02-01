#!/usr/bin/env python3
"""
Article Enhancement Service - AI-powered article analysis
Generates summaries and impact statements using Gemini AI
"""

import logging
from typing import Optional, Dict, Any
from .gemini_service import GeminiService

logger = logging.getLogger(__name__)


class ArticleEnhancementService:
    """Enhances news articles with AI-generated summaries and impact analysis"""

    def __init__(self, gemini_service: GeminiService):
        self.gemini = gemini_service

    def generate_article_summary(self, article_title: str, article_content: str) -> Optional[str]:
        """
        Generate 100-200 word AI summary of article

        Args:
            article_title: Article headline
            article_content: Full article text or summary

        Returns:
            AI-generated summary (100-200 words) or None if failed
        """
        try:
            prompt = f"""Analyze this aviation industry news article and provide a comprehensive summary.

ARTICLE TITLE: {article_title}

ARTICLE CONTENT:
{article_content[:2000]}

Generate a professional 100-200 word summary that:
1. Captures the key facts and developments
2. Highlights business implications for the aviation sector
3. Uses industry-appropriate terminology
4. Maintains objective, analytical tone

Summary (100-200 words):"""

            summary = self.gemini.generate_content(prompt, temperature=0.3)

            if summary:
                # Trim if too long
                words = summary.split()
                if len(words) > 220:
                    summary = ' '.join(words[:200]) + '...'
                logger.info(f"✅ Generated AI summary ({len(words)} words)")
                return summary

            return None

        except Exception as e:
            logger.error(f"❌ Failed to generate article summary: {e}")
            return None

    def generate_impact_statement(self, article_title: str, article_content: str, tags: list) -> Optional[str]:
        """
        Generate one-sentence impact statement

        Args:
            article_title: Article headline
            article_content: Full article text or summary
            tags: Article categorization tags

        Returns:
            One-sentence impact statement or None if failed
        """
        try:
            tags_str = ', '.join(tags) if tags else 'general aviation'

            prompt = f"""Analyze this aviation industry news article and describe its impact in ONE SENTENCE.

ARTICLE TITLE: {article_title}
TAGS: {tags_str}

ARTICLE CONTENT:
{article_content[:1000]}

Generate ONE concise sentence (15-25 words) that describes:
- The direct impact on airlines, lessors, or the aviation industry
- The significance or implications of this development
- Use active, specific language

Impact Statement (one sentence):"""

            impact = self.gemini.generate_content(prompt, temperature=0.4)

            if impact:
                # Ensure it's one sentence
                impact = impact.strip().split('.')[0] + '.'
                logger.info(f"✅ Generated impact statement")
                return impact

            return None

        except Exception as e:
            logger.error(f"❌ Failed to generate impact statement: {e}")
            return None

    def enhance_article(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance article with AI-generated summary and impact statement

        Args:
            article_data: Dictionary with title, content, summary, tags

        Returns:
            Enhanced article_data with ai_summary and impact_statement fields
        """
        try:
            title = article_data.get('title', '')
            content = article_data.get('content', article_data.get('summary', ''))
            tags = article_data.get('tags', [])

            # Generate AI summary (100-200 words)
            ai_summary = self.generate_article_summary(title, content)
            if ai_summary:
                article_data['ai_summary'] = ai_summary

            # Generate impact statement (one sentence)
            impact = self.generate_impact_statement(title, content, tags)
            if impact:
                article_data['impact_statement'] = impact

            logger.info(f"✅ Article enhanced: {title[:50]}...")
            return article_data

        except Exception as e:
            logger.error(f"❌ Article enhancement failed: {e}")
            return article_data

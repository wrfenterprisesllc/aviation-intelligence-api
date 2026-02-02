#!/usr/bin/env python3
"""
Clean HTML markup from existing articles in Firestore
This script processes all articles and removes HTML tags from content and summary fields
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from bs4 import BeautifulSoup
import html as html_module
import re
from typing import Dict, Any

from app.services.database_service import DatabaseService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clean_html(html_content: str) -> str:
    """
    Remove HTML tags and clean content using BeautifulSoup
    (Same logic as rss_handler.py)
    """
    if not html_content:
        return ""

    try:
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements completely
        for script in soup(["script", "style", "iframe", "noscript"]):
            script.decompose()

        # Get text content
        text = soup.get_text()

        # Decode HTML entities
        text = html_module.unescape(text)

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        # Remove any remaining special characters or artifacts
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    except Exception as e:
        logger.warning(f"Error cleaning HTML content with BeautifulSoup: {e}")
        # Fallback to simple regex if BeautifulSoup fails
        try:
            clean_text = re.sub(r'<[^>]+>', '', html_content)
            clean_text = html_module.unescape(clean_text)
            clean_text = re.sub(r'\s+', ' ', clean_text)
            return clean_text.strip()
        except:
            return html_content


def clean_article_content(article: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
    """
    Clean HTML from article content and summary

    Returns:
        (needs_update, updated_fields) tuple
    """
    needs_update = False
    updated_fields = {}

    # Check if content has HTML tags
    content = article.get('content', '')
    if content and ('<' in content or '&' in content):
        cleaned_content = clean_html(content)
        if cleaned_content != content:
            updated_fields['content'] = cleaned_content
            needs_update = True
            logger.debug(f"Cleaned content: {len(content)} -> {len(cleaned_content)} chars")

    # Check if summary has HTML tags
    summary = article.get('summary', '')
    if summary and ('<' in summary or '&' in summary):
        cleaned_summary = clean_html(summary)
        if cleaned_summary != summary:
            updated_fields['summary'] = cleaned_summary
            needs_update = True
            logger.debug(f"Cleaned summary: {len(summary)} -> {len(cleaned_summary)} chars")

    return needs_update, updated_fields


def main():
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("ARTICLE CONTENT CLEANING SCRIPT")
    logger.info("=" * 60)

    # Initialize database service
    db = DatabaseService()

    # Get all articles
    logger.info("Fetching all articles from Firestore...")
    articles = db.get_articles(limit=1000)  # Process in batches of 1000
    logger.info(f"Found {len(articles)} articles to process")

    # Process statistics
    stats = {
        'total': len(articles),
        'cleaned': 0,
        'skipped': 0,
        'errors': 0
    }

    # Process each article
    for i, article in enumerate(articles, 1):
        try:
            article_id = article.get('id')
            title = article.get('title', 'Unknown')[:50]

            logger.info(f"[{i}/{len(articles)}] Processing: {title}...")

            # Clean the article
            needs_update, updated_fields = clean_article_content(article)

            if needs_update:
                # Update the article in Firestore
                logger.info(f"  ✓ Updating article {article_id}: {list(updated_fields.keys())}")
                db.update_article(article_id, updated_fields)
                stats['cleaned'] += 1
            else:
                logger.info(f"  → No HTML found, skipping")
                stats['skipped'] += 1

        except Exception as e:
            logger.error(f"  ✗ Error processing article: {e}")
            stats['errors'] += 1

    # Print summary
    logger.info("=" * 60)
    logger.info("CLEANING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total articles: {stats['total']}")
    logger.info(f"Cleaned: {stats['cleaned']}")
    logger.info(f"Skipped (no HTML): {stats['skipped']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("=" * 60)

    logger.info("✅ Article cleaning complete!")
    logger.info("Next step: Run AI enhancement script to regenerate summaries")
    logger.info("  Command: curl -X POST https://aviation-intelligence-api-rmexsuffdq-uc.a.run.app/api/news/enhance-batch \\")
    logger.info("           -H 'Content-Type: application/json' \\")
    logger.info("           -H 'X-API-Key: YOUR_API_KEY' \\")
    logger.info("           -d '{\"limit\": 50}'")


if __name__ == '__main__':
    main()

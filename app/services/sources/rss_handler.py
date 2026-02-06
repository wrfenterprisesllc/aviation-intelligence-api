"""
RSS Feed Handler for Aviation News Sources
Fetches and parses RSS feeds from various aviation industry sources
"""

import logging
import feedparser
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse
import time

from app.models.news_article import NewsArticle
from .article_scraper import ArticleScraper
from app.utils.text_cleaner import strip_images_from_html

logger = logging.getLogger(__name__)

class RSSHandler:
    """Handles RSS feed parsing and article extraction"""
    
    def __init__(self, timeout: int = 60, user_agent: str = None):
        """
        Initialize RSS handler

        Args:
            timeout: Request timeout in seconds (default: 60)
            user_agent: Custom user agent string
        """
        self.timeout = timeout
        self.user_agent = user_agent or 'Aviation-Intelligence-Platform/1.0 (+https://ai.wrfenterprisesllc.com)'

        # Configure requests session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'application/rss+xml, application/xml, text/xml'
        })

        # Initialize article scraper for full content extraction
        self.scraper = ArticleScraper(timeout=timeout, user_agent=user_agent)
    
    def fetch_articles(self, source_id: str, feed_url: str, max_articles: int = 50) -> List[NewsArticle]:
        """
        Fetch and parse articles from an RSS feed
        
        Args:
            source_id: Identifier for the news source
            feed_url: RSS feed URL
            max_articles: Maximum number of articles to fetch
            
        Returns:
            List of NewsArticle objects
        """
        logger.info(f"Fetching RSS feed: {feed_url}")
        
        try:
            # Fetch the feed
            response = self.session.get(feed_url, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse the feed
            feed = feedparser.parse(response.content)
            
            # Check for parsing errors
            if hasattr(feed, 'bozo') and feed.bozo:
                logger.warning(f"Feed parsing warnings for {feed_url}: {feed.bozo_exception}")
            
            # Extract articles
            articles = []
            for entry in feed.entries[:max_articles]:
                try:
                    article = self._parse_entry(source_id, entry, feed)
                    if article:
                        articles.append(article)
                        
                except Exception as e:
                    logger.error(f"Error parsing RSS entry: {e}")
                    continue
            
            logger.info(f"Successfully parsed {len(articles)} articles from {feed_url}")
            return articles
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching RSS feed {feed_url}: {e}")
            return []
            
        except Exception as e:
            logger.error(f"Unexpected error processing RSS feed {feed_url}: {e}")
            return []
    
    def _parse_entry(self, source_id: str, entry: Any, feed: Any) -> NewsArticle:
        """
        Parse a single RSS entry into a NewsArticle
        
        Args:
            source_id: Source identifier
            entry: feedparser entry object
            feed: feedparser feed object
            
        Returns:
            NewsArticle object or None if parsing fails
        """
        try:
            # Extract basic fields
            title = self._clean_text(getattr(entry, 'title', ''))
            if not title:
                logger.warning("Skipping entry with no title")
                return None
            
            # Get article URL
            source_url = getattr(entry, 'link', '')
            if not source_url:
                logger.warning(f"Skipping entry with no URL: {title}")
                return None
            
            # Extract content/summary
            content = self._extract_content(entry)
            summary = self._extract_summary(entry, content)

            # Attempt to scrape full content if RSS content is truncated
            if self.scraper.should_scrape(content, source_url):
                logger.info(f"🔍 Attempting to scrape full content for: {title[:60]}...")
                full_content = self.scraper.fetch_full_content(source_url)

                if full_content:
                    content = full_content  # Replace truncated content with full text
                    logger.info(f"✅ Replaced truncated content with {len(content)} chars")
                else:
                    logger.info(f"⚠️  Scraping failed, keeping RSS content ({len(content)} chars)")

            # Parse publication date
            published_at = self._parse_date(entry)
            
            # Get current time for ingestion timestamp
            ingested_at = datetime.utcnow()
            
            # Extract tags based on RSS categories
            tags = self._extract_tags(entry)
            
            # Clean images from content and summary
            content = strip_images_from_html(content) if content else content
            summary = strip_images_from_html(summary) if summary else summary

            # Build raw payload for debugging/reprocessing
            raw_payload = {
                'feed_title': getattr(feed, 'title', ''),
                'feed_url': getattr(feed, 'href', ''),
                'entry_id': getattr(entry, 'id', ''),
                'entry_updated': getattr(entry, 'updated', ''),
                'entry_author': getattr(entry, 'author', ''),
                'entry_categories': getattr(entry, 'tags', [])
            }

            # Create NewsArticle
            article = NewsArticle(
                source=source_id,
                source_url=source_url,
                title=title,
                summary=summary,
                content=content,
                published_at=published_at,
                ingested_at=ingested_at,
                tags=tags,
                entities=[],  # Will be populated by future entity extraction
                raw_payload=raw_payload
            )
            
            return article
            
        except Exception as e:
            logger.error(f"Error parsing RSS entry: {e}")
            return None
    
    def _extract_content(self, entry: Any) -> str:
        """Extract full content from RSS entry"""
        # Try various content fields
        content_fields = [
            'content',      # Full content
            'description',  # Usually summary but sometimes full content
            'summary',      # Summary
        ]
        
        for field in content_fields:
            if hasattr(entry, field):
                field_value = getattr(entry, field)
                
                # Handle different content formats
                if isinstance(field_value, list):
                    # Multiple content entries (e.g., different formats)
                    for content_item in field_value:
                        if hasattr(content_item, 'value'):
                            return self._clean_html(content_item.value)
                        elif isinstance(content_item, dict) and 'value' in content_item:
                            return self._clean_html(content_item['value'])
                elif isinstance(field_value, str):
                    return self._clean_html(field_value)
        
        return ""
    
    def _extract_summary(self, entry: Any, content: str) -> str:
        """Extract or generate summary from RSS entry"""
        # Try summary field first
        if hasattr(entry, 'summary'):
            summary = self._clean_html(entry.summary)
            if summary:
                return summary[:1000]  # Limit summary length
        
        # Fall back to truncated content
        if content:
            # Remove extra whitespace and truncate
            clean_content = ' '.join(content.split())
            if len(clean_content) > 500:
                return clean_content[:497] + "..."
            return clean_content
        
        return ""
    
    def _parse_date(self, entry: Any) -> datetime:
        """Parse publication date from RSS entry"""
        # Try various date fields
        date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']
        
        for field in date_fields:
            if hasattr(entry, field):
                parsed_time = getattr(entry, field)
                if parsed_time:
                    try:
                        # Convert time.struct_time to datetime
                        return datetime(*parsed_time[:6], tzinfo=timezone.utc).replace(tzinfo=None)
                    except (TypeError, ValueError):
                        continue
        
        # Try string date fields
        string_date_fields = ['published', 'updated', 'created']
        for field in string_date_fields:
            if hasattr(entry, field):
                date_string = getattr(entry, field)
                if date_string:
                    try:
                        # Let feedparser handle the parsing
                        parsed = feedparser._parse_date(date_string)
                        if parsed:
                            return datetime(*parsed[:6], tzinfo=timezone.utc).replace(tzinfo=None)
                    except:
                        continue
        
        # Default to current time if no date found
        logger.warning("No publication date found, using current time")
        return datetime.utcnow()
    
    def _extract_tags(self, entry: Any) -> List[str]:
        """Extract tags/categories from RSS entry"""
        tags = []
        
        # Extract from RSS categories/tags
        if hasattr(entry, 'tags'):
            for tag in entry.tags:
                if hasattr(tag, 'term'):
                    tags.append(tag.term.lower())
                elif isinstance(tag, dict) and 'term' in tag:
                    tags.append(tag['term'].lower())
                elif isinstance(tag, str):
                    tags.append(tag.lower())
        
        # Clean up tags
        cleaned_tags = []
        for tag in tags:
            if tag and isinstance(tag, str):
                # Remove special characters and normalize
                clean_tag = ''.join(c for c in tag if c.isalnum() or c in [' ', '_', '-']).strip()
                if clean_tag and len(clean_tag) > 1:
                    cleaned_tags.append(clean_tag.replace(' ', '_'))
        
        return list(set(cleaned_tags))  # Remove duplicates
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Remove extra whitespace
        cleaned = ' '.join(text.split())
        
        # Basic HTML entity decoding
        import html
        cleaned = html.unescape(cleaned)
        
        return cleaned.strip()
    
    def _clean_html(self, html_content: str) -> str:
        """Remove HTML tags and clean content using BeautifulSoup"""
        if not html_content:
            return ""

        try:
            from bs4 import BeautifulSoup
            import html as html_module
            import re

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
                import re
                import html as html_module
                clean_text = re.sub(r'<[^>]+>', '', html_content)
                clean_text = html_module.unescape(clean_text)
                clean_text = re.sub(r'\s+', ' ', clean_text)
                return clean_text.strip()
            except:
                return html_content
    
    def test_feed(self, feed_url: str) -> Dict[str, Any]:
        """
        Test an RSS feed and return basic information
        
        Args:
            feed_url: RSS feed URL to test
            
        Returns:
            Dictionary with feed information and test results
        """
        try:
            logger.info(f"Testing RSS feed: {feed_url}")
            
            # Fetch and parse feed
            response = self.session.get(feed_url, timeout=self.timeout)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            
            # Extract feed information
            feed_info = {
                'url': feed_url,
                'title': getattr(feed.feed, 'title', 'Unknown'),
                'description': getattr(feed.feed, 'description', ''),
                'language': getattr(feed.feed, 'language', ''),
                'last_updated': getattr(feed.feed, 'updated', ''),
                'total_entries': len(feed.entries),
                'bozo': getattr(feed, 'bozo', False),
                'bozo_exception': str(getattr(feed, 'bozo_exception', '')),
                'success': True,
                'sample_entries': []
            }
            
            # Get sample entries
            for entry in feed.entries[:3]:
                entry_info = {
                    'title': getattr(entry, 'title', ''),
                    'link': getattr(entry, 'link', ''),
                    'published': getattr(entry, 'published', ''),
                    'summary': getattr(entry, 'summary', '')[:200] + '...' if getattr(entry, 'summary', '') else ''
                }
                feed_info['sample_entries'].append(entry_info)
            
            return feed_info
            
        except Exception as e:
            return {
                'url': feed_url,
                'success': False,
                'error': str(e),
                'total_entries': 0
            }
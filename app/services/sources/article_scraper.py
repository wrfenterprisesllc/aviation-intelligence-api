"""
Article Content Scraper
Fetches full article text from URLs using newspaper4k
"""

from newspaper import Article, Config, ArticleException
from typing import Optional
import logging
import time

logger = logging.getLogger(__name__)


class ArticleScraper:
    """Scrapes full article content from news websites"""

    def __init__(self, timeout: int = 60, user_agent: Optional[str] = None):
        """
        Initialize article scraper

        Args:
            timeout: HTTP request timeout in seconds (default: 60)
            user_agent: Custom User-Agent string (default: Aviation-Intelligence-Platform/1.0)
        """
        self.timeout = timeout
        self.user_agent = user_agent or 'Aviation-Intelligence-Platform/1.0 (+https://ai.wrfenterprisesllc.com)'

        # Configure newspaper settings
        self.config = Config()
        self.config.browser_user_agent = self.user_agent
        self.config.request_timeout = timeout
        self.config.follow_robots_txt = False  # More aggressive scraping (was True)
        self.config.fetch_images = False  # We only need text content
        self.config.memoize_articles = False  # Don't cache (we have our own storage)

    def fetch_full_content(self, url: str, retry_count: int = 2) -> Optional[str]:
        """
        Fetch and extract full article text from URL with retry logic

        Args:
            url: Article URL to scrape
            retry_count: Number of retry attempts (default: 2)

        Returns:
            Full article text or None if scraping fails after all retries
        """
        for attempt in range(retry_count):
            try:
                # Create Article object with configuration
                article = Article(url, config=self.config, language='en')

                # Download and parse
                article.download()
                article.parse()

                # Extract clean text (no HTML, no images)
                if article.text and len(article.text) > 200:
                    char_count = len(article.text)
                    logger.info(f"✅ Scraped {char_count} chars from {url[:60]}... (attempt {attempt + 1})")
                    return article.text  # Plain text, automatically excludes HTML/images
                else:
                    logger.warning(f"⚠️  Scraped content too short ({len(article.text or '')} chars) from {url[:60]}...")

            except ArticleException as e:
                logger.warning(f"❌ Scraping failed (attempt {attempt + 1}/{retry_count}) for {url[:60]}...: {str(e)[:100]}")
                if attempt < retry_count - 1:
                    # Exponential backoff before retry
                    wait_time = 2 ** attempt
                    logger.debug(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
            except Exception as e:
                logger.error(f"❌ Unexpected error scraping {url[:60]}...: {str(e)[:100]}")
                # Don't retry on unexpected errors
                break

        # All retry attempts failed
        logger.warning(f"❌ Failed to scrape {url[:60]}... after {retry_count} attempts")
        return None

    def should_scrape(self, current_content: str, source_url: str) -> bool:
        """
        Determine if we should attempt to scrape full content

        Args:
            current_content: Content from RSS/API
            source_url: URL to scrape

        Returns:
            True if scraping is worthwhile
        """
        # Don't scrape if we already have substantial content
        if len(current_content) > 1000:
            return False

        # Don't scrape SEC filings (use SEC API instead)
        if 'sec.gov' in source_url.lower():
            return False

        # Don't scrape PDFs or non-HTML content
        if any(ext in source_url.lower() for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx']):
            return False

        # Don't scrape video/media URLs
        if any(media in source_url.lower() for media in ['youtube.com', 'vimeo.com', 'youtu.be']):
            return False

        return True

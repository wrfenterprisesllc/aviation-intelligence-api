"""
Aviation News Ingestion Service
Coordinates pulling news from multiple sources and storing in Firestore
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Import the database service (use backend's database service)
from app.services.database_service import DatabaseService
from app.models.news_article import NewsArticle, AVIATION_SOURCES

# Import source handlers
from app.services.sources.rss_handler import RSSHandler
from app.services.sources.newsapi_handler import NewsAPIHandler
from app.services.sources.sec_edgar_handler import SECEdgarHandler

# Configure logging
logger = logging.getLogger(__name__)


class NewsIngestionService:
    """
    Main news ingestion service that orchestrates pulling from multiple sources
    """

    def __init__(self):
        """
        Initialize the news ingestion service
        """
        # Use backend's database service instead of direct Firestore client
        self.db_service = DatabaseService()

        # Initialize source handlers
        self.rss_handler = RSSHandler()
        self.newsapi_handler = NewsAPIHandler()
        self.sec_handler = SECEdgarHandler()

        # Track ingestion statistics
        self.stats = {
            'articles_processed': 0,
            'articles_saved': 0,
            'articles_skipped': 0,
            'errors': 0,
            'sources_processed': 0
        }

    def ingest_all_sources(self, source_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Ingest from all configured news sources

        Args:
            source_types: Optional list of source types to ingest ('rss', 'newsapi', 'sec_edgar')
                         If None, ingests from all active sources

        Returns:
            Dictionary with ingestion statistics
        """
        logger.info("Starting news ingestion from all sources")
        start_time = datetime.utcnow()

        # Reset stats
        self.stats = {
            'articles_processed': 0,
            'articles_saved': 0,
            'articles_skipped': 0,
            'errors': 0,
            'sources_processed': 0,
            'start_time': start_time,
            'sources_attempted': []
        }

        try:
            # Process RSS feeds
            if not source_types or 'rss' in source_types:
                self._ingest_rss_sources()

            # Process NewsAPI
            if not source_types or 'newsapi' in source_types:
                self._ingest_newsapi()

            # Process SEC EDGAR (typically weekly)
            if not source_types or 'sec_edgar' in source_types:
                self._ingest_sec_edgar()

        except Exception as e:
            logger.error(f"Critical error during ingestion: {e}")
            self.stats['errors'] += 1

        # Finalize stats
        self.stats['end_time'] = datetime.utcnow()
        self.stats['duration_seconds'] = (self.stats['end_time'] - start_time).total_seconds()

        # Log ingestion summary
        self._log_ingestion_summary()

        return self.stats

    def _ingest_rss_sources(self) -> None:
        """Process all RSS feed sources"""
        logger.info("Processing RSS feed sources")

        for source_id, config in AVIATION_SOURCES.items():
            if config.get('type') == 'rss' and config.get('active', False):
                try:
                    self.stats['sources_attempted'].append(source_id)
                    articles = self.rss_handler.fetch_articles(source_id, config['url'])

                    for article in articles:
                        if self._process_article(article):
                            self.stats['articles_saved'] += 1
                        else:
                            self.stats['articles_skipped'] += 1
                        self.stats['articles_processed'] += 1

                    self.stats['sources_processed'] += 1
                    logger.info(f"Processed {len(articles)} articles from {config['name']}")

                except Exception as e:
                    logger.error(f"Error processing RSS source {source_id}: {e}")
                    self.stats['errors'] += 1

    def _ingest_newsapi(self) -> None:
        """Process NewsAPI source"""
        logger.info("Processing NewsAPI source")

        try:
            self.stats['sources_attempted'].append('newsapi')
            articles = self.newsapi_handler.fetch_articles()

            for article in articles:
                if self._process_article(article):
                    self.stats['articles_saved'] += 1
                else:
                    self.stats['articles_skipped'] += 1
                self.stats['articles_processed'] += 1

            self.stats['sources_processed'] += 1
            logger.info(f"Processed {len(articles)} articles from NewsAPI")

        except Exception as e:
            logger.error(f"Error processing NewsAPI: {e}")
            self.stats['errors'] += 1

    def _ingest_sec_edgar(self) -> None:
        """Process SEC EDGAR filings"""
        logger.info("Processing SEC EDGAR filings")

        try:
            self.stats['sources_attempted'].append('sec_edgar')
            articles = self.sec_handler.fetch_recent_filings()

            for article in articles:
                if self._process_article(article):
                    self.stats['articles_saved'] += 1
                else:
                    self.stats['articles_skipped'] += 1
                self.stats['articles_processed'] += 1

            self.stats['sources_processed'] += 1
            logger.info(f"Processed {len(articles)} SEC filings")

        except Exception as e:
            logger.error(f"Error processing SEC EDGAR: {e}")
            self.stats['errors'] += 1

    def _process_article(self, article: NewsArticle) -> bool:
        """
        Process a single article: validate, check for duplicates, and save

        Args:
            article: NewsArticle instance to process

        Returns:
            True if article was saved, False if skipped
        """
        try:
            # Validate article
            if not article.is_valid():
                logger.warning(f"Invalid article skipped: {article.validate()}")
                return False

            # Auto-tag article
            article.auto_tag()

            # Save to Firestore using database service
            return self._save_article(article)

        except Exception as e:
            logger.error(f"Error processing article {article.source_url}: {e}")
            self.stats['errors'] += 1
            return False

    def _save_article(self, article: NewsArticle) -> bool:
        """
        Save article to Firestore using database service

        Args:
            article: NewsArticle instance to save

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Convert to Firestore format
            article_data = article.to_firestore_dict()

            # Use the database service to save (it handles deduplication via MD5 hash)
            doc_id = self.db_service.save_article(article_data)

            if doc_id:
                logger.debug(f"Saved article: {article.title[:50]}...")
                return True
            else:
                # Article was likely a duplicate (database_service returns None for duplicates)
                return False

        except Exception as e:
            logger.error(f"Error saving article {article.source_url}: {e}")
            self.stats['errors'] += 1
            return False

    def _log_ingestion_summary(self) -> None:
        """Log summary of ingestion process"""
        logger.info("="*60)
        logger.info("NEWS INGESTION SUMMARY")
        logger.info("="*60)
        logger.info(f"Duration: {self.stats.get('duration_seconds', 0):.2f} seconds")
        logger.info(f"Sources attempted: {len(self.stats.get('sources_attempted', []))}")
        logger.info(f"Sources processed successfully: {self.stats['sources_processed']}")
        logger.info(f"Articles processed: {self.stats['articles_processed']}")
        logger.info(f"Articles saved: {self.stats['articles_saved']}")
        logger.info(f"Articles skipped (duplicates): {self.stats['articles_skipped']}")
        logger.info(f"Errors encountered: {self.stats['errors']}")

        if self.stats['articles_processed'] > 0:
            save_rate = (self.stats['articles_saved'] / self.stats['articles_processed']) * 100
            logger.info(f"Save rate: {save_rate:.1f}%")

        logger.info("="*60)

    def get_recent_articles(self,
                          hours: int = 24,
                          source: Optional[str] = None,
                          tags: Optional[List[str]] = None,
                          limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieve recent articles from Firestore using database service

        Args:
            hours: Number of hours back to look
            source: Optional source filter
            tags: Optional tags filter
            limit: Maximum number of articles to return

        Returns:
            List of article dictionaries
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            # Use database service to get articles
            articles = self.db_service.get_articles(
                source=source,
                tags=tags,
                start_date=cutoff_time,
                limit=limit
            )

            return articles

        except Exception as e:
            logger.error(f"Error retrieving recent articles: {e}")
            return []

    def delete_old_articles(self, days: int = 90) -> int:
        """
        Delete articles older than specified days using database service

        Args:
            days: Number of days to keep articles

        Returns:
            Number of articles deleted
        """
        try:
            deleted_count = self.db_service.delete_old_articles(days_to_keep=days)
            return deleted_count

        except Exception as e:
            logger.error(f"Error deleting old articles: {e}")
            return 0

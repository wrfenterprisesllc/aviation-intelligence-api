"""
Database Service - Firestore Integration
Handles all database operations for the Aviation Intelligence API
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter


class DatabaseService:
    """Service for interacting with Firestore database"""

    def __init__(self):
        """Initialize Firestore client"""
        self.logger = logging.getLogger(__name__)

        # Get configuration from environment variables
        project_id = os.getenv('GCP_PROJECT_ID', 'ai-projects-485420')
        database_name = os.getenv('FIRESTORE_DATABASE', 'aviation-intelligence')

        try:
            self.db = firestore.Client(
                project=project_id,
                database=database_name
            )
            self.logger.info(f"✅ Firestore client initialized: {project_id}/{database_name}")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Firestore: {e}")
            raise

    # ========== NEWS ARTICLES ==========

    def save_article(self, article_data: Dict[str, Any]) -> Optional[str]:
        """
        Save news article to Firestore (skips duplicates)

        Args:
            article_data: Dictionary containing article fields
                - source: str
                - source_url: str (unique identifier)
                - title: str
                - summary: str
                - content: str
                - published_at: datetime
                - tags: List[str]
                - raw_payload: Dict

        Returns:
            Document ID if successfully saved, None if duplicate or error
        """
        try:
            # Validate required fields
            required_fields = ['source', 'source_url', 'title']
            for field in required_fields:
                if field not in article_data:
                    raise ValueError(f"Missing required field: {field}")

            # Use source_url hash as document ID for deduplication
            import hashlib
            doc_id = hashlib.md5(article_data['source_url'].encode()).hexdigest()

            # Check if article already exists
            doc_ref = self.db.collection('news_articles').document(doc_id)
            if doc_ref.get().exists:
                self.logger.debug(f"Duplicate article skipped: {article_data['title'][:50]}... ({doc_id})")
                return None

            # Add ingestion timestamp
            article_data['ingested_at'] = datetime.now()

            # Save to Firestore (only if new)
            doc_ref.set(article_data)

            self.logger.info(f"Saved NEW article: {article_data['title'][:50]}... ({doc_id})")
            return doc_id

        except Exception as e:
            self.logger.error(f"Error saving article: {e}")
            return None

    def get_articles(
        self,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Query articles with optional filters

        Args:
            source: Filter by source (e.g., 'newsapi', 'rss_feed')
            tags: Filter by tags (articles must have any of these tags)
            start_date: Filter articles published after this date
            end_date: Filter articles published before this date
            limit: Maximum number of articles to return
            offset: Number of articles to skip

        Returns:
            List of article dictionaries
        """
        try:
            # Start with base query
            query = self.db.collection('news_articles')

            # Apply filters
            if source:
                query = query.where(filter=FieldFilter('source', '==', source))

            if start_date:
                query = query.where(filter=FieldFilter('published_at', '>=', start_date))

            if end_date:
                query = query.where(filter=FieldFilter('published_at', '<=', end_date))

            # Order by published date (newest first)
            query = query.order_by('published_at', direction=firestore.Query.DESCENDING)

            # Apply offset and limit
            if offset > 0:
                query = query.offset(offset)
            query = query.limit(limit)

            # Execute query
            docs = query.stream()

            articles = []
            for doc in docs:
                article_data = doc.to_dict()
                article_data['id'] = doc.id

                # Convert Firestore timestamps to datetime
                if 'published_at' in article_data and hasattr(article_data['published_at'], 'timestamp'):
                    article_data['published_at'] = article_data['published_at'].replace(tzinfo=None)
                if 'ingested_at' in article_data and hasattr(article_data['ingested_at'], 'timestamp'):
                    article_data['ingested_at'] = article_data['ingested_at'].replace(tzinfo=None)

                # Client-side tag filtering (Firestore doesn't support array-contains-any efficiently with other filters)
                if tags:
                    article_tags = article_data.get('tags', [])
                    if not any(tag in article_tags for tag in tags):
                        continue

                articles.append(article_data)

            self.logger.info(f"Retrieved {len(articles)} articles")
            return articles

        except Exception as e:
            self.logger.error(f"Error querying articles: {e}")
            return []

    def get_article_by_id(self, article_id: str) -> Optional[Dict[str, Any]]:
        """
        Get single article by ID

        Args:
            article_id: Document ID

        Returns:
            Article dictionary or None if not found
        """
        try:
            doc_ref = self.db.collection('news_articles').document(article_id)
            doc = doc_ref.get()

            if doc.exists:
                article_data = doc.to_dict()
                article_data['id'] = doc.id

                # Convert timestamps
                if 'published_at' in article_data and hasattr(article_data['published_at'], 'timestamp'):
                    article_data['published_at'] = article_data['published_at'].replace(tzinfo=None)
                if 'ingested_at' in article_data and hasattr(article_data['ingested_at'], 'timestamp'):
                    article_data['ingested_at'] = article_data['ingested_at'].replace(tzinfo=None)

                return article_data
            else:
                self.logger.warning(f"Article not found: {article_id}")
                return None

        except Exception as e:
            self.logger.error(f"Error fetching article {article_id}: {e}")
            return None

    def delete_old_articles(self, days_to_keep: int = 90) -> int:
        """
        Delete articles older than specified days

        Args:
            days_to_keep: Number of days to retain articles

        Returns:
            Number of articles deleted
        """
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            query = self.db.collection('news_articles').where(
                filter=FieldFilter('ingested_at', '<', cutoff_date)
            )

            deleted_count = 0
            for doc in query.stream():
                doc.reference.delete()
                deleted_count += 1

            self.logger.info(f"Deleted {deleted_count} old articles (older than {days_to_keep} days)")
            return deleted_count

        except Exception as e:
            self.logger.error(f"Error deleting old articles: {e}")
            return 0

    def get_article_stats(self) -> Dict[str, Any]:
        """
        Get statistics about articles in database

        Returns:
            Dictionary with stats (total count, counts by source, date range)
        """
        try:
            stats = {
                'total_articles': 0,
                'by_source': {},
                'date_range': {
                    'oldest': None,
                    'newest': None
                }
            }

            # Get all articles (limited query for stats)
            docs = self.db.collection('news_articles').stream()

            for doc in docs:
                stats['total_articles'] += 1
                data = doc.to_dict()

                # Count by source
                source = data.get('source', 'unknown')
                stats['by_source'][source] = stats['by_source'].get(source, 0) + 1

                # Track date range
                pub_date = data.get('published_at')
                if pub_date:
                    if hasattr(pub_date, 'timestamp'):
                        pub_date = pub_date.replace(tzinfo=None)

                    if stats['date_range']['oldest'] is None or pub_date < stats['date_range']['oldest']:
                        stats['date_range']['oldest'] = pub_date
                    if stats['date_range']['newest'] is None or pub_date > stats['date_range']['newest']:
                        stats['date_range']['newest'] = pub_date

            return stats

        except Exception as e:
            self.logger.error(f"Error getting article stats: {e}")
            return {'error': str(e)}

    # ========== AI INSIGHTS ==========

    def save_insight(self, insight_data: Dict[str, Any]) -> Optional[str]:
        """
        Save AI-generated insight to Firestore

        Args:
            insight_data: Dictionary containing insight fields
                - timeframe: str ('daily', 'weekly', 'monthly')
                - generated_at: datetime
                - articles_analyzed: int
                - key_trends: List[str]
                - sentiment: str
                - summary: str
                - cached_until: datetime

        Returns:
            Document ID if successful, None otherwise
        """
        try:
            # Add timestamp if not provided
            if 'generated_at' not in insight_data:
                insight_data['generated_at'] = datetime.now()

            # Save to Firestore (auto-generate ID)
            doc_ref = self.db.collection('insights').document()
            doc_ref.set(insight_data)

            self.logger.info(f"Saved insight: {insight_data.get('timeframe', 'unknown')} ({doc_ref.id})")
            return doc_ref.id

        except Exception as e:
            self.logger.error(f"Error saving insight: {e}")
            return None

    def get_latest_insight(self, timeframe: str = 'weekly') -> Optional[Dict[str, Any]]:
        """
        Get the most recent cached insight for a timeframe

        Args:
            timeframe: 'daily', 'weekly', or 'monthly'

        Returns:
            Insight dictionary or None if not found
        """
        try:
            query = (self.db.collection('insights')
                    .where(filter=FieldFilter('timeframe', '==', timeframe))
                    .where(filter=FieldFilter('cached_until', '>', datetime.now()))
                    .order_by('generated_at', direction=firestore.Query.DESCENDING)
                    .limit(1))

            docs = list(query.stream())

            if docs:
                insight_data = docs[0].to_dict()
                insight_data['id'] = docs[0].id

                # Convert timestamps
                if 'generated_at' in insight_data and hasattr(insight_data['generated_at'], 'timestamp'):
                    insight_data['generated_at'] = insight_data['generated_at'].replace(tzinfo=None)
                if 'cached_until' in insight_data and hasattr(insight_data['cached_until'], 'timestamp'):
                    insight_data['cached_until'] = insight_data['cached_until'].replace(tzinfo=None)

                return insight_data
            else:
                self.logger.info(f"No cached {timeframe} insight found")
                return None

        except Exception as e:
            self.logger.error(f"Error fetching insight: {e}")
            return None

    # ========== HEALTH CHECK ==========

    def health_check(self) -> Dict[str, Any]:
        """
        Check database connectivity and basic stats

        Returns:
            Health status dictionary
        """
        try:
            # Try to read from news_articles collection
            query = self.db.collection('news_articles').limit(1)
            list(query.stream())

            return {
                'status': 'healthy',
                'database': 'aviation-intelligence',
                'collections': ['news_articles', 'insights']
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

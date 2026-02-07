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
        keywords: Optional[List[str]] = None,
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
            keywords: Filter by keywords in title or summary (case-insensitive)
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

                # Client-side keyword filtering (case-insensitive search in title and summary)
                if keywords:
                    title = article_data.get('title', '').lower()
                    summary = article_data.get('summary', '').lower()
                    combined_text = f"{title} {summary}"

                    # Check if any keyword appears in title or summary
                    if not any(keyword.lower() in combined_text for keyword in keywords):
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

    def update_article(self, article_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an article's fields in Firestore

        Args:
            article_id: Document ID of the article to update
            updates: Dictionary of fields to update

        Returns:
            True if update successful, False otherwise
        """
        try:
            doc_ref = self.db.collection('news_articles').document(article_id)
            doc_ref.update(updates)
            self.logger.debug(f"Updated article {article_id}: {list(updates.keys())}")
            return True

        except Exception as e:
            self.logger.error(f"Error updating article {article_id}: {e}")
            return False

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

    # ========== TSA PASSENGER DATA ==========

    def save_tsa_data(self, tsa_data: Dict[str, Any]) -> Optional[str]:
        """
        Save TSA passenger throughput data to Firestore

        Args:
            tsa_data: Dictionary containing TSA data fields
                - date: str (YYYY-MM-DD format)
                - current_throughput: int
                - compared_to_2019: float
                - source: str
                - data_quality: str
                - trend_analysis: str

        Returns:
            Document ID if successfully saved, None if duplicate or error
        """
        try:
            # Validate required fields
            if 'date' not in tsa_data or 'current_throughput' not in tsa_data:
                raise ValueError("Missing required fields: date or current_throughput")

            # Use date as document ID for deduplication (only one reading per day)
            date_str = tsa_data['date']
            doc_id = date_str.replace('-', '')  # e.g., "20260131"

            # Check if data for this date already exists
            doc_ref = self.db.collection('tsa_data').document(doc_id)
            existing_doc = doc_ref.get()

            if existing_doc.exists:
                # Update existing record only if it's better quality data
                existing_data = existing_doc.to_dict()
                existing_quality = existing_data.get('data_quality', 'unknown')
                new_quality = tsa_data.get('data_quality', 'unknown')

                # Priority: live_scrape > model_fallback > basic_fallback
                quality_priority = {'live_scrape': 3, 'model_fallback': 2, 'basic_fallback': 1, 'unknown': 0}

                if quality_priority.get(new_quality, 0) <= quality_priority.get(existing_quality, 0):
                    self.logger.debug(f"TSA data for {date_str} already exists with equal/better quality")
                    return None

            # Add ingestion timestamp
            tsa_data['ingested_at'] = datetime.now()

            # Save to Firestore
            doc_ref.set(tsa_data)

            self.logger.info(f"Saved TSA data: {date_str} - {tsa_data['current_throughput']:,} passengers")
            return doc_id

        except Exception as e:
            self.logger.error(f"Error saving TSA data: {e}")
            return None

    def get_tsa_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Query TSA passenger data with optional date filters

        Args:
            start_date: Filter data after this date
            end_date: Filter data before this date
            limit: Maximum number of records to return

        Returns:
            List of TSA data dictionaries
        """
        try:
            query = self.db.collection('tsa_data')

            # Apply date filters
            if start_date:
                query = query.where(filter=FieldFilter('date', '>=', start_date.strftime('%Y-%m-%d')))
            if end_date:
                query = query.where(filter=FieldFilter('date', '<=', end_date.strftime('%Y-%m-%d')))

            # Order by date (newest first)
            query = query.order_by('date', direction=firestore.Query.DESCENDING)
            query = query.limit(limit)

            # Execute query
            docs = query.stream()
            tsa_records = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id

                # Convert ingested_at timestamp if present
                if 'ingested_at' in data and hasattr(data['ingested_at'], 'timestamp'):
                    data['ingested_at'] = data['ingested_at'].replace(tzinfo=None)

                tsa_records.append(data)

            self.logger.info(f"Retrieved {len(tsa_records)} TSA records")
            return tsa_records

        except Exception as e:
            self.logger.error(f"Error querying TSA data: {e}")
            return []

    # ========== FRED ECONOMIC DATA ==========

    def save_fred_data(self, fred_data: Dict[str, Any]) -> Optional[str]:
        """
        Save FRED credit spread data to Firestore

        Args:
            fred_data: Dictionary containing FRED data fields
                - data_date: str (YYYY-MM-DD format)
                - credit_spread_bps: int
                - corporate_yield_pct: float
                - treasury_yield_pct: float
                - spread_description: str
                - risk_level: str
                - trend: str

        Returns:
            Document ID if successfully saved, None if duplicate or error
        """
        try:
            # Validate required fields
            if 'data_date' not in fred_data or 'credit_spread_bps' not in fred_data:
                raise ValueError("Missing required fields: data_date or credit_spread_bps")

            # Use date as document ID for deduplication
            date_str = fred_data['data_date']
            doc_id = date_str.replace('-', '')  # e.g., "20260131"

            # Check if data for this date already exists
            doc_ref = self.db.collection('fred_data').document(doc_id)
            if doc_ref.get().exists:
                self.logger.debug(f"FRED data for {date_str} already exists")
                return None

            # Add ingestion timestamp
            fred_data['ingested_at'] = datetime.now()

            # Save to Firestore
            doc_ref.set(fred_data)

            self.logger.info(f"Saved FRED data: {date_str} - {fred_data['credit_spread_bps']} bps spread")
            return doc_id

        except Exception as e:
            self.logger.error(f"Error saving FRED data: {e}")
            return None

    def get_fred_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Query FRED credit spread data with optional date filters

        Args:
            start_date: Filter data after this date
            end_date: Filter data before this date
            limit: Maximum number of records to return

        Returns:
            List of FRED data dictionaries
        """
        try:
            query = self.db.collection('fred_data')

            # Apply date filters
            if start_date:
                query = query.where(filter=FieldFilter('data_date', '>=', start_date.strftime('%Y-%m-%d')))
            if end_date:
                query = query.where(filter=FieldFilter('data_date', '<=', end_date.strftime('%Y-%m-%d')))

            # Order by date (newest first)
            query = query.order_by('data_date', direction=firestore.Query.DESCENDING)
            query = query.limit(limit)

            # Execute query
            docs = query.stream()
            fred_records = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id

                # Convert ingested_at timestamp if present
                if 'ingested_at' in data and hasattr(data['ingested_at'], 'timestamp'):
                    data['ingested_at'] = data['ingested_at'].replace(tzinfo=None)

                fred_records.append(data)

            self.logger.info(f"Retrieved {len(fred_records)} FRED records")
            return fred_records

        except Exception as e:
            self.logger.error(f"Error querying FRED data: {e}")
            return []

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

    # ========== AIRLINE REPORTS ==========

    def save_airline_report(self, report_data: Dict[str, Any]) -> Optional[str]:
        """
        Save airline or industry sector report to Firestore

        Args:
            report_data: Dictionary containing report fields
                - report_type: str ('airline' or 'sector')
                - subject: str (airline name or sector)
                - generated_at: datetime
                - period_start: datetime
                - period_end: datetime
                - markdown_content: str
                - html_content: str
                - sections: Dict[str, str]
                - metadata: Dict
                - cached_until: datetime

        Returns:
            Document ID if successful, None otherwise
        """
        try:
            # Add timestamp if not provided
            if 'generated_at' not in report_data:
                report_data['generated_at'] = datetime.now()

            # Save to Firestore (auto-generate ID)
            doc_ref = self.db.collection('airline_reports').document()
            doc_ref.set(report_data)

            self.logger.info(f"Saved {report_data.get('report_type')} report for {report_data.get('subject')} ({doc_ref.id})")
            return doc_ref.id

        except Exception as e:
            self.logger.error(f"Error saving airline report: {e}")
            return None

    def get_airline_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific airline report by ID

        Args:
            report_id: Document ID of the report

        Returns:
            Report dictionary or None if not found
        """
        try:
            doc_ref = self.db.collection('airline_reports').document(report_id)
            doc = doc_ref.get()

            if doc.exists:
                report_data = doc.to_dict()
                report_data['id'] = doc.id

                # Convert timestamps
                for field in ['generated_at', 'period_start', 'period_end', 'cached_until']:
                    if field in report_data and hasattr(report_data[field], 'timestamp'):
                        report_data[field] = report_data[field].replace(tzinfo=None)

                return report_data
            else:
                self.logger.info(f"Report {report_id} not found")
                return None

        except Exception as e:
            self.logger.error(f"Error fetching airline report: {e}")
            return None

    def get_airline_reports(
        self,
        subject: Optional[str] = None,
        report_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Query multiple airline reports with optional filtering

        Args:
            subject: Filter by airline name/sector (optional)
            report_type: Filter by report type ('airline' or 'sector') (optional)
            limit: Maximum number of reports to return
            offset: Number of reports to skip

        Returns:
            List of report dictionaries
        """
        try:
            query = self.db.collection('airline_reports')

            # Apply filters
            if subject:
                query = query.where(filter=FieldFilter('subject', '==', subject))

            if report_type:
                query = query.where(filter=FieldFilter('report_type', '==', report_type))

            # Order by generated date (newest first)
            query = query.order_by('generated_at', direction=firestore.Query.DESCENDING)

            # Apply pagination
            if offset > 0:
                query = query.offset(offset)
            query = query.limit(limit)

            # Execute query
            docs = query.stream()

            reports = []
            for doc in docs:
                report_data = doc.to_dict()
                report_data['id'] = doc.id

                # Convert timestamps
                for field in ['generated_at', 'period_start', 'period_end', 'cached_until']:
                    if field in report_data and hasattr(report_data[field], 'timestamp'):
                        report_data[field] = report_data[field].replace(tzinfo=None)

                reports.append(report_data)

            self.logger.info(f"Retrieved {len(reports)} airline reports")
            return reports

        except Exception as e:
            self.logger.error(f"Error querying airline reports: {e}")
            return []

    def get_cached_report(self, subject: str, report_type: str) -> Optional[Dict[str, Any]]:
        """
        Get a cached report for a subject if still valid

        Args:
            subject: Airline name or sector
            report_type: 'airline' or 'sector'

        Returns:
            Cached report dictionary or None if not found/expired
        """
        try:
            query = (self.db.collection('airline_reports')
                    .where(filter=FieldFilter('subject', '==', subject))
                    .where(filter=FieldFilter('report_type', '==', report_type))
                    .where(filter=FieldFilter('cached_until', '>', datetime.now()))
                    .order_by('generated_at', direction=firestore.Query.DESCENDING)
                    .limit(1))

            docs = list(query.stream())

            if docs:
                report_data = docs[0].to_dict()
                report_data['id'] = docs[0].id

                # Convert timestamps
                for field in ['generated_at', 'period_start', 'period_end', 'cached_until']:
                    if field in report_data and hasattr(report_data[field], 'timestamp'):
                        report_data[field] = report_data[field].replace(tzinfo=None)

                self.logger.info(f"Found cached {report_type} report for {subject}")
                return report_data
            else:
                self.logger.info(f"No cached {report_type} report found for {subject}")
                return None

        except Exception as e:
            self.logger.error(f"Error fetching cached report: {e}")
            return None

    # ========== WEEKLY NEWSLETTERS ==========

    def save_weekly_newsletter(self, newsletter_data: Dict[str, Any]) -> Optional[str]:
        """
        Save weekly newsletter to Firestore

        Args:
            newsletter_data: Dictionary containing newsletter fields
                - week_start: datetime
                - week_end: datetime
                - generated_at: datetime
                - markdown_content: str
                - html_content: str
                - sections: Dict[str, str]
                - articles_analyzed: int
                - previous_newsletter_id: Optional[str]
                - predictions_from_last_week: Optional[str]
                - metadata: Dict

        Returns:
            Document ID if successful, None otherwise
        """
        try:
            # Add timestamp if not provided
            if 'generated_at' not in newsletter_data:
                newsletter_data['generated_at'] = datetime.now()

            # Use week_start as document ID for deduplication (format: YYYY-MM-DD)
            week_start = newsletter_data['week_start']
            if isinstance(week_start, datetime):
                doc_id = week_start.strftime('%Y-%m-%d')
            else:
                doc_id = str(week_start)

            # Save to Firestore
            doc_ref = self.db.collection('weekly_newsletters').document(doc_id)
            doc_ref.set(newsletter_data)

            self.logger.info(f"Saved weekly newsletter for week of {doc_id}")
            return doc_id

        except Exception as e:
            self.logger.error(f"Error saving weekly newsletter: {e}")
            return None

    def get_newsletter(self, newsletter_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific newsletter by ID (date)

        Args:
            newsletter_id: Document ID (YYYY-MM-DD format)

        Returns:
            Newsletter dictionary or None if not found
        """
        try:
            doc_ref = self.db.collection('weekly_newsletters').document(newsletter_id)
            doc = doc_ref.get()

            if doc.exists:
                newsletter_data = doc.to_dict()
                newsletter_data['id'] = doc.id

                # Convert timestamps
                for field in ['week_start', 'week_end', 'generated_at']:
                    if field in newsletter_data and hasattr(newsletter_data[field], 'timestamp'):
                        newsletter_data[field] = newsletter_data[field].replace(tzinfo=None)

                return newsletter_data
            else:
                self.logger.info(f"Newsletter {newsletter_id} not found")
                return None

        except Exception as e:
            self.logger.error(f"Error fetching newsletter: {e}")
            return None

    def get_latest_newsletter(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent newsletter

        Returns:
            Newsletter dictionary or None if not found
        """
        try:
            query = (self.db.collection('weekly_newsletters')
                    .order_by('generated_at', direction=firestore.Query.DESCENDING)
                    .limit(1))

            docs = list(query.stream())

            if docs:
                newsletter_data = docs[0].to_dict()
                newsletter_data['id'] = docs[0].id

                # Convert timestamps
                for field in ['week_start', 'week_end', 'generated_at']:
                    if field in newsletter_data and hasattr(newsletter_data[field], 'timestamp'):
                        newsletter_data[field] = newsletter_data[field].replace(tzinfo=None)

                return newsletter_data
            else:
                self.logger.info("No newsletters found")
                return None

        except Exception as e:
            self.logger.error(f"Error fetching latest newsletter: {e}")
            return None

    def get_all_newsletters(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all newsletters, ordered by most recent first

        Args:
            limit: Optional limit on number of newsletters to return

        Returns:
            List of newsletter dictionaries
        """
        try:
            query = (self.db.collection('weekly_newsletters')
                    .order_by('generated_at', direction=firestore.Query.DESCENDING))

            if limit:
                query = query.limit(limit)

            docs = list(query.stream())

            newsletters = []
            for doc in docs:
                newsletter_data = doc.to_dict()
                newsletter_data['id'] = doc.id

                # Convert timestamps
                for field in ['week_start', 'week_end', 'generated_at']:
                    if field in newsletter_data and hasattr(newsletter_data[field], 'timestamp'):
                        newsletter_data[field] = newsletter_data[field].replace(tzinfo=None)

                newsletters.append(newsletter_data)

            self.logger.info(f"Retrieved {len(newsletters)} newsletters")
            return newsletters

        except Exception as e:
            self.logger.error(f"Error fetching all newsletters: {e}")
            return []

    # ========== CARRIER FINANCIALS ==========

    def save_carrier_financial(self, financial_data: Dict[str, Any]) -> Optional[str]:
        """
        Save carrier financial data to Firestore

        Args:
            financial_data: Dictionary containing carrier financial fields
                - carrier_code: str (e.g., 'UA', 'DL')
                - period: str (e.g., 'Q3-2025')
                - operating_revenue: float
                - etc.

        Returns:
            Document ID if successful, None otherwise
        """
        try:
            # Validate required fields
            required_fields = ['carrier_code', 'period']
            for field in required_fields:
                if field not in financial_data:
                    raise ValueError(f"Missing required field: {field}")

            # Use carrier_code + period as document ID
            import hashlib
            unique_key = f"{financial_data['carrier_code']}_{financial_data['period']}"
            doc_id = hashlib.md5(unique_key.encode()).hexdigest()

            # Add ingestion timestamp if not present
            if 'ingested_at' not in financial_data:
                financial_data['ingested_at'] = datetime.now().isoformat()

            # Save to Firestore
            doc_ref = self.db.collection('carrier_financials').document(doc_id)
            doc_ref.set(financial_data)

            self.logger.info(f"Saved carrier financials: {financial_data['carrier_code']} {financial_data['period']}")
            return doc_id

        except Exception as e:
            self.logger.error(f"Error saving carrier financial: {e}")
            return None

    def get_carrier_financial(self, carrier_code: str, period: str = None) -> Optional[Dict[str, Any]]:
        """
        Get financial data for a specific carrier

        Args:
            carrier_code: DOT carrier code (e.g., 'UA', 'DL')
            period: Optional specific period (e.g., 'Q3-2025'), gets latest if None

        Returns:
            Carrier financial dictionary or None if not found
        """
        try:
            if period:
                # Get specific period
                import hashlib
                unique_key = f"{carrier_code}_{period}"
                doc_id = hashlib.md5(unique_key.encode()).hexdigest()

                doc_ref = self.db.collection('carrier_financials').document(doc_id)
                doc = doc_ref.get()

                if doc.exists:
                    data = doc.to_dict()
                    data['id'] = doc.id
                    return data
                return None
            else:
                # Get latest for carrier
                query = (self.db.collection('carrier_financials')
                        .where(filter=FieldFilter('carrier_code', '==', carrier_code))
                        .order_by('period_end_date', direction=firestore.Query.DESCENDING)
                        .limit(1))

                docs = list(query.stream())

                if docs:
                    data = docs[0].to_dict()
                    data['id'] = docs[0].id
                    return data

                return None

        except Exception as e:
            self.logger.error(f"Error fetching carrier financial: {e}")
            return None

    def get_latest_carrier_financials(self, carrier_code: str, limit: int = 4) -> List[Dict[str, Any]]:
        """
        Get recent financial periods for a carrier (for trend analysis)

        Args:
            carrier_code: DOT carrier code (e.g., 'UA', 'DL')
            limit: Number of periods to return (default 4 quarters)

        Returns:
            List of carrier financial dictionaries
        """
        try:
            query = (self.db.collection('carrier_financials')
                    .where(filter=FieldFilter('carrier_code', '==', carrier_code))
                    .order_by('period_end_date', direction=firestore.Query.DESCENDING)
                    .limit(limit))

            docs = list(query.stream())
            results = []

            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)

            return results

        except Exception as e:
            self.logger.error(f"Error fetching carrier financials: {e}")
            return []

    def get_all_carrier_financials(self, period: str = None) -> List[Dict[str, Any]]:
        """
        Get financials for all carriers (optionally for a specific period)

        Args:
            period: Optional period filter (e.g., 'Q3-2025')

        Returns:
            List of carrier financial dictionaries
        """
        try:
            query = self.db.collection('carrier_financials')

            if period:
                query = query.where(filter=FieldFilter('period', '==', period))

            docs = list(query.stream())
            results = []

            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)

            self.logger.info(f"Retrieved {len(results)} carrier financials")
            return results

        except Exception as e:
            self.logger.error(f"Error fetching all carrier financials: {e}")
            return []

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
                'collections': ['news_articles', 'insights', 'tsa_data', 'fred_data', 'airline_reports', 'weekly_newsletters', 'carrier_financials']
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

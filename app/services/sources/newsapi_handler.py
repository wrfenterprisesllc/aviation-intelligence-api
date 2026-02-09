"""
NewsAPI Handler for Aviation News
Fetches aviation-related news from NewsAPI.org
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from newsapi import NewsApiClient

from app.models.news_article import NewsArticle
from .article_scraper import ArticleScraper
from app.utils.text_cleaner import strip_images_from_html
from app.utils.retry import with_retry

logger = logging.getLogger(__name__)

class NewsAPIHandler:
    """Handles fetching aviation news from NewsAPI.org"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize NewsAPI handler
        
        Args:
            api_key: NewsAPI.org API key (gets from env var if not provided)
        """
        self.api_key = api_key or os.environ.get('NEWSAPI_KEY')
        if not self.api_key:
            raise ValueError("NewsAPI key is required. Set NEWSAPI_KEY environment variable.")
        
        self.client = NewsApiClient(api_key=self.api_key)

        # Initialize article scraper for full content extraction
        self.scraper = ArticleScraper(timeout=60)

        # Aviation-related search queries
        self.search_queries = [
            'aircraft leasing',
            'airline fleet',
            'aviation finance', 
            'aircraft orders',
            'airline industry',
            'jet fuel prices',
            'aviation sustainability',
            'aircraft maintenance',
            'airline mergers',
            'aviation technology'
        ]
        
        # Domain preferences (high-quality aviation sources)
        self.preferred_domains = [
            'reuters.com',
            'bloomberg.com',
            'wsj.com',
            'ft.com',
            'flightglobal.com',
            'aviationweek.com',
            'simpleflying.com',
            'aerotimeanalysis.com',
            'ch-aviation.com'
        ]
    
    @with_retry(max_attempts=3, min_wait=2, max_wait=30)
    def fetch_articles(self,
                      days_back: int = 1,
                      max_articles: int = 100,
                      language: str = 'en') -> List[NewsArticle]:
        """
        Fetch aviation-related articles from NewsAPI
        
        Args:
            days_back: Number of days back to search
            max_articles: Maximum articles to fetch per query
            language: Language code for articles
            
        Returns:
            List of NewsArticle objects
        """
        logger.info("Fetching articles from NewsAPI")
        
        all_articles = []
        seen_urls = set()
        
        # Calculate date range
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days_back)
        
        try:
            # Search for each query term
            for query in self.search_queries:
                try:
                    logger.debug(f"Searching NewsAPI for: {query}")
                    
                    # Build query with preferred domains
                    domains_str = ','.join(self.preferred_domains)
                    
                    # Search everything endpoint
                    response = self.client.get_everything(
                        q=query,
                        domains=domains_str,
                        from_param=from_date.strftime('%Y-%m-%d'),
                        to=to_date.strftime('%Y-%m-%d'),
                        language=language,
                        sort_by='publishedAt',
                        page_size=min(max_articles, 100)  # NewsAPI max is 100
                    )
                    
                    if response.get('status') == 'ok':
                        articles = response.get('articles', [])
                        
                        for article_data in articles:
                            # Skip if we've already seen this URL
                            url = article_data.get('url', '')
                            if url in seen_urls:
                                continue
                            seen_urls.add(url)
                            
                            # Parse article
                            article = self._parse_newsapi_article(article_data, query)
                            if article:
                                all_articles.append(article)
                    
                    else:
                        logger.error(f"NewsAPI error for query '{query}': {response.get('message', 'Unknown error')}")
                
                except Exception as e:
                    logger.error(f"Error searching NewsAPI for '{query}': {e}")
                    continue
            
            logger.info(f"Fetched {len(all_articles)} unique articles from NewsAPI")
            return all_articles
            
        except Exception as e:
            logger.error(f"Critical error fetching from NewsAPI: {e}")
            return []
    
    def _parse_newsapi_article(self, article_data: Dict[str, Any], search_query: str) -> Optional[NewsArticle]:
        """
        Parse a NewsAPI article response into a NewsArticle object
        
        Args:
            article_data: Raw article data from NewsAPI
            search_query: The query term that found this article
            
        Returns:
            NewsArticle object or None if parsing fails
        """
        try:
            # Extract basic fields
            title = article_data.get('title', '').strip()
            if not title or title.lower() == '[removed]':
                return None
            
            url = article_data.get('url', '').strip()
            if not url:
                return None
            
            # Extract content
            description = article_data.get('description', '') or ''
            content = article_data.get('content', '') or ''
            
            # Use description as summary, content as full text
            summary = description[:1000] if description else ''
            
            # If content is available and longer than description, use it
            if content and len(content) > len(description):
                # NewsAPI often truncates content with [+X chars] notation
                is_truncated = '[+' in content and 'chars]' in content
                if is_truncated:
                    # Content is truncated, use description for both
                    full_content = description
                else:
                    full_content = content
            else:
                full_content = description
                is_truncated = True  # Assume truncated if only description available

            # Attempt to scrape full content if NewsAPI content is truncated
            if is_truncated and url:
                logger.info(f"🔍 NewsAPI content truncated for: {title[:60]}...")
                scraped_content = self.scraper.fetch_full_content(url)

                if scraped_content:
                    full_content = scraped_content
                    logger.info(f"✅ Replaced NewsAPI excerpt with {len(full_content)} chars")
                else:
                    logger.info(f"⚠️  Scraping failed, keeping NewsAPI content")

            # Parse publication date
            published_str = article_data.get('publishedAt', '')
            try:
                published_at = datetime.fromisoformat(published_str.replace('Z', '+00:00')).replace(tzinfo=None)
            except:
                published_at = datetime.utcnow()
            
            # Build tags based on search query and source
            tags = [search_query.replace(' ', '_')]
            
            # Add source-specific tags
            source_name = article_data.get('source', {}).get('name', '').lower()
            if 'aviation' in source_name or 'flight' in source_name:
                tags.append('aviation_industry')
            if 'bloomberg' in source_name or 'reuters' in source_name:
                tags.append('financial_news')
            
            # Extract entities from author info
            author = article_data.get('author', '') or ''

            # Clean images from content and summary
            full_content = strip_images_from_html(full_content) if full_content else full_content
            summary = strip_images_from_html(summary) if summary else summary

            # Build raw payload (removed urlToImage)
            raw_payload = {
                'newsapi_source': article_data.get('source', {}),
                'author': author,
                'search_query': search_query,
                'api_response': article_data
            }

            # Create NewsArticle
            article = NewsArticle(
                source='newsapi',
                source_url=url,
                title=title,
                summary=summary,
                content=full_content,
                published_at=published_at,
                ingested_at=datetime.utcnow(),
                tags=tags,
                entities=self._extract_entities(article_data),
                raw_payload=raw_payload
            )
            
            return article
            
        except Exception as e:
            logger.error(f"Error parsing NewsAPI article: {e}")
            return None
    
    def _extract_entities(self, article_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract basic entities from NewsAPI article data
        
        Args:
            article_data: Raw NewsAPI article data
            
        Returns:
            List of entity dictionaries
        """
        entities = []
        
        # Extract source as an entity
        source_info = article_data.get('source', {})
        if source_info.get('name'):
            entities.append({
                'type': 'news_source',
                'name': source_info['name'],
                'id': source_info.get('id', ''),
                'confidence': 1.0
            })
        
        # Extract author as an entity if present
        author = article_data.get('author', '')
        if author and author.lower() not in ['unknown', 'staff', 'editor']:
            entities.append({
                'type': 'author',
                'name': author,
                'confidence': 1.0
            })
        
        return entities
    
    def get_sources(self, category: str = 'business', country: str = 'us') -> List[Dict[str, Any]]:
        """
        Get available news sources from NewsAPI
        
        Args:
            category: News category to filter
            country: Country code to filter
            
        Returns:
            List of source information dictionaries
        """
        try:
            response = self.client.get_sources(
                category=category,
                country=country,
                language='en'
            )
            
            if response.get('status') == 'ok':
                return response.get('sources', [])
            else:
                logger.error(f"Error getting NewsAPI sources: {response.get('message')}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching NewsAPI sources: {e}")
            return []
    
    def test_api_connection(self) -> Dict[str, Any]:
        """
        Test the NewsAPI connection and return account info
        
        Returns:
            Dictionary with API status and account information
        """
        try:
            # Test with a simple query
            response = self.client.get_everything(
                q='aviation',
                page_size=1,
                sort_by='publishedAt'
            )
            
            if response.get('status') == 'ok':
                return {
                    'success': True,
                    'total_results': response.get('totalResults', 0),
                    'api_key_valid': True,
                    'message': 'NewsAPI connection successful'
                }
            else:
                return {
                    'success': False,
                    'error': response.get('message', 'Unknown error'),
                    'api_key_valid': False
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'api_key_valid': False
            }
    
    def search_aviation_keywords(self, 
                                custom_queries: Optional[List[str]] = None,
                                days_back: int = 7) -> Dict[str, int]:
        """
        Search for specific aviation keywords and return result counts
        
        Args:
            custom_queries: Optional custom search queries
            days_back: Number of days to search
            
        Returns:
            Dictionary mapping queries to result counts
        """
        queries = custom_queries or self.search_queries
        results = {}
        
        # Calculate date range
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days_back)
        
        for query in queries:
            try:
                response = self.client.get_everything(
                    q=query,
                    from_param=from_date.strftime('%Y-%m-%d'),
                    to=to_date.strftime('%Y-%m-%d'),
                    language='en',
                    page_size=1  # We only want the count
                )
                
                if response.get('status') == 'ok':
                    results[query] = response.get('totalResults', 0)
                else:
                    results[query] = 0
                    
            except Exception as e:
                logger.error(f"Error searching for '{query}': {e}")
                results[query] = 0
        
        return results
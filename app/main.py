#!/usr/bin/env python3
"""
Aviation Intelligence API - Live Data Integration with Monitoring
"""

import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from app.utils.auth import require_api_key

app = Flask(__name__)
CORS(app, expose_headers=['X-API-Key'], allow_headers=['Content-Type', 'X-API-Key'])

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import services - ORDER MATTERS (db_service must be initialized first)
try:
    from app.services.database_service import DatabaseService
    db_service = DatabaseService()
    logger.info("✅ Database service initialized")
except Exception as e:
    logger.warning(f"⚠️ Database service initialization failed: {e}")
    db_service = None

try:
    from app.services.fred_service import FREDCreditSpreadsFinal
    fred_service = FREDCreditSpreadsFinal(db_service=db_service)
    logger.info("✅ FRED service initialized with database persistence")
except Exception as e:
    logger.warning(f"⚠️ FRED service initialization failed: {e}")
    fred_service = None

try:
    from app.services.tsa_service import TSADataService
    tsa_service = TSADataService(db_service=db_service)
    logger.info("✅ TSA service initialized with database persistence")
except Exception as e:
    logger.warning(f"⚠️ TSA service initialization failed: {e}")
    tsa_service = None

try:
    from app.services.monitoring_service import MonitoringService
    monitor = MonitoringService()
    logger.info("✅ Monitoring service initialized")
except Exception as e:
    logger.warning(f"⚠️ Monitoring service initialization failed: {e}")
    monitor = None

try:
    from app.services.news_ingestion import NewsIngestionService
    news_service = NewsIngestionService()
    logger.info("✅ News ingestion service initialized")
except Exception as e:
    logger.warning(f"⚠️ News ingestion service initialization failed: {e}")
    news_service = None

try:
    from app.services.gemini_service import GeminiService
    from app.services.insights_service import InsightsService
    from app.services.stock_data_service import StockDataService
    from app.services.sec_filings_service import SECFilingsService
    from app.services.bts_service import BTSService
    from app.services.financial_data_service import FinancialDataService

    gemini_service = GeminiService()
    stock_service = StockDataService()
    sec_service = SECFilingsService()
    bts_service = BTSService(db_service=db_service)
    financial_service = FinancialDataService(bts_service=bts_service)

    insights_service = InsightsService(
        gemini_service=gemini_service,
        database_service=db_service,
        stock_service=stock_service,
        sec_service=sec_service,
        bts_service=bts_service,
        financial_service=financial_service,
        fred_service=fred_service
    )
    logger.info("✅ Gemini, Stock, SEC, BTS, Financial, FRED, and Insights services initialized")
except Exception as e:
    logger.warning(f"⚠️ Gemini/Insights service initialization failed: {e}")
    gemini_service = None
    insights_service = None
    stock_service = None
    sec_service = None
    bts_service = None
    financial_service = None

@app.before_request
def before_request():
    """Record request start time for monitoring"""
    if monitor:
        request.start_time = datetime.now()

@app.after_request
def after_request(response):
    """Record request metrics for monitoring"""
    if monitor and hasattr(request, 'start_time'):
        response_time = (datetime.now() - request.start_time).total_seconds() * 1000
        monitor.record_request(request.path, response.status_code, response_time)
    return response

@app.route('/')
def root():
    return jsonify({
        'service': 'Aviation Intelligence API',
        'status': 'operational',
        'version': '2.1.0',
        'features': {
            'live_fred_data': fred_service is not None,
            'live_tsa_data': tsa_service is not None,
            'monitoring': 'enhanced' if monitor else 'basic',
            'news_ingestion': news_service is not None,
            'firestore_database': db_service is not None,
            'ai_insights': insights_service is not None
        },
        'endpoints': [
            '/health',
            '/api/status',
            '/api/credit-spread/current',
            '/api/tsa/current',
            '/api/monitoring/health',
            '/api/monitoring/metrics',
            '/api/news/ingest',
            '/api/news/articles',
            '/api/news/<article_id>',
            '/api/news/stats',
            '/api/tsa/historical',
            '/api/credit-spread/historical',
            '/api/reports/generate',
            '/api/reports/<id>',
            '/api/reports',
            '/api/newsletter/generate',
            '/api/newsletter/latest',
            '/api/newsletter/<id>'
        ]
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'aviation-intelligence-api',
        'timestamp': datetime.now().isoformat(),
        'platform': 'Google Cloud Run',
        'integrations': {
            'fred_service': 'active' if fred_service else 'fallback',
            'tsa_service': 'active' if tsa_service else 'fallback',
            'monitoring': 'active' if monitor else 'disabled',
            'news_service': 'active' if news_service else 'disabled',
            'database_service': 'active' if db_service else 'disabled'
        }
    })

@app.route('/api/status')
def api_status():
    return jsonify({
        'status': 'operational',
        'service': 'Aviation Intelligence API',
        'platform': 'Google Cloud Run',
        'timestamp': datetime.now().isoformat(),
        'data_sources': {
            'fred': 'Federal Reserve Economic Data - Live API',
            'tsa': 'TSA Checkpoint Data - Live Scraping + Enhanced Modeling',
            'eia': 'Energy Information Administration - Coming Soon'
        },
        'integrations': {
            'fred_service': 'active' if fred_service else 'fallback',
            'tsa_service': 'active' if tsa_service else 'fallback',
            'monitoring': 'active' if monitor else 'disabled',
            'news_service': 'active' if news_service else 'disabled',
            'database_service': 'active' if db_service else 'disabled',
            'live_data': True
        }
    })

@app.route('/api/credit-spread/current')
def get_credit_spread():
    """Federal Reserve credit spread data - LIVE INTEGRATION with MONITORING"""
    start_time = datetime.now()
    
    try:
        if fred_service:
            # Get live FRED data
            fred_data = fred_service.get_real_credit_spreads()
            
            if fred_data and fred_data.get('success'):
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                # Record monitoring metrics
                if monitor:
                    monitor.record_fred_call(True, response_time)
                
                logger.info(f"📊 Served live FRED data in {response_time:.1f}ms")
                
                return jsonify({
                    'success': True,
                    'data': fred_data['data'],
                    'source': 'Federal Reserve Economic Data (FRED) - Live API',
                    'timestamp': datetime.now().isoformat(),
                    'response_time_ms': round(response_time, 1),
                    'data_quality': 'live_feed'
                })
            else:
                # FRED call failed
                if monitor:
                    monitor.record_fred_call(False)
        
        # Fallback to enhanced mock data
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"📊 Served fallback credit spread data in {response_time:.1f}ms")
        
        return jsonify({
            'success': True,
            'data': {
                'credit_spread_bps': 79,
                'spread_description': 'Very Tight - Low credit risk',
                'corporate_yield_pct': 5.01,
                'treasury_yield_pct': 4.22,
                'last_updated': datetime.now().isoformat(),
                'risk_level': 'low',
                'trend': 'tightening',
                'note': 'Fallback data - FRED service unavailable'
            },
            'source': 'Enhanced Fallback (FRED integration attempted)',
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1),
            'data_quality': 'fallback'
        })
        
    except Exception as e:
        if monitor:
            monitor.record_fred_call(False)
        logger.error(f"❌ Error in credit spread endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'Failed to fetch credit spread data',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/tsa/current')
def get_tsa_data():
    """TSA passenger data - LIVE SCRAPING + ENHANCED MODELING with MONITORING"""
    start_time = datetime.now()
    
    try:
        if tsa_service:
            # Get live TSA data
            tsa_data = tsa_service.get_real_tsa_data()
            
            if tsa_data and tsa_data.get('success'):
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                data_quality = tsa_data['data'].get('data_quality', 'unknown')
                success = data_quality in ['live_scrape', 'model_fallback']
                
                # Record monitoring metrics
                if monitor:
                    monitor.record_tsa_call(success, data_quality)
                
                if data_quality == 'live_scrape':
                    logger.info(f"🛂 Served live TSA scraped data in {response_time:.1f}ms")
                else:
                    logger.info(f"🛂 Served enhanced TSA modeled data in {response_time:.1f}ms")
                
                return jsonify({
                    'success': True,
                    'data': tsa_data['data'],
                    'timestamp': datetime.now().isoformat(),
                    'response_time_ms': round(response_time, 1)
                })
            else:
                if monitor:
                    monitor.record_tsa_call(False)
        
        # Basic fallback
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"🛂 Served basic TSA fallback data in {response_time:.1f}ms")
        
        return jsonify({
            'success': True,
            'data': {
                'current_throughput': 2100000,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'compared_to_2019': 95.2,
                'source': 'Basic Fallback',
                'note': 'TSA service unavailable'
            },
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1),
            'data_quality': 'basic_fallback'
        })
        
    except Exception as e:
        if monitor:
            monitor.record_tsa_call(False)
        logger.error(f"❌ Error in TSA endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'Failed to fetch TSA data',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/market-data')
def get_market_data():
    """
    Get comprehensive market data including fuel prices
    Returns live or fallback fuel price data
    """
    start_time = datetime.now()

    try:
        # For now, provide realistic fuel price data with variation
        # In the future, this could integrate with real fuel price APIs
        import random
        base_price = 2.18
        # Add small random variation (+/- 5%)
        price_variation = random.uniform(-0.11, 0.11)
        current_price = round(base_price + price_variation, 2)

        # Weekly change (simulated for now)
        weekly_change = round(random.uniform(-5.0, 5.0), 1)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"⛽ Served market data (fuel: ${current_price}/gal) in {response_time:.1f}ms")

        return jsonify({
            'status': 'success',
            'data': {
                'fuel_data': {
                    'jet_fuel': {
                        'price_per_gallon': current_price,
                        'weekly_change': {
                            'percent': weekly_change
                        },
                        'last_updated': datetime.now().strftime('%Y-%m-%d'),
                        'source': 'Market estimate (live API integration pending)'
                    }
                }
            },
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in market data endpoint: {e}")
        return jsonify({
            'status': 'error',
            'error': 'Internal server error',
            'message': 'Failed to fetch market data',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/monitoring/health')
def monitoring_health():
    """Detailed health check for monitoring"""
    if monitor:
        health_data = monitor.get_health_status()
        return jsonify(health_data)
    else:
        return jsonify({
            'overall': 'degraded',
            'message': 'Monitoring service unavailable',
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/monitoring/metrics')
def monitoring_metrics():
    """Metrics summary for dashboards"""
    if monitor:
        metrics_data = monitor.get_metrics_summary()
        return jsonify({
            'service': 'aviation-intelligence-api',
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics_data
        })
    else:
        return jsonify({
            'service': 'aviation-intelligence-api',
            'timestamp': datetime.now().isoformat(),
            'message': 'Monitoring unavailable'
        })

# ========== NEWS INGESTION ENDPOINTS ==========

@app.route('/api/news/ingest', methods=['POST'])
@require_api_key
def ingest_news():
    """
    Trigger news ingestion from all sources
    Requires admin authentication (to be added in Phase 6)

    Request body:
    {
        "source_types": ["rss", "newsapi", "sec_edgar"]  // optional, defaults to all
    }
    """
    start_time = datetime.now()

    try:
        if not news_service:
            return jsonify({
                'success': False,
                'error': 'News ingestion service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Get request parameters
        data = request.get_json() or {}
        source_types = data.get('source_types', None)

        # Run ingestion
        logger.info(f"📰 Starting news ingestion (source_types={source_types})")
        stats = news_service.ingest_all_sources(source_types=source_types)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"📰 News ingestion completed in {response_time:.1f}ms - {stats['articles_saved']} articles saved")

        return jsonify({
            'success': True,
            'stats': {
                'articles_processed': stats['articles_processed'],
                'articles_saved': stats['articles_saved'],
                'articles_skipped': stats['articles_skipped'],
                'sources_processed': stats['sources_processed'],
                'errors': stats['errors'],
                'duration_seconds': stats.get('duration_seconds', 0)
            },
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in news ingestion endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/news/articles', methods=['GET'])
def get_articles():
    """
    Get news articles with optional filters

    Query parameters:
    - source: Filter by source (e.g., 'newsapi', 'flightglobal_rss', 'sec_edgar')
    - tags: Comma-separated list of tags
    - keywords: Search in title/summary (case-insensitive)
    - start_date: ISO format date (YYYY-MM-DD)
    - end_date: ISO format date (YYYY-MM-DD)
    - limit: Maximum number of articles (default 50)
    - offset: Number of articles to skip (default 0)
    """
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Parse query parameters
        source = request.args.get('source', None)
        tags_str = request.args.get('tags', None)
        tags = tags_str.split(',') if tags_str else None
        keywords = request.args.get('keywords', None)
        start_date_str = request.args.get('start_date', None)
        end_date_str = request.args.get('end_date', None)
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        # Parse dates if provided
        start_date = None
        end_date = None
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str)
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str)

        # Get articles from database
        articles = db_service.get_articles(
            source=source,
            tags=tags,
            keywords=keywords,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"📰 Retrieved {len(articles)} articles in {response_time:.1f}ms")

        return jsonify({
            'success': True,
            'count': len(articles),
            'articles': articles,
            'filters': {
                'source': source,
                'tags': tags,
                'start_date': start_date_str,
                'end_date': end_date_str,
                'limit': limit,
                'offset': offset
            },
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in get articles endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/news/<article_id>', methods=['GET'])
def get_single_article(article_id):
    """
    Get a single article by ID

    GET /api/news/<article_id>

    Returns:
        200: Article found with full details
        404: Article not found
        500: Server error
    """
    try:
        start_time = datetime.now()

        logger.info(f"📄 Fetching article: {article_id}")

        # Get article from database service
        article = db_service.get_article_by_id(article_id)

        if not article:
            logger.warning(f"⚠️  Article not found: {article_id}")
            return jsonify({
                'success': False,
                'error': 'Article not found',
                'article_id': article_id,
                'timestamp': datetime.now().isoformat()
            }), 404

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"✅ Article fetched successfully: {article_id} ({response_time:.1f}ms)")

        return jsonify({
            'success': True,
            'article': article,
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 2)
        })

    except Exception as e:
        logger.error(f"❌ Error fetching article {article_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/news/enhance/<article_id>', methods=['POST'])
@require_api_key
def enhance_article(article_id):
    """
    Enhance a news article with AI-generated summary and impact statement

    POST /api/news/enhance/<article_id>

    Returns:
        Enhanced article with ai_summary and impact_statement fields
    """
    try:
        # Fetch article from database
        article = db_service.get_article_by_id(article_id)

        if not article:
            return jsonify({
                'success': False,
                'error': 'Article not found'
            }), 404

        # Check if already enhanced
        if article.get('ai_summary') and article.get('impact_statement'):
            logger.info(f"Article {article_id} already enhanced")
            return jsonify({
                'success': True,
                'article': article,
                'message': 'Article already enhanced'
            })

        # Initialize enhancement service
        from app.services.gemini_service import GeminiService
        from app.services.article_enhancement_service import ArticleEnhancementService

        gemini = GeminiService()
        enhancer = ArticleEnhancementService(gemini)

        # Enhance article
        enhanced = enhancer.enhance_article(article)

        # Update in database
        db_service.db.collection('news_articles').document(article_id).update({
            'ai_summary': enhanced.get('ai_summary'),
            'impact_statement': enhanced.get('impact_statement')
        })

        logger.info(f"✅ Article {article_id} enhanced successfully")

        return jsonify({
            'success': True,
            'article': enhanced,
            'enhancements': {
                'ai_summary_length': len(enhanced.get('ai_summary', '')),
                'has_impact_statement': bool(enhanced.get('impact_statement'))
            }
        })

    except Exception as e:
        logger.error(f"❌ Article enhancement failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/news/enhance-batch', methods=['POST'])
@require_api_key
def enhance_articles_batch():
    """
    Enhance multiple articles with AI summaries and impact statements

    POST /api/news/enhance-batch
    Body: { "limit": 10, "tags": ["aviation", "airline_news"] }

    Returns:
        Status of batch enhancement operation
    """
    try:
        data = request.get_json() or {}
        limit = data.get('limit', 10)
        tags = data.get('tags')

        # Fetch articles without AI enhancements
        articles = db_service.get_articles(tags=tags, limit=limit)

        # Filter articles that need enhancement
        to_enhance = [
            a for a in articles
            if not a.get('ai_summary') or not a.get('impact_statement')
        ]

        logger.info(f"Found {len(to_enhance)} articles to enhance")

        # Initialize services
        from app.services.gemini_service import GeminiService
        from app.services.article_enhancement_service import ArticleEnhancementService

        gemini = GeminiService()
        enhancer = ArticleEnhancementService(gemini)

        # Enhance each article
        enhanced_count = 0
        for article in to_enhance:
            try:
                enhanced = enhancer.enhance_article(article)

                # Update in database
                db_service.db.collection('news_articles').document(article['id']).update({
                    'ai_summary': enhanced.get('ai_summary'),
                    'impact_statement': enhanced.get('impact_statement')
                })

                enhanced_count += 1

            except Exception as e:
                logger.warning(f"Failed to enhance article {article.get('id')}: {e}")
                continue

        return jsonify({
            'success': True,
            'total_articles': len(articles),
            'enhanced_count': enhanced_count,
            'already_enhanced': len(articles) - len(to_enhance)
        })

    except Exception as e:
        logger.error(f"❌ Batch enhancement failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/news/clean-html', methods=['POST'])
@require_api_key
def clean_article_html():
    """
    Clean HTML markup from article content and summaries
    This is a one-time cleanup operation for existing articles
    """
    start_time = datetime.now()

    try:
        from bs4 import BeautifulSoup
        import html as html_module
        import re

        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available'
            }), 503

        # Get limit from request (default 100)
        data = request.get_json() or {}
        limit = data.get('limit', 100)

        logger.info(f"🧹 Starting HTML cleanup for up to {limit} articles...")

        # Get all articles
        articles = db_service.get_articles(limit=limit)

        stats = {
            'total': len(articles),
            'cleaned': 0,
            'skipped': 0,
            'errors': 0
        }

        # HTML cleaning function
        def clean_html(html_content):
            if not html_content or ('<' not in html_content and '&' not in html_content):
                return html_content

            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                for script in soup(["script", "style", "iframe", "noscript"]):
                    script.decompose()
                text = soup.get_text()
                text = html_module.unescape(text)
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                text = re.sub(r'\s+', ' ', text)
                return text.strip()
            except:
                clean_text = re.sub(r'<[^>]+>', '', html_content)
                clean_text = html_module.unescape(clean_text)
                clean_text = re.sub(r'\s+', ' ', clean_text)
                return clean_text.strip()

        # Process each article
        for article in articles:
            try:
                article_id = article.get('id')
                needs_update = False
                updated_fields = {}

                # Check content
                content = article.get('content', '')
                if content and ('<' in content or '&' in content):
                    cleaned = clean_html(content)
                    if cleaned != content:
                        updated_fields['content'] = cleaned
                        needs_update = True

                # Check summary
                summary = article.get('summary', '')
                if summary and ('<' in summary or '&' in summary):
                    cleaned = clean_html(summary)
                    if cleaned != summary:
                        updated_fields['summary'] = cleaned
                        needs_update = True

                if needs_update:
                    db_service.update_article(article_id, updated_fields)
                    stats['cleaned'] += 1
                    logger.debug(f"✓ Cleaned article {article_id}: {list(updated_fields.keys())}")
                else:
                    stats['skipped'] += 1

            except Exception as e:
                stats['errors'] += 1
                logger.error(f"✗ Error cleaning article: {e}")

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"🧹 HTML cleanup complete: {stats['cleaned']} cleaned, {stats['skipped']} skipped, {stats['errors']} errors")

        return jsonify({
            'success': True,
            'stats': stats,
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ HTML cleanup failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/news/stats', methods=['GET'])
def get_news_stats():
    """Get statistics about articles in the database"""
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Get stats from database
        stats = db_service.get_article_stats()

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"📰 Retrieved article stats in {response_time:.1f}ms")

        return jsonify({
            'success': True,
            'stats': stats,
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in news stats endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/news/remove-images', methods=['POST'])
def remove_images_from_articles():
    """
    Remove images from all existing articles in Firestore

    This endpoint cleans up existing articles by:
    - Removing <img> tags from content and summary fields
    - Removing urlToImage from raw_payload

    Returns:
        JSON with success status and count of updated articles
    """
    start_time = datetime.now()

    try:
        from app.utils.text_cleaner import strip_images_from_html

        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        logger.info("🧹 Starting image cleanup for all articles...")

        # Get all articles from Firestore
        articles_ref = db_service.db.collection('news_articles')
        docs = articles_ref.stream()

        updated_count = 0
        error_count = 0

        for doc in docs:
            try:
                article_data = doc.to_dict()
                article_id = doc.id

                updates = {}

                # Clean content field
                if 'content' in article_data and article_data['content']:
                    cleaned_content = strip_images_from_html(article_data['content'])
                    if cleaned_content != article_data['content']:
                        updates['content'] = cleaned_content

                # Clean summary field
                if 'summary' in article_data and article_data['summary']:
                    cleaned_summary = strip_images_from_html(article_data['summary'])
                    if cleaned_summary != article_data['summary']:
                        updates['summary'] = cleaned_summary

                # Remove urlToImage from raw_payload
                if 'raw_payload' in article_data:
                    raw_payload = article_data['raw_payload']
                    if isinstance(raw_payload, dict) and 'urlToImage' in raw_payload:
                        del raw_payload['urlToImage']
                        updates['raw_payload'] = raw_payload

                # Update document if there are changes
                if updates:
                    doc.reference.update(updates)
                    updated_count += 1

                    if updated_count % 10 == 0:
                        logger.info(f"✅ Cleaned {updated_count} articles so far...")

            except Exception as e:
                logger.error(f"❌ Error cleaning article {doc.id}: {e}")
                error_count += 1

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"🧹 Image cleanup complete: {updated_count} updated, {error_count} errors in {response_time:.1f}ms")

        return jsonify({
            'success': True,
            'updated': updated_count,
            'errors': error_count,
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in image cleanup endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ========== TSA HISTORICAL DATA ENDPOINTS ==========

@app.route('/api/tsa/historical', methods=['GET'])
def get_tsa_historical():
    """
    Get historical TSA passenger throughput data

    Query parameters:
    - start_date: ISO format date (YYYY-MM-DD)
    - end_date: ISO format date (YYYY-MM-DD)
    - limit: Maximum number of records (default 30)
    """
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Parse query parameters
        start_date_str = request.args.get('start_date', None)
        end_date_str = request.args.get('end_date', None)
        limit = int(request.args.get('limit', 30))

        # Parse dates if provided
        start_date = None
        end_date = None
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str)
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str)

        # Get TSA data from database
        tsa_records = db_service.get_tsa_data(
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"🛂 Retrieved {len(tsa_records)} TSA records in {response_time:.1f}ms")

        return jsonify({
            'success': True,
            'count': len(tsa_records),
            'data': tsa_records,
            'filters': {
                'start_date': start_date_str,
                'end_date': end_date_str,
                'limit': limit
            },
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in TSA historical endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ========== FRED HISTORICAL DATA ENDPOINTS ==========

@app.route('/api/credit-spread/historical', methods=['GET'])
def get_fred_historical():
    """
    Get historical FRED credit spread data

    Query parameters:
    - start_date: ISO format date (YYYY-MM-DD)
    - end_date: ISO format date (YYYY-MM-DD)
    - limit: Maximum number of records (default 30)
    """
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Parse query parameters
        start_date_str = request.args.get('start_date', None)
        end_date_str = request.args.get('end_date', None)
        limit = int(request.args.get('limit', 30))

        # Parse dates if provided
        start_date = None
        end_date = None
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str)
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str)

        # Get FRED data from database
        fred_records = db_service.get_fred_data(
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"📊 Retrieved {len(fred_records)} FRED records in {response_time:.1f}ms")

        return jsonify({
            'success': True,
            'count': len(fred_records),
            'data': fred_records,
            'filters': {
                'start_date': start_date_str,
                'end_date': end_date_str,
                'limit': limit
            },
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in FRED historical endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ========== AI INSIGHTS ENDPOINTS ==========

@app.route('/api/reports/generate', methods=['POST'])
@require_api_key
def generate_report():
    """
    Generate an airline or industry sector report using AI

    Request body:
    {
        "subject": "Delta Air Lines" or "Aircraft Leasing",
        "report_type": "airline" or "sector",
        "days": 30 (optional, default 30)
    }
    """
    start_time = datetime.now()

    try:
        if not insights_service:
            return jsonify({
                'success': False,
                'error': 'AI insights service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required',
                'timestamp': datetime.now().isoformat()
            }), 400

        subject = data.get('subject')
        report_type = data.get('report_type', 'airline')
        days = data.get('days', 30)

        if not subject:
            return jsonify({
                'success': False,
                'error': 'Subject is required',
                'timestamp': datetime.now().isoformat()
            }), 400

        VALID_REPORT_TYPES = ['airline', 'sector', 'credit_analysis', 'leasing_recommendation', 'comprehensive']
        if report_type not in VALID_REPORT_TYPES:
            return jsonify({
                'success': False,
                'error': f'report_type must be one of: {", ".join(VALID_REPORT_TYPES)}',
                'timestamp': datetime.now().isoformat()
            }), 400

        # Generate report
        logger.info(f"📊 Generating {report_type} report for: {subject}")
        report = insights_service.generate_airline_report(
            subject=subject,
            report_type=report_type,
            days=days
        )

        if not report:
            return jsonify({
                'success': False,
                'error': 'Failed to generate report',
                'timestamp': datetime.now().isoformat()
            }), 500

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"✅ Report generated in {response_time:.1f}ms")

        return jsonify({
            'success': True,
            'report': {
                'id': report['id'],
                'report_type': report['report_type'],
                'subject': report['subject'],
                'generated_at': report['generated_at'].isoformat() if isinstance(report['generated_at'], datetime) else report['generated_at'],
                'period_start': report['period_start'].isoformat() if isinstance(report['period_start'], datetime) else report['period_start'],
                'period_end': report['period_end'].isoformat() if isinstance(report['period_end'], datetime) else report['period_end'],
                'markdown_content': report['markdown_content'],
                'html_content': report['html_content'],
                'sections': report['sections'],
                'metadata': report['metadata'],
                'cached_until': report['cached_until'].isoformat() if isinstance(report['cached_until'], datetime) else report['cached_until']
            },
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in report generation endpoint: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'message': 'Report generation failed',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/reports/<report_id>', methods=['GET'])
def get_report(report_id):
    """Get a specific report by ID"""
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        report = db_service.get_airline_report(report_id)

        if not report:
            return jsonify({
                'success': False,
                'error': 'Report not found',
                'timestamp': datetime.now().isoformat()
            }), 404

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'report': {
                'id': report['id'],
                'report_type': report['report_type'],
                'subject': report['subject'],
                'generated_at': report['generated_at'].isoformat() if isinstance(report['generated_at'], datetime) else report['generated_at'],
                'period_start': report['period_start'].isoformat() if isinstance(report['period_start'], datetime) else report['period_start'],
                'period_end': report['period_end'].isoformat() if isinstance(report['period_end'], datetime) else report['period_end'],
                'markdown_content': report['markdown_content'],
                'html_content': report['html_content'],
                'sections': report['sections'],
                'metadata': report['metadata'],
                'cached_until': report['cached_until'].isoformat() if isinstance(report['cached_until'], datetime) else report['cached_until']
            },
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in get report endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/reports', methods=['GET'])
def list_reports():
    """
    List all airline reports with optional filtering

    Query parameters:
        subject: Filter by airline name (optional)
        limit: Maximum number of reports to return (default: 50)
        offset: Number of reports to skip (default: 0)
    """
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Get query parameters
        subject = request.args.get('subject')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        # Get reports from database
        reports = db_service.get_airline_reports(
            subject=subject,
            limit=limit,
            offset=offset
        )

        # Format reports for response
        formatted_reports = []
        for report in reports:
            formatted_reports.append({
                'id': report.get('id'),
                'report_type': report.get('report_type'),
                'subject': report.get('subject'),
                'generated_at': report['generated_at'].isoformat() if isinstance(report['generated_at'], datetime) else report['generated_at'],
                'period_start': report['period_start'].isoformat() if isinstance(report['period_start'], datetime) else report['period_start'],
                'period_end': report['period_end'].isoformat() if isinstance(report['period_end'], datetime) else report['period_end'],
                'articles_analyzed': report.get('metadata', {}).get('articles_analyzed', 0),
                'cached_until': report['cached_until'].isoformat() if isinstance(report.get('cached_until'), datetime) else report.get('cached_until')
            })

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'reports': formatted_reports,
            'count': len(formatted_reports),
            'subject_filter': subject,
            'limit': limit,
            'offset': offset,
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in list reports endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/newsletter/generate', methods=['POST'])
@require_api_key
def generate_newsletter():
    """
    Generate a weekly newsletter

    Request body (optional):
    {
        "week_offset": 0,  # 0 = last week, 1 = 2 weeks ago, etc.
        "frequency": "weekly",  # weekly, monthly (future)
        "format": "html",  # html, pdf, both
        "sections": {  # Which sections to include
            "executive_summary": true,
            "market_indicators": true,
            "industry_news": true,
            "risk_analysis": true,
            "outlook": true
        }
    }
    """
    start_time = datetime.now()

    try:
        if not insights_service:
            return jsonify({
                'success': False,
                'error': 'AI insights service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Get request data
        data = request.get_json() or {}
        week_offset = data.get('week_offset', 0)
        frequency = data.get('frequency', 'weekly')
        format_type = data.get('format', 'html')
        sections = data.get('sections', {
            'executive_summary': True,
            'market_indicators': True,
            'industry_news': True,
            'risk_analysis': True,
            'outlook': True
        })

        # Generate newsletter
        logger.info(f"📰 Generating {frequency} newsletter (offset: {week_offset}, format: {format_type})")
        newsletter = insights_service.generate_weekly_newsletter(
            week_offset=week_offset,
            frequency=frequency,
            format_type=format_type,
            sections=sections
        )

        if not newsletter:
            return jsonify({
                'success': False,
                'error': 'Failed to generate newsletter',
                'timestamp': datetime.now().isoformat()
            }), 500

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"✅ Newsletter generated in {response_time:.1f}ms")

        return jsonify({
            'success': True,
            'newsletter': {
                'id': newsletter['id'],
                'week_start': newsletter['week_start'].isoformat() if isinstance(newsletter['week_start'], datetime) else newsletter['week_start'],
                'week_end': newsletter['week_end'].isoformat() if isinstance(newsletter['week_end'], datetime) else newsletter['week_end'],
                'generated_at': newsletter['generated_at'].isoformat() if isinstance(newsletter['generated_at'], datetime) else newsletter['generated_at'],
                'markdown_content': newsletter['markdown_content'],
                'html_content': newsletter['html_content'],
                'sections': newsletter['sections'],
                'articles_analyzed': newsletter['articles_analyzed'],
                'previous_newsletter_id': newsletter.get('previous_newsletter_id'),
                'predictions_from_last_week': newsletter.get('predictions_from_last_week'),
                'metadata': newsletter['metadata'],
                'frequency': newsletter.get('frequency', 'weekly'),
                'format': newsletter.get('format', 'html')
            },
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in newsletter generation endpoint: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),  # Show actual error message
            'error_type': type(e).__name__,
            'message': 'Newsletter generation failed',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/newsletter/latest', methods=['GET'])
def get_latest_newsletter():
    """Get the most recent newsletter"""
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        newsletter = db_service.get_latest_newsletter()

        if not newsletter:
            return jsonify({
                'success': False,
                'error': 'No newsletters found',
                'timestamp': datetime.now().isoformat()
            }), 404

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'newsletter': {
                'id': newsletter['id'],
                'week_start': newsletter['week_start'].isoformat() if isinstance(newsletter['week_start'], datetime) else newsletter['week_start'],
                'week_end': newsletter['week_end'].isoformat() if isinstance(newsletter['week_end'], datetime) else newsletter['week_end'],
                'generated_at': newsletter['generated_at'].isoformat() if isinstance(newsletter['generated_at'], datetime) else newsletter['generated_at'],
                'markdown_content': newsletter['markdown_content'],
                'html_content': newsletter['html_content'],
                'sections': newsletter['sections'],
                'articles_analyzed': newsletter['articles_analyzed'],
                'previous_newsletter_id': newsletter.get('previous_newsletter_id'),
                'predictions_from_last_week': newsletter.get('predictions_from_last_week'),
                'metadata': newsletter['metadata']
            },
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in get latest newsletter endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/newsletter/<newsletter_id>', methods=['GET'])
def get_newsletter(newsletter_id):
    """Get a specific newsletter by ID (date in YYYY-MM-DD format)"""
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        newsletter = db_service.get_newsletter(newsletter_id)

        if not newsletter:
            return jsonify({
                'success': False,
                'error': 'Newsletter not found',
                'timestamp': datetime.now().isoformat()
            }), 404

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'newsletter': {
                'id': newsletter['id'],
                'week_start': newsletter['week_start'].isoformat() if isinstance(newsletter['week_start'], datetime) else newsletter['week_start'],
                'week_end': newsletter['week_end'].isoformat() if isinstance(newsletter['week_end'], datetime) else newsletter['week_end'],
                'generated_at': newsletter['generated_at'].isoformat() if isinstance(newsletter['generated_at'], datetime) else newsletter['generated_at'],
                'markdown_content': newsletter['markdown_content'],
                'html_content': newsletter['html_content'],
                'sections': newsletter['sections'],
                'articles_analyzed': newsletter['articles_analyzed'],
                'previous_newsletter_id': newsletter.get('previous_newsletter_id'),
                'predictions_from_last_week': newsletter.get('predictions_from_last_week'),
                'metadata': newsletter['metadata']
            },
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in get newsletter endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/newsletters', methods=['GET'])
def get_all_newsletters():
    """Get all newsletters (for archive page)"""
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Get optional limit parameter
        limit = request.args.get('limit', type=int)

        newsletters = db_service.get_all_newsletters(limit=limit)

        if not newsletters:
            return jsonify({
                'success': True,
                'newsletters': [],
                'count': 0,
                'timestamp': datetime.now().isoformat()
            })

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        # Format newsletters for response (metadata only, not full content)
        formatted_newsletters = []
        for newsletter in newsletters:
            formatted_newsletters.append({
                'id': newsletter['id'],
                'week_start': newsletter['week_start'].isoformat() if isinstance(newsletter['week_start'], datetime) else newsletter['week_start'],
                'week_end': newsletter['week_end'].isoformat() if isinstance(newsletter['week_end'], datetime) else newsletter['week_end'],
                'generated_at': newsletter['generated_at'].isoformat() if isinstance(newsletter['generated_at'], datetime) else newsletter['generated_at'],
                'articles_analyzed': newsletter['articles_analyzed'],
                'frequency': newsletter.get('frequency', 'weekly'),
                'format': newsletter.get('format', 'html'),
                'metadata': newsletter.get('metadata', {})
            })

        return jsonify({
            'success': True,
            'newsletters': formatted_newsletters,
            'count': len(formatted_newsletters),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in get all newsletters endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ============================================================================
# RISK ASSESSMENT ENDPOINTS - For Weekly Outlook
# ============================================================================

@app.route('/api/risks/operational')
def get_operational_risks():
    """Get recent operational risk articles for weekly outlook"""
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Fetch articles tagged with 'operational_risk' from last 30 days
        start_date = datetime.now() - timedelta(days=30)
        articles = db_service.get_articles(
            tags=['operational_risk'],
            start_date=start_date,
            limit=5
        )

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'risks': [{
                'title': article['title'],
                'impact_statement': article.get('impact_statement') or article.get('summary', '')[:150],
                'source': article['source'],
                'published_at': article['published_at'],
                'tags': article.get('tags', [])
            } for article in articles],
            'count': len(articles),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in operational risks endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/risks/financial')
def get_financial_risks():
    """Get recent financial risk articles for weekly outlook"""
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Fetch articles tagged with 'financial_risk' from last 30 days
        start_date = datetime.now() - timedelta(days=30)
        articles = db_service.get_articles(
            tags=['financial_risk'],
            start_date=start_date,
            limit=5
        )

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'risks': [{
                'title': article['title'],
                'impact_statement': article.get('impact_statement') or article.get('summary', '')[:150],
                'source': article['source'],
                'published_at': article['published_at'],
                'tags': article.get('tags', [])
            } for article in articles],
            'count': len(articles),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in financial risks endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/risks/regulatory')
def get_regulatory_risks():
    """Get recent regulatory watch articles for weekly outlook"""
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Fetch articles tagged with 'regulatory' from last 30 days
        start_date = datetime.now() - timedelta(days=30)
        articles = db_service.get_articles(
            tags=['regulatory'],
            start_date=start_date,
            limit=5
        )

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'risks': [{
                'title': article['title'],
                'impact_statement': article.get('impact_statement') or article.get('summary', '')[:150],
                'source': article['source'],
                'published_at': article['published_at'],
                'tags': article.get('tags', [])
            } for article in articles],
            'count': len(articles),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in regulatory watch endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ============================================================================
# WEEKLY OUTLOOK INSIGHTS ENDPOINTS - AI-Generated Content
# ============================================================================

@app.route('/api/weekly-outlook/investment-themes')
def get_investment_themes():
    """Get AI-generated investment themes for weekly outlook"""
    start_time = datetime.now()

    try:
        if not insights_service:
            return jsonify({
                'success': False,
                'error': 'Insights service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Generate investment themes (uses cache if available)
        themes = insights_service.generate_investment_themes(use_cache=True)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        if themes:
            return jsonify({
                'success': True,
                'themes': themes,
                'count': len(themes),
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate investment themes',
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            }), 500

    except Exception as e:
        logger.error(f"❌ Error in investment themes endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/weekly-outlook/recommendations')
def get_strategic_recommendations():
    """Get AI-generated strategic recommendations for weekly outlook"""
    start_time = datetime.now()

    try:
        if not insights_service:
            return jsonify({
                'success': False,
                'error': 'Insights service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Generate strategic recommendations (uses cache if available)
        recommendation = insights_service.generate_strategic_recommendations(use_cache=True)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        if recommendation:
            return jsonify({
                'success': True,
                'recommendation': recommendation,
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate strategic recommendations',
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            }), 500

    except Exception as e:
        logger.error(f"❌ Error in strategic recommendations endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/weekly-outlook/executive-summary')
def get_executive_summary():
    """Get AI-generated executive summary for weekly outlook"""
    start_time = datetime.now()

    try:
        if not insights_service:
            return jsonify({
                'success': False,
                'error': 'Insights service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Generate executive summary (uses cache if available)
        summary = insights_service.generate_executive_summary(use_cache=True)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        if summary:
            return jsonify({
                'success': True,
                'summary': summary,
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate executive summary',
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            }), 500

    except Exception as e:
        logger.error(f"❌ Error in executive summary endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/weekly-outlook/catalysts')
def get_catalysts():
    """Get AI-generated upcoming catalysts for weekly outlook"""
    start_time = datetime.now()

    try:
        if not insights_service:
            return jsonify({
                'success': False,
                'error': 'Insights service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Generate catalysts (uses 7-day cache if available)
        catalysts = insights_service.generate_catalysts(use_cache=True)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        if catalysts:
            return jsonify({
                'success': True,
                'catalysts': catalysts,
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate catalysts',
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            }), 500

    except Exception as e:
        logger.error(f"❌ Error in catalysts endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/weekly-outlook/load-factor')
def get_industry_load_factor():
    """Get industry-wide load factor data"""
    start_time = datetime.now()

    try:
        if not tsa_service:
            return jsonify({
                'success': False,
                'error': 'TSA service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        # Get recent TSA data (last 30 days for load factor calculation)
        recent_data = tsa_service.get_recent_data(days=30)

        if not recent_data or len(recent_data) == 0:
            return jsonify({
                'success': False,
                'error': 'No TSA data available',
                'timestamp': datetime.now().isoformat()
            }), 404

        # Calculate average load factor from recent data
        # TSA data includes passenger counts; load factor is typically 80-85% industry average
        # We'll calculate based on year-over-year trends
        total_current = sum(d.get('current_year', 0) for d in recent_data)
        total_last_year = sum(d.get('last_year', 0) for d in recent_data)

        # Industry baseline load factor (typical range: 75-90%)
        baseline_load_factor = 82.5  # Industry average

        # Adjust based on YoY traffic trend
        if total_last_year > 0:
            yoy_growth = ((total_current - total_last_year) / total_last_year) * 100
            # Higher traffic often correlates with higher load factors (up to a point)
            adjusted_load_factor = baseline_load_factor + (yoy_growth * 0.1)
            # Keep within realistic bounds
            adjusted_load_factor = max(75.0, min(90.0, adjusted_load_factor))
        else:
            adjusted_load_factor = baseline_load_factor

        # Get latest data point for trend info
        latest = recent_data[0] if recent_data else {}
        latest_date = latest.get('date', 'N/A')

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'load_factor': round(adjusted_load_factor, 1),
            'baseline': baseline_load_factor,
            'yoy_growth': round(((total_current - total_last_year) / total_last_year) * 100, 1) if total_last_year > 0 else 0,
            'latest_date': latest_date,
            'data_points': len(recent_data),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in load factor endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ============================================================================
# CARRIER FINANCIALS ENDPOINTS - BTS Form 41 Data
# ============================================================================

@app.route('/api/carriers')
def list_carriers():
    """List all available carriers with basic info"""
    start_time = datetime.now()

    try:
        if not bts_service:
            return jsonify({
                'success': False,
                'error': 'BTS service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        carriers = []
        for code, info in bts_service.CARRIER_CODES.items():
            carriers.append({
                'carrier_code': code,
                'carrier_name': info['name'],
                'ticker': info['ticker']
            })

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'carriers': carriers,
            'count': len(carriers),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in list carriers endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/carriers/<carrier_code>/financials')
def get_carrier_financials(carrier_code: str):
    """Get financial data for a specific carrier"""
    start_time = datetime.now()

    try:
        if not bts_service:
            return jsonify({
                'success': False,
                'error': 'BTS service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        carrier_code = carrier_code.upper()
        financials = bts_service.get_carrier_financials(carrier_code)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        if financials:
            return jsonify({
                'success': True,
                'financials': financials,
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            })
        else:
            return jsonify({
                'success': False,
                'error': f'No financial data found for carrier {carrier_code}',
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            }), 404

    except Exception as e:
        logger.error(f"❌ Error in carrier financials endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/carriers/all')
def get_all_carrier_financials():
    """Get financial data for all carriers"""
    start_time = datetime.now()

    try:
        if not bts_service:
            return jsonify({
                'success': False,
                'error': 'BTS service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        all_financials = bts_service.get_all_carriers()

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'carriers': all_financials,
            'count': len(all_financials),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in all carrier financials endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/carriers/refresh', methods=['POST'])
def refresh_carrier_financials():
    """Refresh financial data for all carriers (admin endpoint)"""
    start_time = datetime.now()

    try:
        if not bts_service:
            return jsonify({
                'success': False,
                'error': 'BTS service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        result = bts_service.refresh_all_carriers()

        response_time = (datetime.now() - start_time).total_seconds() * 1000
        result['response_time_ms'] = round(response_time, 1)

        return jsonify(result)

    except Exception as e:
        logger.error(f"❌ Error in refresh carriers endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/carriers/<carrier_code>/report-context')
def get_carrier_report_context(carrier_code: str):
    """Get formatted carrier financials for inclusion in reports"""
    start_time = datetime.now()

    try:
        if not bts_service:
            return jsonify({
                'success': False,
                'error': 'BTS service not available',
                'timestamp': datetime.now().isoformat()
            }), 503

        carrier_code = carrier_code.upper()
        formatted_context = bts_service.format_for_report(carrier_code)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'carrier_code': carrier_code,
            'report_context': formatted_context,
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in carrier report context endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/balance-sheet/<airline_name>')
def get_balance_sheet(airline_name: str):
    """Get balance sheet data from Yahoo Finance for an airline"""
    start_time = datetime.now()

    try:
        if not financial_service:
            return jsonify({
                'success': False,
                'error': 'Financial service not initialized',
                'timestamp': datetime.now().isoformat()
            }), 503

        # URL decode the airline name (spaces come as %20)
        from urllib.parse import unquote
        airline_name = unquote(airline_name)

        balance_sheet = financial_service.get_balance_sheet_data(airline_name)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        if balance_sheet:
            return jsonify({
                'success': True,
                'airline_name': airline_name,
                'balance_sheet': balance_sheet,
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            })
        else:
            # Check if yfinance is available
            from app.services.financial_data_service import YFINANCE_AVAILABLE
            return jsonify({
                'success': False,
                'error': f'Could not fetch balance sheet for {airline_name}',
                'yfinance_available': YFINANCE_AVAILABLE,
                'ticker_found': financial_service.get_ticker(airline_name),
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            }), 404

    except Exception as e:
        logger.error(f"❌ Error in balance sheet endpoint: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/credit-benchmarks')
def get_credit_benchmarks():
    """Get multi-tier credit spread benchmarks from FRED"""
    start_time = datetime.now()

    try:
        if not fred_service:
            return jsonify({
                'success': False,
                'error': 'FRED service not initialized',
                'timestamp': datetime.now().isoformat()
            }), 503

        benchmarks = fred_service.get_credit_spread_benchmarks()
        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            **benchmarks,
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in credit benchmarks endpoint: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/credit-rating/<airline_name>')
def get_credit_rating(airline_name: str):
    """Get estimated credit rating for an airline based on financial metrics"""
    start_time = datetime.now()

    try:
        if not financial_service:
            return jsonify({
                'success': False,
                'error': 'Financial service not initialized',
                'timestamp': datetime.now().isoformat()
            }), 503

        # URL decode the airline name
        from urllib.parse import unquote
        airline_name = unquote(airline_name)

        # Get balance sheet data
        balance_sheet = financial_service.get_balance_sheet_data(airline_name)

        if not balance_sheet:
            return jsonify({
                'success': False,
                'error': f'Could not fetch financial data for {airline_name}',
                'timestamp': datetime.now().isoformat()
            }), 404

        # Get credit rating estimate
        debt_to_ebitda = balance_sheet.get('debt_to_ebitda')
        interest_coverage = balance_sheet.get('interest_coverage')

        rating_estimate = financial_service.estimate_credit_rating(
            debt_to_ebitda=debt_to_ebitda if debt_to_ebitda else 0,
            interest_coverage=interest_coverage if interest_coverage else 0
        )

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'airline_name': airline_name,
            'ticker': balance_sheet.get('ticker'),
            'rating_estimate': rating_estimate,
            'underlying_metrics': {
                'debt_to_ebitda': debt_to_ebitda,
                'interest_coverage': interest_coverage,
                'total_debt': balance_sheet.get('total_debt'),
                'ebitda': balance_sheet.get('ebitda'),
                'ebit': balance_sheet.get('ebit'),
                'interest_expense': balance_sheet.get('interest_expense')
            },
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error in credit rating endpoint: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# ============================================================================
# AUTOMATED DATA INGESTION ENDPOINTS - Daily Pre-loading
# ============================================================================

@app.route('/api/ingest/financial-data', methods=['POST'])
def ingest_financial_data():
    """
    Daily ingestion of all financial data sources
    Designed to be triggered by Cloud Scheduler at 7:00 AM ET

    This endpoint pre-loads:
    1. FRED credit spreads (all rating tiers: AA, A, BBB, BB)
    2. Carrier financials for all tracked airlines
    3. TSA passenger data
    4. BTS operational metrics
    """
    start_time = datetime.now()
    from datetime import timezone

    results = {
        'success': True,
        'fred_data': {},
        'carrier_financials': {},
        'tsa_data': {},
        'bts_data': {},
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'errors': []
    }

    # 1. Fetch and store FRED credit spreads (all tiers)
    try:
        if fred_service:
            logger.info("📊 Ingesting FRED credit spreads...")
            fred_data = fred_service.get_credit_spread_benchmarks()
            if fred_data and fred_data.get('success'):
                db_service.store_financial_snapshot('fred_spreads', fred_data)
                results['fred_data'] = {
                    'status': 'success',
                    'data_date': fred_data.get('data_date'),
                    'spreads_fetched': len(fred_data.get('spreads', {}))
                }
                logger.info(f"✅ FRED data stored: {fred_data.get('data_date')}")
            else:
                results['fred_data'] = {'status': 'no_data'}
                results['errors'].append('FRED: No data returned')
        else:
            results['fred_data'] = {'status': 'service_unavailable'}
            results['errors'].append('FRED: Service not available')
    except Exception as e:
        results['fred_data'] = {'status': 'error', 'message': str(e)}
        results['errors'].append(f'FRED: {str(e)}')
        logger.error(f"❌ FRED ingestion error: {e}")

    # 2. Fetch and store carrier financials for all tracked airlines
    airlines = [
        'United Airlines', 'Delta Air Lines', 'American Airlines',
        'Southwest Airlines', 'Alaska Airlines', 'JetBlue Airways'
    ]

    if financial_service:
        logger.info("💰 Ingesting carrier financials...")
        for airline in airlines:
            try:
                balance_sheet = financial_service.get_balance_sheet_data(airline)
                if balance_sheet:
                    # Add credit rating estimate
                    debt_to_ebitda = balance_sheet.get('debt_to_ebitda')
                    interest_coverage = balance_sheet.get('interest_coverage')
                    if debt_to_ebitda and interest_coverage:
                        rating = financial_service.estimate_credit_rating(debt_to_ebitda, interest_coverage)
                        balance_sheet['credit_rating_estimate'] = rating

                    db_service.store_carrier_financial_snapshot(airline, balance_sheet)
                    results['carrier_financials'][airline] = 'success'
                    logger.info(f"✅ {airline} financials stored")
                else:
                    results['carrier_financials'][airline] = 'no_data'
            except Exception as e:
                results['carrier_financials'][airline] = f'error: {str(e)}'
                results['errors'].append(f'{airline}: {str(e)}')
                logger.error(f"❌ {airline} ingestion error: {e}")
    else:
        for airline in airlines:
            results['carrier_financials'][airline] = 'service_unavailable'
        results['errors'].append('Financial service not available')

    # 3. Fetch and store TSA passenger data
    try:
        if tsa_service:
            logger.info("🛂 Ingesting TSA passenger data...")
            tsa_data = tsa_service.get_real_tsa_data()
            if tsa_data and tsa_data.get('success'):
                db_service.store_financial_snapshot('tsa_passengers', tsa_data['data'])
                results['tsa_data'] = {
                    'status': 'success',
                    'date': tsa_data['data'].get('date'),
                    'throughput': tsa_data['data'].get('current_throughput')
                }
                logger.info(f"✅ TSA data stored: {tsa_data['data'].get('date')}")
            else:
                results['tsa_data'] = {'status': 'no_data'}
        else:
            results['tsa_data'] = {'status': 'service_unavailable'}
    except Exception as e:
        results['tsa_data'] = {'status': 'error', 'message': str(e)}
        results['errors'].append(f'TSA: {str(e)}')
        logger.error(f"❌ TSA ingestion error: {e}")

    # 4. Fetch and store BTS operational data for carriers
    if bts_service:
        logger.info("📈 Ingesting BTS operational metrics...")
        results['bts_data'] = {}
        for airline in airlines:
            try:
                # Get carrier code from airline name
                carrier_code = None
                for code, info in bts_service.CARRIER_CODES.items():
                    if info['name'] == airline:
                        carrier_code = code
                        break

                if carrier_code:
                    bts_data = bts_service.get_carrier_financials(carrier_code)
                    if bts_data:
                        db_service.store_financial_snapshot(f'bts_{airline.replace(" ", "_")}', bts_data)
                        results['bts_data'][airline] = 'success'
                        logger.info(f"✅ BTS data stored for {airline}")
                    else:
                        results['bts_data'][airline] = 'no_data'
                else:
                    results['bts_data'][airline] = 'carrier_not_found'
            except Exception as e:
                results['bts_data'][airline] = f'error: {str(e)}'
                logger.error(f"❌ BTS ingestion error for {airline}: {e}")
    else:
        results['bts_data'] = {'status': 'service_unavailable'}

    # Calculate response time and finalize
    response_time = (datetime.now() - start_time).total_seconds() * 1000
    results['response_time_ms'] = round(response_time, 1)
    results['success'] = len(results['errors']) == 0

    logger.info(f"📊 Financial data ingestion complete in {response_time:.1f}ms - {len(results['errors'])} errors")

    return jsonify(results)


@app.route('/api/ingest/status', methods=['GET'])
def get_ingestion_status():
    """
    Check the status of pre-loaded financial data
    Returns freshness of each data type
    """
    start_time = datetime.now()
    from datetime import timezone

    status = {
        'success': True,
        'data_freshness': {},
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    # Check FRED data freshness
    try:
        fred_snapshot = db_service.get_latest_financial_snapshot('fred_spreads')
        if fred_snapshot:
            stored_at = fred_snapshot.get('stored_at')
            if stored_at:
                age_hours = (datetime.now(timezone.utc) - stored_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
                status['data_freshness']['fred_spreads'] = {
                    'last_updated': stored_at.isoformat() if hasattr(stored_at, 'isoformat') else str(stored_at),
                    'age_hours': round(age_hours, 1),
                    'is_fresh': age_hours < 24
                }
        else:
            status['data_freshness']['fred_spreads'] = {'status': 'no_data'}
    except Exception as e:
        status['data_freshness']['fred_spreads'] = {'status': 'error', 'message': str(e)}

    # Check TSA data freshness
    try:
        tsa_snapshot = db_service.get_latest_financial_snapshot('tsa_passengers')
        if tsa_snapshot:
            stored_at = tsa_snapshot.get('stored_at')
            if stored_at:
                age_hours = (datetime.now(timezone.utc) - stored_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
                status['data_freshness']['tsa_passengers'] = {
                    'last_updated': stored_at.isoformat() if hasattr(stored_at, 'isoformat') else str(stored_at),
                    'age_hours': round(age_hours, 1),
                    'is_fresh': age_hours < 24
                }
        else:
            status['data_freshness']['tsa_passengers'] = {'status': 'no_data'}
    except Exception as e:
        status['data_freshness']['tsa_passengers'] = {'status': 'error', 'message': str(e)}

    # Check carrier financial snapshots
    airlines = ['United Airlines', 'Delta Air Lines', 'American Airlines']
    for airline in airlines:
        try:
            carrier_snapshot = db_service.get_latest_carrier_financial_snapshot(airline)
            if carrier_snapshot:
                stored_at = carrier_snapshot.get('stored_at')
                if stored_at:
                    age_hours = (datetime.now(timezone.utc) - stored_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
                    status['data_freshness'][airline] = {
                        'last_updated': stored_at.isoformat() if hasattr(stored_at, 'isoformat') else str(stored_at),
                        'age_hours': round(age_hours, 1),
                        'is_fresh': age_hours < 24
                    }
            else:
                status['data_freshness'][airline] = {'status': 'no_data'}
        except Exception as e:
            status['data_freshness'][airline] = {'status': 'error', 'message': str(e)}

    response_time = (datetime.now() - start_time).total_seconds() * 1000
    status['response_time_ms'] = round(response_time, 1)

    return jsonify(status)


# ============================================================================
# DEFENSE CONTRACTS ENDPOINTS
# ============================================================================

# Initialize defense contracts handler
try:
    from app.services.sources.defense_contracts_handler import DefenseContractsHandler
    defense_contracts_handler = DefenseContractsHandler()
    logger.info("✅ Defense Contracts handler initialized")
except Exception as e:
    logger.warning(f"⚠️ Defense Contracts handler initialization failed: {e}")
    defense_contracts_handler = None


@app.route('/api/defense-contracts', methods=['GET'])
def get_defense_contracts():
    """
    Get defense contracts with optional filters

    Query params:
        - start_date: Filter contracts after this date (YYYY-MM-DD)
        - end_date: Filter contracts before this date (YYYY-MM-DD)
        - branch: Filter by military branch (NAVY, AIR FORCE, ARMY, etc.)
        - contractor: Filter by contractor name (partial match)
        - aviation_only: If 'true', only return aviation-related contracts
        - limit: Maximum number of results (default 50)
    """
    start_time = datetime.now()

    try:
        # Parse query parameters
        start_date = None
        end_date = None

        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

        branch = request.args.get('branch')
        contractor = request.args.get('contractor')
        aviation_only = request.args.get('aviation_only', 'false').lower() == 'true'
        limit = int(request.args.get('limit', 50))

        # Get contracts from database
        contracts = db_service.get_defense_contracts(
            start_date=start_date,
            end_date=end_date,
            branch=branch,
            contractor=contractor,
            aviation_only=aviation_only,
            limit=limit
        )

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'contracts': contracts,
            'count': len(contracts),
            'filters': {
                'start_date': start_date_str,
                'end_date': end_date_str,
                'branch': branch,
                'contractor': contractor,
                'aviation_only': aviation_only,
                'limit': limit
            },
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"Error fetching defense contracts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/defense-contracts/summary', methods=['GET'])
def get_defense_contracts_summary():
    """
    Get summary statistics for defense contracts

    Query params:
        - start_date: Filter contracts after this date (YYYY-MM-DD)
        - end_date: Filter contracts before this date (YYYY-MM-DD)
    """
    start_time = datetime.now()

    try:
        start_date = None
        end_date = None

        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

        summary = db_service.get_defense_contract_summary(
            start_date=start_date,
            end_date=end_date
        )

        response_time = (datetime.now() - start_time).total_seconds() * 1000
        summary['response_time_ms'] = round(response_time, 1)
        summary['success'] = True

        return jsonify(summary)

    except Exception as e:
        logger.error(f"Error fetching defense contracts summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ingest/defense-contracts', methods=['POST'])
def ingest_defense_contracts():
    """
    Ingest defense contracts from defense.gov

    This endpoint fetches recent contract announcements and stores them
    in Firestore. Designed to be triggered daily by Cloud Scheduler.

    Request body (optional):
        - days_back: Number of days to fetch (default 7)
        - aviation_only: If true, only store aviation-related contracts (default true)
    """
    start_time = datetime.now()
    from datetime import timezone

    if not defense_contracts_handler:
        return jsonify({
            'success': False,
            'error': 'Defense contracts handler not available'
        }), 503

    if not db_service:
        return jsonify({
            'success': False,
            'error': 'Database service not available'
        }), 503

    try:
        # Parse request body
        data = request.get_json() or {}
        days_back = data.get('days_back', 7)
        aviation_only = data.get('aviation_only', True)

        logger.info(f"🎯 Starting defense contracts ingestion (last {days_back} days, aviation_only={aviation_only})")

        # Fetch contracts from defense.gov
        contracts = defense_contracts_handler.fetch_recent_contracts(
            days_back=days_back,
            aviation_only=aviation_only
        )

        logger.info(f"📋 Fetched {len(contracts)} contracts from defense.gov")

        # Store contracts in database
        saved_count = 0
        duplicate_count = 0
        errors = []

        for contract in contracts:
            try:
                doc_id = db_service.save_defense_contract(contract)
                if doc_id:
                    saved_count += 1
                else:
                    duplicate_count += 1
            except Exception as e:
                errors.append(f"{contract.get('contractor', 'Unknown')}: {str(e)}")

        # Generate summary
        summary = defense_contracts_handler.get_aviation_contract_summary(contracts)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        result = {
            'success': True,
            'contracts_fetched': len(contracts),
            'contracts_saved': saved_count,
            'duplicates_skipped': duplicate_count,
            'errors': errors,
            'summary': summary,
            'parameters': {
                'days_back': days_back,
                'aviation_only': aviation_only
            },
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'response_time_ms': round(response_time, 1)
        }

        logger.info(f"✅ Defense contracts ingestion complete: {saved_count} saved, {duplicate_count} duplicates, {len(errors)} errors")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error during defense contracts ingestion: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/defense-contracts/test', methods=['GET'])
def test_defense_contracts_connection():
    """
    Test connection to defense.gov contracts page
    """
    if not defense_contracts_handler:
        return jsonify({
            'success': False,
            'error': 'Defense contracts handler not available'
        }), 503

    result = defense_contracts_handler.test_connection()
    return jsonify(result)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

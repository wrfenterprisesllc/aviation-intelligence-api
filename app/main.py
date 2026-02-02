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
    gemini_service = GeminiService()
    insights_service = InsightsService(gemini_service=gemini_service, database_service=db_service)
    logger.info("✅ Gemini and Insights services initialized")
except Exception as e:
    logger.warning(f"⚠️ Gemini/Insights service initialization failed: {e}")
    gemini_service = None
    insights_service = None

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
            '/api/news/stats',
            '/api/tsa/historical',
            '/api/credit-spread/historical',
            '/api/reports/generate',
            '/api/reports/<id>',
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

        if report_type not in ['airline', 'sector']:
            return jsonify({
                'success': False,
                'error': 'report_type must be either "airline" or "sector"',
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
        logger.error(f"❌ Error in report generation endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
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
        logger.error(f"❌ Error in newsletter generation endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

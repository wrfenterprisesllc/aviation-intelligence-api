#!/usr/bin/env python3
"""
Aviation Intelligence API - Live Data Integration with Monitoring
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import services
try:
    from services.fred_service import FREDCreditSpreadsFinal
    fred_service = FREDCreditSpreadsFinal()
    logger.info("✅ FRED service initialized")
except Exception as e:
    logger.warning(f"⚠️ FRED service initialization failed: {e}")
    fred_service = None

try:
    from services.tsa_service import TSADataService
    tsa_service = TSADataService()
    logger.info("✅ TSA service initialized")
except Exception as e:
    logger.warning(f"⚠️ TSA service initialization failed: {e}")
    tsa_service = None

try:
    from services.monitoring_service import MonitoringService
    monitor = MonitoringService()
    logger.info("✅ Monitoring service initialized")
except Exception as e:
    logger.warning(f"⚠️ Monitoring service initialization failed: {e}")
    monitor = None

try:
    from services.news_ingestion import NewsIngestionService
    news_service = NewsIngestionService()
    logger.info("✅ News ingestion service initialized")
except Exception as e:
    logger.warning(f"⚠️ News ingestion service initialization failed: {e}")
    news_service = None

try:
    from services.database_service import DatabaseService
    db_service = DatabaseService()
    logger.info("✅ Database service initialized")
except Exception as e:
    logger.warning(f"⚠️ Database service initialization failed: {e}")
    db_service = None

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
            'firestore_database': db_service is not None
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
            '/api/news/stats'
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

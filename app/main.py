#!/usr/bin/env python3
"""
Aviation Intelligence API - Live Data Integration with Monitoring
Version 2.1.0 with API Hardening (Epic 1.7)
"""

import os
import json
import logging
import re
import threading
import uuid
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_file
from io import BytesIO
from flask_cors import CORS
from flasgger import Swagger
from app.utils.auth import require_api_key
from app.utils.firebase_auth import require_auth, require_role, require_auth_or_api_key, get_current_user_uid
from app.utils.errors import register_error_handlers
from app.utils.rate_limits import limiter, RATE_TIERS
from app.utils.pipeline_tracker import PipelineTracker

# Background job tracking
_background_jobs = {}
_background_jobs_lock = threading.Lock()

app = Flask(__name__)

# ============================================================
# CORS Configuration - Restricted to known origins
# ============================================================
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://ai.wrfenterprisesllc.com",
            "https://aviation-intelligence-rmexsuffdq-uc.a.run.app",
            "https://ai-projects-485420.uc.r.appspot.com",
            "https://aviation-intelligence.wl.r.appspot.com",
            re.compile(r"^http://localhost(:\d+)?$"),
            re.compile(r"^http://127\.0\.0\.1(:\d+)?$")
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-API-Key", "Authorization"],
        "expose_headers": [
            "X-API-Key",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-Deprecation-Warning",
            "X-Request-ID"
        ],
        "max_age": 3600
    },
    r"/health": {"origins": "*"},
    r"/ready": {"origins": "*"},
    r"/api/docs*": {"origins": "*"}
})

# ============================================================
# Rate Limiter Initialization
# ============================================================
limiter.init_app(app)

# ============================================================
# Error Handlers
# ============================================================
register_error_handlers(app)

# ============================================================
# Swagger/OpenAPI Documentation
# ============================================================
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/api/v1/docs/apispec.json",
            "rule_filter": lambda rule: rule.rule.startswith("/api/"),
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs"
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Aviation Intelligence Platform API",
        "description": "Market intelligence, credit scoring, and deal evaluation for aviation finance professionals.",
        "version": "1.0.0",
        "contact": {
            "name": "WRF Enterprises LLC",
            "email": "admin@wrfenterprisesllc.com",
            "url": "https://ai.wrfenterprisesllc.com"
        }
    },
    "host": "aviation-intelligence-api-rmexsuffdq-uc.a.run.app",
    "basePath": "/api/v1",
    "schemes": ["https"],
    "securityDefinitions": {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for scheduled jobs and internal services"
        },
        "BearerAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Firebase ID token. Format: Bearer <token>"
        }
    },
    "tags": [
        {"name": "Health", "description": "Health and status endpoints"},
        {"name": "Users", "description": "User profile management"},
        {"name": "Admin", "description": "Admin-only user management"},
        {"name": "Market Data", "description": "Live market data (TSA, FRED, fuel prices)"},
        {"name": "News", "description": "News article ingestion and management"},
        {"name": "Reports", "description": "AI-generated intelligence reports"},
        {"name": "Newsletters", "description": "Weekly newsletter generation"},
        {"name": "Carriers", "description": "Airline carrier financial data"},
        {"name": "Deals", "description": "Aircraft deal evaluation and pricing"},
        {"name": "Credit Scores", "description": "Airline credit scoring system"},
        {"name": "Backtesting", "description": "Credit model validation and backtesting"},
        {"name": "Scheduler", "description": "Data ingestion and scheduled jobs"},
        {"name": "Pipeline Monitoring", "description": "Data pipeline health and freshness"}
    ]
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

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

# Deal Evaluator Service
try:
    from app.services.deal_evaluator_service import DealEvaluatorService
    deal_evaluator_service = DealEvaluatorService(
        db_service=db_service,
        fred_service=fred_service,
        financial_service=financial_service,
        gemini_service=gemini_service
    )
    logger.info("✅ Deal Evaluator service initialized")
except Exception as e:
    logger.warning(f"⚠️ Deal Evaluator service initialization failed: {e}")
    deal_evaluator_service = None

# PDF Service
try:
    from app.services.pdf_service import PDFService
    pdf_service = PDFService()
    logger.info("✅ PDF service initialized")
except Exception as e:
    logger.warning(f"⚠️ PDF service initialization failed: {e}")
    pdf_service = None

# User Service (Firebase Auth)
from app.services import user_service

# Credit Scoring Services
try:
    from app.services.xbrl_service import XBRLService
    from app.services.credit_signals_service import CreditSignalsService
    from app.services.operational_service import OperationalService
    from app.services.credit_qualitative_service import CreditQualitativeService
    from app.services.credit_score_service import CreditScoreService

    xbrl_service = XBRLService()
    credit_signals_service = CreditSignalsService(db_service=db_service)
    operational_service = OperationalService(bts_service=bts_service)
    credit_qualitative_service = CreditQualitativeService(
        gemini_service=gemini_service,
        db_service=db_service
    )
    credit_score_service = CreditScoreService(
        db_service=db_service,
        xbrl_service=xbrl_service,
        signals_service=credit_signals_service,
        operational_service=operational_service,
        qualitative_service=credit_qualitative_service
    )
    logger.info("✅ Credit Scoring services initialized")
except Exception as e:
    logger.warning(f"⚠️ Credit Scoring service initialization failed: {e}")
    credit_score_service = None
    xbrl_service = None
    operational_service = None

# Backtesting Services
try:
    from app.services.backtest_data_service import BacktestDataService
    from app.services.backtest_runner import BacktestRunner
    from app.services.backtest_optimizer import BacktestOptimizer
    from app.services.backtest_validation import BacktestValidation
    from app.services.backtest_report import BacktestReport

    backtest_data_service = BacktestDataService(
        xbrl_service=xbrl_service,
        db_service=db_service
    )
    backtest_runner = BacktestRunner(
        credit_score_service=credit_score_service,
        backtest_data_service=backtest_data_service,
        db_service=db_service
    )
    backtest_optimizer = BacktestOptimizer(
        backtest_runner=backtest_runner,
        db_service=db_service
    )
    backtest_validation = BacktestValidation(
        backtest_runner=backtest_runner,
        backtest_data_service=backtest_data_service,
        db_service=db_service
    )
    backtest_report = BacktestReport(
        backtest_runner=backtest_runner,
        backtest_optimizer=backtest_optimizer,
        backtest_validation=backtest_validation,
        db_service=db_service
    )
    logger.info("✅ Backtesting services initialized")
except Exception as e:
    logger.warning(f"⚠️ Backtesting service initialization failed: {e}")
    backtest_data_service = None
    backtest_runner = None
    backtest_optimizer = None
    backtest_validation = None
    backtest_report = None

import uuid
from flask import g

@app.before_request
def before_request():
    """Record request start time and generate request ID for tracking"""
    g.request_id = str(uuid.uuid4())[:8]
    g.start_time = datetime.now()
    if monitor:
        request.start_time = g.start_time

@app.after_request
def after_request(response):
    """Record request metrics, add headers, and log completed requests"""
    duration_ms = (datetime.now() - getattr(g, 'start_time', datetime.now())).total_seconds() * 1000

    # Add request ID to response headers for debugging
    if hasattr(g, 'request_id'):
        response.headers['X-Request-ID'] = g.request_id

    # Record monitoring metrics
    if monitor and hasattr(request, 'start_time'):
        monitor.record_request(request.path, response.status_code, duration_ms)

    # Log request (skip health checks to reduce noise)
    if request.path not in ('/health', '/ready'):
        logger.info(
            f"[{getattr(g, 'request_id', 'N/A')}] {request.method} {request.path} "
            f"-> {response.status_code} ({duration_ms:.1f}ms)"
        )

    return response

@app.route('/')
@limiter.exempt
def root():
    """
    API Root - Service information and endpoint listing
    ---
    tags:
      - Health
    responses:
      200:
        description: Service information
    """
    return jsonify({
        'service': 'Aviation Intelligence Platform API',
        'status': 'operational',
        'version': '2.1.0',
        'api_version': 'v1',
        'documentation': '/api/docs',
        'features': {
            'live_fred_data': fred_service is not None,
            'live_tsa_data': tsa_service is not None,
            'monitoring': 'enhanced' if monitor else 'basic',
            'news_ingestion': news_service is not None,
            'firestore_database': db_service is not None,
            'ai_insights': insights_service is not None,
            'credit_scoring': credit_score_service is not None
        },
        'endpoints': {
            'health': '/health',
            'ready': '/ready',
            'status': '/api/v1/status',
            'docs': '/api/docs',
            'market_data': '/api/v1/credit-spread/current, /api/v1/tsa/current',
            'news': '/api/v1/news/articles',
            'reports': '/api/v1/reports',
            'credit_scores': '/api/v1/credit-scores',
            'deals': '/api/v1/deals/evaluate'
        },
        'authentication': {
            'type': 'API Key',
            'header': 'X-API-Key',
            'required_for': 'Most write operations and data access'
        }
    })

@app.route('/health')
@limiter.exempt
def health():
    """
    Basic health check - Is the service running?
    ---
    tags:
      - Health
    responses:
      200:
        description: Service is healthy
        schema:
          type: object
          properties:
            status:
              type: string
              example: healthy
            service:
              type: string
            timestamp:
              type: string
              format: date-time
    """
    return jsonify({
        'status': 'healthy',
        'service': 'aviation-intelligence-api',
        'version': '2.1.0',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/ready')
@limiter.exempt
def ready():
    """
    Readiness check - Can the service handle requests?
    Verifies database and critical service availability.
    ---
    tags:
      - Health
    responses:
      200:
        description: Service is ready
      503:
        description: Service not ready (dependency unavailable)
    """
    checks = {
        'database': db_service is not None,
        'fred_service': fred_service is not None,
        'tsa_service': tsa_service is not None,
        'credit_scoring': credit_score_service is not None
    }

    # Quick database connectivity test
    if db_service:
        try:
            db_service.db.collection('config').document('health_check').get()
            checks['database_connected'] = True
        except Exception:
            checks['database_connected'] = False

    all_ready = checks.get('database', False) and checks.get('database_connected', False)
    status_code = 200 if all_ready else 503

    return jsonify({
        'status': 'ready' if all_ready else 'not_ready',
        'checks': {k: 'ok' if v else 'failed' for k, v in checks.items()},
        'timestamp': datetime.now().isoformat()
    }), status_code


@app.route('/api/status')
@app.route('/api/v1/status')
@limiter.limit(RATE_TIERS['public'])
def api_status():
    """
    API status with service details
    ---
    tags:
      - Health
    responses:
      200:
        description: Detailed API status
    """
    return jsonify({
        'status': 'operational',
        'service': 'Aviation Intelligence Platform API',
        'version': '2.1.0',
        'api_version': 'v1',
        'platform': 'Google Cloud Run',
        'documentation': '/api/docs',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'fred_service': 'active' if fred_service else 'fallback',
            'tsa_service': 'active' if tsa_service else 'fallback',
            'monitoring': 'active' if monitor else 'disabled',
            'news_service': 'active' if news_service else 'disabled',
            'database': 'active' if db_service else 'disabled',
            'credit_scoring': 'active' if credit_score_service else 'disabled',
            'deal_evaluator': 'active' if deal_evaluator_service else 'disabled'
        }
    })

@app.route('/api/credit-spread/current')
@limiter.limit(RATE_TIERS['public'])
def get_credit_spread():
    """
    Get current FRED credit spread data
    ---
    tags:
      - Market Data
    summary: Federal Reserve credit spread data
    description: Returns current corporate bond vs treasury spread from FRED
    responses:
      200:
        description: Credit spread data
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                credit_spread_bps:
                  type: integer
                  description: Spread in basis points
                spread_description:
                  type: string
                risk_level:
                  type: string
                  enum: [low, moderate, elevated, high]
            timestamp:
              type: string
              format: date-time
      503:
        description: Service unavailable
    """
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

    with PipelineTracker("news_ingestion", trigger="api", db_service=db_service) as tracker:
        try:
            if not news_service:
                tracker.record_error("news_service", "unavailable", "News ingestion service not available")
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

            # Record summary for pipeline tracking
            tracker.set_summary(
                items_processed=stats['articles_processed'],
                items_new=stats['articles_saved'],
                items_skipped=stats['articles_skipped'],
                sources_processed=stats['sources_processed']
            )

            # Record error count from stats
            error_count = stats.get('errors', 0)
            if error_count > 0:
                tracker.record_error("source", "ingestion_error", f"{error_count} error(s) during ingestion")

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
            tracker.record_error("pipeline", "unhandled_exception", str(e))
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
@require_auth
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
@require_auth
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
@require_auth
@require_role('admin')
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
@require_auth
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


@app.route('/api/reports/<report_id>/pdf', methods=['GET'])
def get_report_pdf(report_id):
    """
    Generate and download PDF for an airline intelligence report.

    This endpoint is public (no API key required) since the report data
    is already accessible via GET /api/reports/<id>.

    Returns:
        PDF file download with Content-Disposition header
    """
    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available'
            }), 503

        if not pdf_service:
            return jsonify({
                'success': False,
                'error': 'PDF service not available'
            }), 503

        # Fetch the report
        report = db_service.get_airline_report(report_id)
        if not report:
            return jsonify({
                'success': False,
                'error': 'Report not found'
            }), 404

        # Generate PDF
        logger.info(f"📄 Generating PDF for report: {report_id}")
        pdf_bytes = pdf_service.generate_airline_report_pdf(report)

        # Generate filename
        subject = report.get('subject', 'Report').replace(' ', '_').replace('/', '-')
        report_type = report.get('report_type', 'Analysis').replace('_', ' ').title().replace(' ', '_')
        date_str = datetime.now().strftime('%Y-%m-%d')
        filename = f"{subject}_{report_type}_{date_str}.pdf"

        return send_file(
            BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"❌ PDF generation failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
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

    with PipelineTracker("newsletter_generation", trigger="api", db_service=db_service) as tracker:
        try:
            if not insights_service:
                tracker.record_error("insights_service", "unavailable", "AI insights service not available")
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
                tracker.record_error("newsletter", "generation_failed", "Failed to generate newsletter")
                return jsonify({
                    'success': False,
                    'error': 'Failed to generate newsletter',
                    'timestamp': datetime.now().isoformat()
                }), 500

            # Record summary for pipeline tracking
            tracker.set_summary(
                newsletter_id=newsletter['id'],
                articles_analyzed=newsletter.get('articles_analyzed', 0),
                sections_generated=len(newsletter.get('sections', {})),
                frequency=frequency,
                format=format_type
            )

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
            tracker.record_error("pipeline", "unhandled_exception", str(e))
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


# ============================================================
# Weekly Outlook Pre-Generation (Scheduled Job)
# ============================================================

@app.route('/api/outlook/pre-generate', methods=['POST'])
@require_api_key
def pre_generate_weekly_outlook():
    """
    Pre-generate all Weekly Outlook AI content and cache in database.
    Called by Cloud Scheduler after daily news ingestion completes.

    This endpoint generates fresh content for:
    - Executive Summary
    - Investment Themes
    - Strategic Recommendations
    - Catalysts

    All content is cached in Firestore for instant retrieval by the frontend.
    ---
    tags:
      - Weekly Outlook
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: All content pre-generated successfully
      500:
        description: Pre-generation failed
      503:
        description: Insights service not available
    """
    start_time = datetime.now()

    # Use PipelineTracker for monitoring
    with PipelineTracker("outlook_pre_generation", trigger="api", db_service=db_service) as tracker:
        results = {}

        try:
            if not insights_service:
                tracker.record_error("pre_generation", "service_unavailable", "Insights service not available")
                return jsonify({
                    'success': False,
                    'error': 'Insights service not available',
                    'timestamp': datetime.now().isoformat()
                }), 503

            # 1. Generate Executive Summary (force fresh, bypass cache)
            logger.info("📋 Pre-generating executive summary...")
            try:
                summary = insights_service.generate_executive_summary(use_cache=False)
                results['executive_summary'] = 'success' if summary else 'failed'
                if not summary:
                    tracker.record_error("executive_summary", "generation_failed", "Gemini returned empty response")
            except Exception as e:
                results['executive_summary'] = 'failed'
                tracker.record_error("executive_summary", "exception", str(e))
                logger.error(f"❌ Executive summary generation failed: {e}")

            # 2. Generate Investment Themes
            logger.info("💡 Pre-generating investment themes...")
            try:
                themes = insights_service.generate_investment_themes(use_cache=False)
                results['investment_themes'] = len(themes) if themes else 0
                if not themes:
                    tracker.record_error("investment_themes", "generation_failed", "Gemini returned empty response")
            except Exception as e:
                results['investment_themes'] = 0
                tracker.record_error("investment_themes", "exception", str(e))
                logger.error(f"❌ Investment themes generation failed: {e}")

            # 3. Generate Strategic Recommendations
            logger.info("📊 Pre-generating strategic recommendations...")
            try:
                recs = insights_service.generate_strategic_recommendations(use_cache=False)
                results['recommendations'] = 'success' if recs else 'failed'
                if not recs:
                    tracker.record_error("recommendations", "generation_failed", "Gemini returned empty response")
            except Exception as e:
                results['recommendations'] = 'failed'
                tracker.record_error("recommendations", "exception", str(e))
                logger.error(f"❌ Strategic recommendations generation failed: {e}")

            # 4. Generate Catalysts (longer cache - 7 days)
            logger.info("📅 Pre-generating catalysts...")
            try:
                catalysts = insights_service.generate_catalysts(use_cache=False)
                results['catalysts'] = len(catalysts) if catalysts else 0
                if not catalysts:
                    tracker.record_error("catalysts", "generation_failed", "Gemini returned empty response")
            except Exception as e:
                results['catalysts'] = 0
                tracker.record_error("catalysts", "exception", str(e))
                logger.error(f"❌ Catalysts generation failed: {e}")

            response_time = (datetime.now() - start_time).total_seconds() * 1000

            # Determine overall status
            all_success = all(v not in ['failed', 0] for v in results.values())
            partial_success = any(v not in ['failed', 0] for v in results.values())

            tracker.set_summary(
                sections_generated=4,
                themes_count=results.get('investment_themes', 0),
                catalysts_count=results.get('catalysts', 0),
                status='success' if all_success else ('partial' if partial_success else 'failed')
            )

            logger.info(f"✅ Weekly outlook pre-generation completed: {results}")

            return jsonify({
                'success': all_success or partial_success,
                'results': results,
                'message': 'Weekly outlook content pre-generated and cached',
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            }), 200

        except Exception as e:
            logger.error(f"❌ Weekly outlook pre-generation failed: {e}")
            tracker.record_error("pre_generation", "exception", str(e))
            return jsonify({
                'success': False,
                'error': str(e),
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
@require_api_key
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

    with PipelineTracker("financial_data", trigger="api", db_service=db_service) as tracker:
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
            tracker.record_error("fred", "ingestion_error", str(e))
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
                    tracker.record_error("carrier_financials", "ingestion_error", f"{airline}: {str(e)}")
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
            tracker.record_error("tsa", "ingestion_error", str(e))
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
                    tracker.record_error("bts", "ingestion_error", f"{airline}: {str(e)}")
                    logger.error(f"❌ BTS ingestion error for {airline}: {e}")
        else:
            results['bts_data'] = {'status': 'service_unavailable'}

        # Calculate response time and finalize
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        results['response_time_ms'] = round(response_time, 1)
        results['success'] = len(results['errors']) == 0

        # Record summary for pipeline tracking
        fred_ok = 1 if results.get('fred_data', {}).get('status') == 'success' else 0
        tsa_ok = 1 if results.get('tsa_data', {}).get('status') == 'success' else 0
        carrier_ok = sum(1 for v in results.get('carrier_financials', {}).values() if v == 'success')
        bts_ok = sum(1 for v in results.get('bts_data', {}).values() if v == 'success')

        tracker.set_summary(
            fred_success=fred_ok,
            tsa_success=tsa_ok,
            carriers_success=carrier_ok,
            bts_success=bts_ok,
            total_errors=len(results['errors'])
        )

        logger.info(f"📊 Financial data ingestion complete in {response_time:.1f}ms - {len(results['errors'])} errors")

        return jsonify(results)


@app.route('/api/ingest/status', methods=['GET'])
@require_auth_or_api_key
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
@require_api_key
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

    with PipelineTracker("defense_contracts", trigger="api", db_service=db_service) as tracker:
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
                    tracker.record_error("contract_save", "database_error", f"{contract.get('contractor', 'Unknown')}: {str(e)}")

            # Generate summary
            summary = defense_contracts_handler.get_aviation_contract_summary(contracts)

            response_time = (datetime.now() - start_time).total_seconds() * 1000

            # Record summary for pipeline tracking
            tracker.set_summary(
                items_fetched=len(contracts),
                items_new=saved_count,
                items_skipped=duplicate_count,
                errors_count=len(errors)
            )

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
            tracker.record_error("pipeline", "unhandled_exception", str(e))
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


# ========== DEAL EVALUATOR ENDPOINTS ==========

@app.route('/api/deals/aircraft-types', methods=['GET'])
def get_aircraft_types():
    """
    Get list of supported aircraft types with valuation data.
    Fetches from database if available, otherwise uses defaults.
    """
    start_time = datetime.now()

    try:
        if deal_evaluator_service:
            aircraft_types = deal_evaluator_service.get_aircraft_types_list()
        else:
            # Fallback to default data
            from app.services.deal_evaluator_service import DEFAULT_AIRCRAFT_DATA
            aircraft_types = [
                {
                    'type': aircraft_type,
                    'residual_base': data['residual_base'],
                    'half_life': data['half_life'],
                    'new_price': data['new_price']
                }
                for aircraft_type, data in DEFAULT_AIRCRAFT_DATA.items()
            ]

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'aircraft_types': aircraft_types,
            'count': len(aircraft_types),
            'data_source': 'database' if deal_evaluator_service and deal_evaluator_service.db_service else 'defaults',
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error fetching aircraft types: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/deals/credit-tiers', methods=['GET'])
def get_credit_tiers():
    """
    Get credit tiers with LIVE FRED-adjusted hurdle rates.
    Hurdle rates are calculated from current Treasury yields and market spreads.
    """
    start_time = datetime.now()

    try:
        if deal_evaluator_service:
            credit_tiers = deal_evaluator_service.get_credit_tiers_with_hurdles()
        else:
            # Fallback to static tiers
            from app.services.deal_evaluator_service import TIER_SPREADS
            credit_tiers = [
                {
                    'tier': tier_name,
                    'label': tier_info['label'],
                    'color': tier_info['color'],
                    'spread_bps': tier_info['spread_bps'],
                    'hurdle_rate': 4.5 + tier_info['spread_bps'] / 100,  # Fallback calculation
                    'data_source': 'fallback'
                }
                for tier_name, tier_info in TIER_SPREADS.items()
            ]

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'credit_tiers': credit_tiers,
            'count': len(credit_tiers),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error fetching credit tiers: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/deals/lessee-profile/<name>', methods=['GET'])
def get_lessee_profile(name):
    """
    Auto-detect lessee credit tier from airline financials.
    Uses Yahoo Finance to fetch balance sheet data and estimate credit rating.

    Args:
        name: Airline name (URL-encoded, e.g., "United%20Airlines")
    """
    start_time = datetime.now()

    try:
        if not deal_evaluator_service:
            return jsonify({
                'success': False,
                'error': 'Deal evaluator service not available'
            }), 503

        result = deal_evaluator_service.auto_detect_credit_tier(name)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': result.get('tier') is not None,
            'lessee_name': name,
            'profile': result,
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error fetching lessee profile for {name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/deals/evaluate', methods=['POST'])
@require_auth
def evaluate_deal():
    """
    Evaluate a deal - calculate IRR, NPV, verdict, sensitivity.

    Request body:
    {
        "aircraft_type": "A320neo",
        "current_age": 3.5,
        "lease_term": 8,
        "monthly_rent": 320000,
        "step_up_pct": 2.0,
        "maintenance_reserve": 35000,
        "transition_cost": 500000,
        "purchase_price": 45000000,
        "residual_value": null,  // Optional, auto-calculated if not provided
        "credit_tier": "BBB/BBB-",
        "lessee_name": "United Airlines",
        "include_ai_commentary": true
    }
    """
    start_time = datetime.now()

    try:
        if not deal_evaluator_service:
            return jsonify({
                'success': False,
                'error': 'Deal evaluator service not available'
            }), 503

        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        # Validate required fields
        required_fields = ['aircraft_type', 'current_age', 'lease_term', 'monthly_rent', 'purchase_price', 'credit_tier']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        # Build params dict
        params = {
            'aircraft_type': data['aircraft_type'],
            'current_age': float(data['current_age']),
            'lease_term': int(data['lease_term']),
            'monthly_rent': float(data['monthly_rent']),
            'step_up_pct': float(data.get('step_up_pct', 0)),
            'maintenance_reserve': float(data.get('maintenance_reserve', 0)),
            'transition_cost': float(data.get('transition_cost', 0)),
            'purchase_price': float(data['purchase_price']),
            'credit_tier': data['credit_tier'],
            'lessee_name': data.get('lessee_name', 'Unknown')
        }

        # Add residual if provided
        if data.get('residual_value'):
            params['residual_value'] = float(data['residual_value'])

        # Evaluate the deal
        logger.info(f"📊 Evaluating deal: {params['aircraft_type']} for {params['lessee_name']}")
        results = deal_evaluator_service.evaluate_deal(params)

        # Generate AI commentary if requested
        if data.get('include_ai_commentary', False):
            commentary = deal_evaluator_service.generate_deal_commentary(params, results)
            results['ai_commentary'] = commentary

        # Save to database if requested
        if data.get('save', False) and db_service:
            evaluation_data = {
                'mode': 'evaluate',
                'params': params,
                'results': {k: v for k, v in results.items() if k != 'sensitivity_matrix'},  # Exclude large matrix
                'ai_commentary': results.get('ai_commentary')
            }
            results['evaluation_id'] = db_service.save_deal_evaluation(evaluation_data)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'mode': 'evaluate',
            'results': results,
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"❌ Deal evaluation failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/deals/price', methods=['POST'])
@require_auth
def price_deal():
    """
    Price a deal - solve for max purchase price given target IRR.

    Request body:
    {
        "aircraft_type": "A320neo",
        "current_age": 3.5,
        "lease_term": 8,
        "monthly_rent": 320000,
        "step_up_pct": 2.0,
        "maintenance_reserve": 35000,
        "transition_cost": 500000,
        "target_irr": 8.5,  // As percentage
        "residual_value": null,  // Optional, auto-calculated if not provided
        "credit_tier": "BBB/BBB-",
        "lessee_name": "United Airlines",
        "include_ai_commentary": true
    }
    """
    start_time = datetime.now()

    try:
        if not deal_evaluator_service:
            return jsonify({
                'success': False,
                'error': 'Deal evaluator service not available'
            }), 503

        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        # Validate required fields
        required_fields = ['aircraft_type', 'current_age', 'lease_term', 'monthly_rent', 'target_irr', 'credit_tier']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        # Build params dict
        params = {
            'aircraft_type': data['aircraft_type'],
            'current_age': float(data['current_age']),
            'lease_term': int(data['lease_term']),
            'monthly_rent': float(data['monthly_rent']),
            'step_up_pct': float(data.get('step_up_pct', 0)),
            'maintenance_reserve': float(data.get('maintenance_reserve', 0)),
            'transition_cost': float(data.get('transition_cost', 0)),
            'target_irr': float(data['target_irr']),
            'credit_tier': data['credit_tier'],
            'lessee_name': data.get('lessee_name', 'Unknown')
        }

        # Add residual if provided
        if data.get('residual_value'):
            params['residual_value'] = float(data['residual_value'])

        # Price the deal
        logger.info(f"💰 Pricing deal: {params['aircraft_type']} for {params['lessee_name']} @ {params['target_irr']}% IRR")
        results = deal_evaluator_service.price_deal(params)

        # Generate AI commentary if requested
        if data.get('include_ai_commentary', False):
            commentary = deal_evaluator_service.generate_deal_commentary(params, results)
            results['ai_commentary'] = commentary

        # Save to database if requested
        if data.get('save', False) and db_service:
            evaluation_data = {
                'mode': 'price',
                'params': params,
                'results': {k: v for k, v in results.items() if k != 'sensitivity_matrix'},
                'ai_commentary': results.get('ai_commentary')
            }
            results['evaluation_id'] = db_service.save_deal_evaluation(evaluation_data)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'mode': 'price',
            'results': results,
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"❌ Deal pricing failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/deals/evaluate/pdf', methods=['POST'])
@require_auth
def evaluate_deal_pdf():
    """
    Evaluate a deal and return PDF instead of JSON.

    Same request body as POST /api/deals/evaluate.
    Returns PDF file download.
    """
    try:
        if not deal_evaluator_service:
            return jsonify({
                'success': False,
                'error': 'Deal evaluator service not available'
            }), 503

        if not pdf_service:
            return jsonify({
                'success': False,
                'error': 'PDF service not available'
            }), 503

        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        # Validate required fields
        required_fields = ['aircraft_type', 'purchase_price', 'credit_tier']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        # Build params dict - handle both field naming conventions
        params = {
            'aircraft_type': data['aircraft_type'],
            'current_age': float(data.get('current_age', data.get('aircraft_age', 0))),
            'lease_term': int(data.get('lease_term', data.get('lease_term_years', 8))),
            'monthly_rent': float(data.get('monthly_rent', 0)),
            'step_up_pct': float(data.get('step_up_pct', 0)),
            'maintenance_reserve': float(data.get('maintenance_reserve', data.get('monthly_maintenance_reserve', 0))),
            'transition_cost': float(data.get('transition_cost', 0)),
            'purchase_price': float(data['purchase_price']),
            'credit_tier': data['credit_tier'],
            'lessee_name': data.get('lessee_name', 'Unknown')
        }

        # Add residual if provided
        if data.get('residual_value'):
            params['residual_value'] = float(data['residual_value'])

        # Evaluate the deal
        logger.info(f"📄 Generating PDF for deal evaluation: {params['aircraft_type']} for {params['lessee_name']}")
        results = deal_evaluator_service.evaluate_deal(params)

        # Generate PDF
        pdf_bytes = pdf_service.generate_deal_memo_pdf(params, results, mode='evaluate')

        # Generate filename
        aircraft = params['aircraft_type'].replace(' ', '_').replace('/', '-')
        date_str = datetime.now().strftime('%Y-%m-%d')
        filename = f"{aircraft}_Deal_Memo_{date_str}.pdf"

        return send_file(
            BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"❌ Deal evaluation PDF failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/deals/price/pdf', methods=['POST'])
@require_auth
def price_deal_pdf():
    """
    Price a deal and return PDF instead of JSON.

    Same request body as POST /api/deals/price.
    Returns PDF file download.
    """
    try:
        if not deal_evaluator_service:
            return jsonify({
                'success': False,
                'error': 'Deal evaluator service not available'
            }), 503

        if not pdf_service:
            return jsonify({
                'success': False,
                'error': 'PDF service not available'
            }), 503

        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        # Validate required fields
        required_fields = ['aircraft_type', 'target_irr', 'credit_tier']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        # Build params dict
        params = {
            'aircraft_type': data['aircraft_type'],
            'current_age': float(data.get('current_age', data.get('aircraft_age', 0))),
            'lease_term': int(data.get('lease_term', data.get('lease_term_years', 8))),
            'monthly_rent': float(data.get('monthly_rent', 0)),
            'step_up_pct': float(data.get('step_up_pct', 0)),
            'maintenance_reserve': float(data.get('maintenance_reserve', data.get('monthly_maintenance_reserve', 0))),
            'transition_cost': float(data.get('transition_cost', 0)),
            'target_irr': float(data['target_irr']),
            'credit_tier': data['credit_tier'],
            'lessee_name': data.get('lessee_name', 'Unknown')
        }

        # Add residual if provided
        if data.get('residual_value'):
            params['residual_value'] = float(data['residual_value'])

        # Price the deal
        logger.info(f"📄 Generating PDF for deal pricing: {params['aircraft_type']} for {params['lessee_name']}")
        results = deal_evaluator_service.price_deal(params)

        # Generate PDF
        pdf_bytes = pdf_service.generate_deal_memo_pdf(params, results, mode='price')

        # Generate filename
        aircraft = params['aircraft_type'].replace(' ', '_').replace('/', '-')
        date_str = datetime.now().strftime('%Y-%m-%d')
        filename = f"{aircraft}_Pricing_Memo_{date_str}.pdf"

        return send_file(
            BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"❌ Deal pricing PDF failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/deals/history', methods=['GET'])
def get_deal_history():
    """
    Get recent saved deal evaluations.

    Query params:
        - aircraft_type: Filter by aircraft type
        - lessee_name: Filter by lessee name
        - mode: Filter by mode ('evaluate' or 'price')
        - limit: Max results (default 50)
    """
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available'
            }), 503

        # Get query params
        aircraft_type = request.args.get('aircraft_type')
        lessee_name = request.args.get('lessee_name')
        mode = request.args.get('mode')
        limit = int(request.args.get('limit', 50))

        evaluations = db_service.get_deal_evaluations(
            aircraft_type=aircraft_type,
            lessee_name=lessee_name,
            mode=mode,
            limit=limit
        )

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'evaluations': evaluations,
            'count': len(evaluations),
            'filters': {
                'aircraft_type': aircraft_type,
                'lessee_name': lessee_name,
                'mode': mode
            },
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error fetching deal history: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/deals/seed-defaults', methods=['POST'])
@require_auth
@require_role('admin')
def seed_aircraft_defaults():
    """
    Admin endpoint: Seed aircraft defaults to database.
    Run once to populate the aircraft_defaults collection.
    """
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available'
            }), 503

        # Get default aircraft data
        from app.services.deal_evaluator_service import DEFAULT_AIRCRAFT_DATA

        result = db_service.seed_aircraft_defaults(DEFAULT_AIRCRAFT_DATA)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': result.get('success', False),
            'result': result,
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error seeding aircraft defaults: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/deals/save', methods=['POST'])
@require_auth
def save_deal_evaluation():
    """
    Save a deal evaluation to history.

    Request body should contain the full evaluation data including params and results.
    """
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available'
            }), 503

        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        evaluation_id = db_service.save_deal_evaluation(data)

        if evaluation_id:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            return jsonify({
                'success': True,
                'evaluation_id': evaluation_id,
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save evaluation'
            }), 500

    except Exception as e:
        logger.error(f"❌ Error saving deal evaluation: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# ========== CREDIT SCORING ENDPOINTS ==========

@app.route('/api/credit-scores', methods=['GET'])
@limiter.limit(RATE_TIERS['auth_read'])
def get_all_credit_scores():
    """
    Get all airline credit scores
    ---
    tags:
      - Credit Scores
    summary: List all credit scores
    description: Returns current credit scores for all 8 tracked US airlines
    responses:
      200:
        description: List of credit scores
        schema:
          type: object
          properties:
            success:
              type: boolean
            scores:
              type: array
            count:
              type: integer
      503:
        description: Credit scoring service unavailable
    """
    start_time = datetime.now()

    try:
        if not credit_score_service:
            return jsonify({
                'success': False,
                'error': 'Credit scoring service not available'
            }), 503

        scores = credit_score_service.get_all_scores()
        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'scores': scores,
            'count': len(scores),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error fetching credit scores: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/credit-scores/<code>', methods=['GET'])
@limiter.limit(RATE_TIERS['auth_read'])
def get_credit_score(code):
    """
    Get credit score for a specific airline
    ---
    tags:
      - Credit Scores
    summary: Get airline credit score
    description: Returns full credit score breakdown including all 4 dimensions
    parameters:
      - name: code
        in: path
        type: string
        required: true
        description: Airline ticker
        enum: [DAL, UAL, AAL, LUV, JBLU, ALK, SAVE, ULCC]
    responses:
      200:
        description: Full credit score breakdown
      404:
        description: Airline not found or not yet scored
      503:
        description: Credit scoring service unavailable
    """
    start_time = datetime.now()

    try:
        if not credit_score_service:
            return jsonify({
                'success': False,
                'error': 'Credit scoring service not available'
            }), 503

        score = credit_score_service.get_score(code.upper())

        if not score:
            return jsonify({
                'success': False,
                'error': f'No credit score found for {code.upper()}. Run POST /api/credit-scores/{code}/refresh to generate.'
            }), 404

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'score': score,
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error fetching credit score for {code}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/credit-scores/<code>/refresh', methods=['POST'])
@require_auth
@require_role('admin')
def refresh_credit_score(code):
    """
    Trigger rescore for a single airline.

    Args:
        code: Airline ticker

    Optional query params:
        as_of_date: Date for backtesting (YYYY-MM-DD)
    """
    start_time = datetime.now()

    try:
        if not credit_score_service:
            return jsonify({
                'success': False,
                'error': 'Credit scoring service not available'
            }), 503

        as_of_date = request.args.get('as_of_date')

        logger.info(f"📊 Refreshing credit score for {code.upper()}")
        score = credit_score_service.calculate_credit_score(
            code.upper(),
            as_of_date=as_of_date
        )

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'score': score,
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"❌ Error refreshing credit score for {code}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/credit-scores/refresh-all', methods=['POST'])
@require_api_key
def refresh_all_credit_scores():
    """
    Trigger rescore for all airlines.

    Processes airlines with 2-second delay between each for SEC rate limiting.
    This endpoint may take 30-60 seconds to complete.
    """
    start_time = datetime.now()

    with PipelineTracker("credit_score_refresh", trigger="api", db_service=db_service) as tracker:
        try:
            if not credit_score_service:
                tracker.record_error("credit_score_service", "unavailable", "Credit scoring service not available")
                return jsonify({
                    'success': False,
                    'error': 'Credit scoring service not available'
                }), 503

            logger.info("📊 Refreshing all credit scores")
            results = credit_score_service.refresh_all_scores(delay_seconds=2.0)

            # Record summary for pipeline tracking
            airlines_processed = len(results.get('scores', {}))
            airlines_success = sum(1 for v in results.get('scores', {}).values() if v.get('success', False))
            airlines_failed = airlines_processed - airlines_success

            tracker.set_summary(
                airlines_processed=airlines_processed,
                airlines_success=airlines_success,
                airlines_failed=airlines_failed
            )

            # Record any errors from results
            for airline, score_result in results.get('scores', {}).items():
                if not score_result.get('success', False):
                    tracker.record_error("credit_score", "calculation_failed", f"{airline}: {score_result.get('error', 'Unknown error')}")

            response_time = (datetime.now() - start_time).total_seconds() * 1000

            return jsonify({
                'success': results['success'],
                'results': results,
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            })

        except Exception as e:
            tracker.record_error("pipeline", "unhandled_exception", str(e))
            logger.error(f"❌ Error refreshing all credit scores: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500


@app.route('/api/credit-scores/<code>/history', methods=['GET'])
def get_credit_score_history(code):
    """
    Get historical credit scores for trend analysis.

    Args:
        code: Airline ticker

    Query params:
        limit: Max records to return (default 52 for ~1 year weekly)
    """
    start_time = datetime.now()

    try:
        if not credit_score_service:
            return jsonify({
                'success': False,
                'error': 'Credit scoring service not available'
            }), 503

        limit = request.args.get('limit', 52, type=int)
        history = credit_score_service.get_score_history(code.upper(), limit=limit)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'airline_code': code.upper(),
            'history': history,
            'count': len(history),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error fetching credit score history for {code}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/deal-evaluator-overrides', methods=['POST'])
@require_auth
def log_deal_evaluator_override():
    """
    Log when user overrides hurdle rate from credit score default.
    Used for model validation and analytics.

    Body:
        - airline_code: str
        - suggested_hurdle_rate: float
        - user_override_rate: float
        - credit_score_at_time: float
        - letter_grade_at_time: str
        - deal_params: Dict (optional)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        if db_service:
            doc_id = db_service.log_hurdle_override(data)
            logger.info(f"📊 Logged hurdle override: {data.get('airline_code')} "
                       f"{data.get('suggested_hurdle_rate')} → {data.get('user_override_rate')}")
        else:
            doc_id = None
            logger.warning("⚠️ Database service not available for override logging")

        return jsonify({
            'success': True,
            'message': 'Override logged',
            'doc_id': doc_id,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"❌ Error logging deal evaluator override: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/credit-scores/seed-ratings', methods=['POST'])
@require_auth
@require_role('admin')
def seed_credit_ratings():
    """
    Seed initial published credit ratings for all airlines.

    This populates the airline_credit_ratings collection with current
    Moody's/S&P/Fitch ratings for the 8 airlines.
    """
    start_time = datetime.now()

    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Database service not available'
            }), 503

        # Current credit ratings as of Feb 2026 (to be updated as needed)
        ratings_data = {
            'DAL': {
                'airline_code': 'DAL',
                'airline_name': 'Delta Air Lines',
                'moodys': 'Baa2',
                'moodys_outlook': 'stable',
                'sp': 'BBB-',
                'sp_outlook': 'positive',
                'fitch': 'BBB-',
                'fitch_outlook': 'stable',
                'as_of_date': '2026-02-01'
            },
            'UAL': {
                'airline_code': 'UAL',
                'airline_name': 'United Airlines',
                'moodys': 'Baa3',
                'moodys_outlook': 'stable',
                'sp': 'BB+',
                'sp_outlook': 'positive',
                'fitch': 'BB+',
                'fitch_outlook': 'stable',
                'as_of_date': '2026-02-01'
            },
            'AAL': {
                'airline_code': 'AAL',
                'airline_name': 'American Airlines',
                'moodys': 'B1',
                'moodys_outlook': 'stable',
                'sp': 'B+',
                'sp_outlook': 'stable',
                'fitch': 'B+',
                'fitch_outlook': 'stable',
                'as_of_date': '2026-02-01'
            },
            'LUV': {
                'airline_code': 'LUV',
                'airline_name': 'Southwest Airlines',
                'moodys': 'Baa1',
                'moodys_outlook': 'stable',
                'sp': 'BBB',
                'sp_outlook': 'stable',
                'fitch': 'BBB',
                'fitch_outlook': 'stable',
                'as_of_date': '2026-02-01'
            },
            'JBLU': {
                'airline_code': 'JBLU',
                'airline_name': 'JetBlue Airways',
                'moodys': 'B1',
                'moodys_outlook': 'negative',
                'sp': 'B',
                'sp_outlook': 'stable',
                'fitch': 'B',
                'fitch_outlook': 'stable',
                'as_of_date': '2026-02-01'
            },
            'ALK': {
                'airline_code': 'ALK',
                'airline_name': 'Alaska Air Group',
                'moodys': 'Baa3',
                'moodys_outlook': 'stable',
                'sp': 'BB+',
                'sp_outlook': 'positive',
                'fitch': 'BBB-',
                'fitch_outlook': 'stable',
                'as_of_date': '2026-02-01'
            },
            'SAVE': {
                'airline_code': 'SAVE',
                'airline_name': 'Spirit Airlines',
                'moodys': 'Caa2',
                'moodys_outlook': 'negative',
                'sp': 'CCC',
                'sp_outlook': 'negative',
                'fitch': 'CCC',
                'fitch_outlook': 'negative',
                'as_of_date': '2026-02-01'
            },
            'ULCC': {
                'airline_code': 'ULCC',
                'airline_name': 'Frontier Group',
                'moodys': 'B3',
                'moodys_outlook': 'stable',
                'sp': 'B-',
                'sp_outlook': 'stable',
                'fitch': 'B-',
                'fitch_outlook': 'stable',
                'as_of_date': '2026-02-01'
            }
        }

        seeded = []
        errors = []

        for code, rating_data in ratings_data.items():
            try:
                db_service.save_published_rating(rating_data)
                seeded.append(code)
            except Exception as e:
                errors.append({'code': code, 'error': str(e)})

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': len(errors) == 0,
            'seeded': seeded,
            'errors': errors,
            'count': len(seeded),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error seeding credit ratings: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# ========== BACKTESTING ENDPOINTS ==========

@app.route('/api/credit-scores/backtest/collect-data', methods=['POST'])
@require_auth
@require_role('admin')
@limiter.limit(RATE_TIERS['heavy'])
def collect_backtest_data():
    """
    Collect historical backtest data
    ---
    tags:
      - Backtesting
    summary: Collect historical data for backtesting
    description: |
      Collects historical financial data from SEC EDGAR and stock data from Yahoo Finance
      for all 8 tracked airlines. This is a heavy operation - rate limited to 5/min.
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: Data collection summary
      401:
        description: Authentication required
      429:
        description: Rate limit exceeded (5/min)
      503:
        description: Backtest service unavailable

    Returns: Summary of data collected per airline
    """
    start_time = datetime.now()

    try:
        if not backtest_data_service:
            return jsonify({
                'success': False,
                'error': 'Backtest data service not available'
            }), 503

        start_year = request.json.get('start_year', 2015) if request.json else 2015

        logger.info(f"📊 Starting backtest data collection from {start_year}...")
        results = backtest_data_service.collect_all_historical_data(start_year=start_year)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': results.get('success', False),
            'results': results,
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error collecting backtest data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/credit-scores/backtest/run', methods=['POST'])
@require_auth
@require_role('admin')
@limiter.limit(RATE_TIERS['heavy'])
def run_backtest():
    """
    Run credit model backtest
    ---
    tags:
      - Backtesting
    summary: Run full backtest
    description: |
      Runs retrospective credit scoring across all airlines for specified date range.
      Heavy computation - rate limited to 5/min.
    security:
      - ApiKeyAuth: []
    parameters:
      - name: body
        in: body
        schema:
          type: object
          properties:
            weights:
              type: object
              description: Weight overrides
            start_year:
              type: integer
              default: 2015
            end_year:
              type: integer
    responses:
      200:
        description: Backtest results with metrics
      401:
        description: Authentication required
      429:
        description: Rate limit exceeded (5/min)
      503:
        description: Service unavailable
    """
    start_time = datetime.now()

    try:
        if not backtest_runner:
            return jsonify({
                'success': False,
                'error': 'Backtest runner service not available'
            }), 503

        data = request.get_json() or {}
        weights = data.get('weights')
        start_year = data.get('start_year', 2015)
        end_year = data.get('end_year')

        logger.info(f"📊 Running backtest {start_year}-{end_year or 'present'}...")
        results = backtest_runner.run_full_backtest(
            weights=weights,
            start_year=start_year,
            end_year=end_year
        )

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'run_id': results.get('run_id'),
            'summary_metrics': results.get('summary_metrics'),
            'airline_summaries': results.get('airline_summaries'),
            'total_observations': results.get('total_observations'),
            'weights_used': results.get('weights'),
            'date_range': results.get('date_range'),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error running backtest: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/credit-scores/backtest/optimize', methods=['POST'])
@require_auth
@require_role('admin')
def optimize_weights():
    """
    Run weight optimization via grid search.
    This is computationally intensive and may take 2-5 minutes.

    Body (optional):
        - start_year: Start year (default 2015)
        - end_year: End year
        - quick: Boolean - if True, use quick optimization (fewer samples, faster)

    Returns: Optimal weights and all tested combinations
    """
    start_time = datetime.now()

    try:
        if not backtest_optimizer:
            return jsonify({
                'success': False,
                'error': 'Backtest optimizer service not available'
            }), 503

        data = request.get_json() or {}
        start_year = data.get('start_year', 2015)
        end_year = data.get('end_year')
        quick_mode = data.get('quick', False)

        logger.info(f"📊 Running weight optimization (quick={quick_mode})...")

        if quick_mode:
            results = backtest_optimizer.quick_optimize(
                start_year=max(2018, start_year),
                end_year=end_year,
                sample_size=data.get('sample_size', 15)
            )
        else:
            results = backtest_optimizer.optimize_weights(
                start_year=start_year,
                end_year=end_year
            )

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': results.get('success', False),
            'optimal_weights': results.get('optimal_weights'),
            'optimal_score': results.get('optimal_score'),
            'optimal_combined_score': results.get('optimal_combined_score'),
            'top_5_configs': results.get('top_5_configs'),
            'total_combinations_tested': results.get('total_combinations_tested') or results.get('combinations_tested'),
            'runtime_seconds': results.get('runtime_seconds'),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error running weight optimization: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/credit-scores/backtest/validate', methods=['POST'])
@require_auth
@require_role('admin')
def run_validation():
    """
    Run validation suite with named test cases.

    Body (optional):
        - weights: Dict with weight overrides

    Returns: Pass/fail report for all validation cases
    """
    start_time = datetime.now()

    try:
        if not backtest_validation:
            return jsonify({
                'success': False,
                'error': 'Backtest validation service not available'
            }), 503

        data = request.get_json() or {}
        weights = data.get('weights')

        logger.info("📊 Running validation suite...")
        results = backtest_validation.run_validation_suite(weights=weights)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'validation_id': results.get('validation_id'),
            'total_cases': results.get('total_cases'),
            'passed': results.get('passed'),
            'failed': results.get('failed'),
            'skipped': results.get('skipped'),
            'pass_rate': results.get('pass_rate'),
            'results': results.get('results'),
            'weights_used': results.get('weights_used'),
            'runtime_seconds': results.get('runtime_seconds'),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error running validation suite: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/credit-scores/backtest/report', methods=['GET'])
@require_auth
@require_role('admin')
def get_backtest_report():
    """
    Get the most recent comprehensive validation report.
    If no report exists, returns demo/static data for display.

    Returns: Full validation report (cached or demo)
    """
    start_time = datetime.now()

    try:
        # Try to get cached report first
        report = None
        if backtest_report:
            report = backtest_report.get_latest_report()

        # If no cached report, return demo data
        if not report:
            report = _get_demo_validation_report()

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'report': report,
            'is_demo': report.get('is_demo', False),
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error fetching backtest report: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


def _get_demo_validation_report():
    """Generate demo validation report data for display when no real report exists."""
    return {
        'is_demo': True,
        'report_title': 'Credit Scoring Model Validation Report',
        'report_id': 'demo_report',
        'generated_at': datetime.now().isoformat(),
        'model_version': '1.0',
        'executive_summary': {
            'total_observations': 280,
            'date_range': '2015-Q1 to 2024-Q4',
            'airlines_covered': 8,
            'rank_correlation_with_agencies': 0.82,
            'pre_distress_detection_rate': '78%',
            'validation_pass_rate': '89% (8/9 cases passed)',
            'conclusion': 'Model demonstrates strong alignment with credit agency ratings and reliable early detection of airline financial distress. Recommended for production use.'
        },
        'weight_calibration': {
            'initial_weights': {'financial': 0.44, 'signals': 0.25, 'operational': 0.31, 'qualitative': 0.0},
            'optimized_weights': {'financial': 0.45, 'signals': 0.28, 'operational': 0.27},
            'initial_spearman': 0.78,
            'optimized_spearman': 0.82,
            'improvement': 'Optimization improved rank correlation by +0.04',
            'note': 'Optimized weights are for quantitative dimensions only. Production weights include 20% qualitative weight.'
        },
        'airline_profiles': {
            'DAL': {'airline_name': 'Delta Air Lines', 'score_range': '62 – 88', 'current_score': 82.5, 'current_grade': 'A', 'trajectory': 'Stable with strong recovery from COVID lows', 'model_accuracy': 'Correctly tracked full recovery arc', 'observations': 40},
            'UAL': {'airline_name': 'United Airlines', 'score_range': '55 – 82', 'current_score': 76.3, 'current_grade': 'B+', 'trajectory': 'Improving trend post-merger integration', 'model_accuracy': 'No major credit events in period', 'observations': 40},
            'AAL': {'airline_name': 'American Airlines', 'score_range': '42 – 72', 'current_score': 61.8, 'current_grade': 'C+', 'trajectory': 'Recovering from high debt load', 'model_accuracy': 'Correctly tracked 2011-2013 bankruptcy period', 'observations': 40},
            'LUV': {'airline_name': 'Southwest Airlines', 'score_range': '68 – 92', 'current_score': 85.1, 'current_grade': 'A', 'trajectory': 'Consistently strong performer', 'model_accuracy': 'No major credit events', 'observations': 40},
            'JBLU': {'airline_name': 'JetBlue Airways', 'score_range': '48 – 74', 'current_score': 58.2, 'current_grade': 'C', 'trajectory': 'Declining due to merger uncertainty', 'model_accuracy': 'Detected merger stress signals', 'observations': 40},
            'ALK': {'airline_name': 'Alaska Air Group', 'score_range': '65 – 85', 'current_score': 78.4, 'current_grade': 'B+', 'trajectory': 'Stable with consistent margins', 'model_accuracy': 'No major credit events', 'observations': 40},
            'SAVE': {'airline_name': 'Spirit Airlines', 'score_range': '28 – 62', 'current_score': 32.1, 'current_grade': 'D', 'trajectory': 'Deteriorating - filed Chapter 11 in Nov 2024', 'model_accuracy': 'Detected pre-bankruptcy stress 5+ months early', 'observations': 40},
            'ULCC': {'airline_name': 'Frontier Group', 'score_range': '42 – 58', 'current_score': 48.5, 'current_grade': 'D+', 'trajectory': 'Volatile with ULCC industry challenges', 'model_accuracy': 'Limited history (IPO 2021)', 'observations': 16}
        },
        'key_findings': [
            'Strong rank correlation (0.82) with published credit ratings demonstrates model alignment with agency assessments.',
            'Model detected 78% of credit events in the quarter preceding the event, enabling early warning.',
            'Passed 89% of named validation cases, including Spirit bankruptcy detection and Delta recovery tracking.',
            'Spirit Airlines correctly flagged as distressed (score 32) prior to November 2024 bankruptcy filing.',
            'Model correctly captured industry-wide COVID-19 stress, with all airlines showing score deterioration in Q1/Q2 2020.',
            'Optimized weights: Financial 45%, Signals 28%, Operational 27%'
        ],
        'validation_cases': [
            {'name': 'Spirit Pre-Bankruptcy Detection', 'description': 'Score should be below 40 in 2024 Q2-Q3', 'passed': True, 'actual_value': 32, 'expected': '< 40', 'result_summary': 'Score 32, correctly flagged as distressed'},
            {'name': 'Spirit Deterioration Trend', 'description': 'Score should show declining trend 2022-2024', 'passed': True, 'result_summary': 'Clear downward trajectory from 58 to 32'},
            {'name': 'Delta Recovery Arc', 'description': 'Score should improve from 2020 lows to 2024', 'passed': True, 'result_summary': 'Recovery from 62 to 82.5'},
            {'name': 'Delta Strong Performer', 'description': 'Score should be above 75 in recent periods', 'passed': True, 'actual_value': 82.5, 'expected': '> 75'},
            {'name': 'Southwest Stability', 'description': 'Score should remain consistently above 70', 'passed': True, 'result_summary': 'Maintained 80+ score throughout period'},
            {'name': 'COVID Stress Test', 'description': 'All airlines should show decline in Q1-Q2 2020', 'passed': True, 'result_summary': '8/8 airlines showed score decline'},
            {'name': 'Rank Order Consistency', 'description': 'Model rankings should align with agency ratings', 'passed': True, 'result_summary': 'Spearman correlation 0.82'},
            {'name': 'JetBlue Merger Stress', 'description': 'Score should decline during merger uncertainty', 'passed': True, 'result_summary': 'Decline from 68 to 58 during 2023-2024'},
            {'name': 'American High Debt Flag', 'description': 'Score should reflect elevated debt concerns', 'passed': False, 'result_summary': 'Score at 61.8 vs expected < 55 for debt level'}
        ],
        'limitations': [
            'Backtesting covers quantitative dimensions only (70-80% of live model weight)',
            'Qualitative assessment (Gemini AI) is skipped in backtest mode',
            'BTS operational data has 2-3 month reporting lag in live scoring',
            'Credit rating history is manually compiled — some dates approximate',
            'Sample limited to 8 US airlines — not validated on international carriers',
            'COVID-19 period represents unprecedented systemic shock with limited predictive value',
            'Historical stock data may not be available for all periods (e.g., ULCC IPO 2021)',
            'SEC XBRL data availability varies by airline and filing history'
        ],
        'full_results': {
            'backtest_summary': {
                'spearman_rank_correlation': 0.82,
                'pre_event_detection_rate': 0.78,
                'false_positive_rate': 0.12
            },
            'optimization_summary': {
                'optimal_weights': {'financial': 0.45, 'signals': 0.28, 'operational': 0.27},
                'optimal_combined_score': 0.847,
                'combinations_tested': 84
            },
            'validation_summary': {
                'passed': 8,
                'failed': 1,
                'pass_rate': 0.89
            }
        },
        'report_metadata': {
            'date_range': '2015-Q1 to 2024-Q4',
            'airlines_covered': 8,
            'total_observations': 280,
            'generation_time_seconds': 0.1
        }
    }


def _run_report_generation_background(job_id: str, start_year: int, end_year: int, quick_mode: bool):
    """Background thread function to generate validation report."""
    global _background_jobs

    try:
        logger.info(f"🚀 Background job {job_id}: Starting report generation...")

        with _background_jobs_lock:
            _background_jobs[job_id]['status'] = 'running'
            _background_jobs[job_id]['started_at'] = datetime.now().isoformat()

        # Generate the report
        report = backtest_report.generate_validation_report(
            run_fresh=True,
            start_year=start_year,
            end_year=end_year
        )

        # Get text summary
        summary_text = backtest_report.get_report_summary(report)

        # Store result
        with _background_jobs_lock:
            _background_jobs[job_id]['status'] = 'completed'
            _background_jobs[job_id]['completed_at'] = datetime.now().isoformat()
            _background_jobs[job_id]['result'] = {
                'success': True,
                'report_id': report.get('report_id'),
                'executive_summary': report.get('executive_summary'),
                'key_findings': report.get('key_findings'),
                'validation_cases': report.get('validation_cases'),
                'weight_calibration': report.get('weight_calibration'),
                'airline_profiles': report.get('airline_profiles'),
                'limitations': report.get('limitations'),
                'full_results': report.get('full_results'),
                'report_metadata': report.get('report_metadata'),
                'summary_text': summary_text
            }

        logger.info(f"✅ Background job {job_id}: Report generation completed!")

    except Exception as e:
        logger.error(f"❌ Background job {job_id}: Error - {e}")
        import traceback
        logger.error(traceback.format_exc())

        with _background_jobs_lock:
            _background_jobs[job_id]['status'] = 'failed'
            _background_jobs[job_id]['completed_at'] = datetime.now().isoformat()
            _background_jobs[job_id]['error'] = str(e)


@app.route('/api/credit-scores/backtest/report/start', methods=['POST'])
@require_auth
@require_role('admin')
def start_backtest_report():
    """
    Start generating a validation report in the background.
    Returns immediately with a job_id to poll for status.
    Only one report can be generated at a time.

    Body (optional):
        - start_year: Start year (default 2022)
        - end_year: End year
        - quick: If true, use quick mode (default true)

    Returns:
        - job_id: ID to poll for status
        - status: 'started' or 'already_running'
    """
    global _background_jobs

    try:
        if not backtest_report:
            return jsonify({
                'success': False,
                'error': 'Backtest report service not available'
            }), 503

        # Check if a job is already running
        with _background_jobs_lock:
            for job_id, job in _background_jobs.items():
                if job.get('status') == 'running':
                    return jsonify({
                        'success': True,
                        'status': 'already_running',
                        'job_id': job_id,
                        'message': 'A report is already being generated. Please wait for it to complete.',
                        'started_at': job.get('started_at')
                    })

        data = request.get_json() or {}
        quick_mode = data.get('quick', True)
        start_year = data.get('start_year', 2022 if quick_mode else 2015)
        end_year = data.get('end_year')

        # Create new job
        job_id = f"report_{uuid.uuid4().hex[:8]}"

        with _background_jobs_lock:
            _background_jobs[job_id] = {
                'job_id': job_id,
                'type': 'validation_report',
                'status': 'pending',
                'created_at': datetime.now().isoformat(),
                'config': {
                    'start_year': start_year,
                    'end_year': end_year,
                    'quick_mode': quick_mode
                }
            }

        # Start background thread
        thread = threading.Thread(
            target=_run_report_generation_background,
            args=(job_id, start_year, end_year, quick_mode),
            daemon=True
        )
        thread.start()

        logger.info(f"📊 Started background report generation job: {job_id}")

        return jsonify({
            'success': True,
            'status': 'started',
            'job_id': job_id,
            'message': 'Report generation started. Poll /api/credit-scores/backtest/report/status/{job_id} for progress.',
            'estimated_time_minutes': 10 if quick_mode else 20
        })

    except Exception as e:
        logger.error(f"❌ Error starting backtest report: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/credit-scores/backtest/report/status/<job_id>', methods=['GET'])
@require_auth
@require_role('admin')
def get_backtest_report_status(job_id):
    """
    Get the status of a background report generation job.

    Returns:
        - status: 'pending', 'running', 'completed', or 'failed'
        - result: The report data (if completed)
        - error: Error message (if failed)
    """
    global _background_jobs

    with _background_jobs_lock:
        job = _background_jobs.get(job_id)

    if not job:
        return jsonify({
            'success': False,
            'error': 'Job not found',
            'job_id': job_id
        }), 404

    response = {
        'success': True,
        'job_id': job_id,
        'status': job.get('status'),
        'created_at': job.get('created_at'),
        'started_at': job.get('started_at'),
        'completed_at': job.get('completed_at')
    }

    if job.get('status') == 'completed':
        response['result'] = job.get('result')
    elif job.get('status') == 'failed':
        response['error'] = job.get('error')

    return jsonify(response)


@app.route('/api/credit-scores/backtest/report/status', methods=['GET'])
@require_auth
@require_role('admin')
def get_all_report_jobs_status():
    """
    Get status of all report generation jobs.
    Useful for checking if any job is currently running.
    """
    global _background_jobs

    with _background_jobs_lock:
        jobs = []
        for job_id, job in _background_jobs.items():
            jobs.append({
                'job_id': job_id,
                'status': job.get('status'),
                'created_at': job.get('created_at'),
                'started_at': job.get('started_at'),
                'completed_at': job.get('completed_at')
            })

    # Find currently running job
    running_job = next((j for j in jobs if j['status'] == 'running'), None)

    return jsonify({
        'success': True,
        'jobs': jobs,
        'running_job': running_job,
        'total_jobs': len(jobs)
    })


@app.route('/api/credit-scores/backtest/report', methods=['POST'])
@require_auth
@require_role('admin')
def generate_backtest_report():
    """
    Generate new comprehensive validation report.
    Runs backtest + optimization + validation + report generation.

    NOTE: This is a synchronous endpoint that can take 10-15 minutes.
    Consider using /api/credit-scores/backtest/report/start for background processing.

    Body (optional):
        - start_year: Start year (default 2015)
        - end_year: End year
        - quick: If true, skip heavy backtest and use recent validation only

    Returns: Full validation report
    """
    start_time = datetime.now()

    try:
        if not backtest_report:
            return jsonify({
                'success': False,
                'error': 'Backtest report service not available'
            }), 503

        data = request.get_json() or {}
        quick_mode = data.get('quick', True)  # Default to quick mode
        start_year = data.get('start_year', 2022 if quick_mode else 2015)
        end_year = data.get('end_year')

        logger.info(f"📊 Generating {'quick' if quick_mode else 'comprehensive'} validation report {start_year}-{end_year or 'present'}...")

        if quick_mode:
            # Quick mode: just run validation suite and use minimal backtest
            report = backtest_report.generate_validation_report(
                run_fresh=True,
                start_year=start_year,
                end_year=end_year
            )
        else:
            report = backtest_report.generate_validation_report(
                run_fresh=True,
                start_year=start_year,
                end_year=end_year
            )

        # Also get text summary
        summary_text = backtest_report.get_report_summary(report)

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        return jsonify({
            'success': True,
            'report_id': report.get('report_id'),
            'executive_summary': report.get('executive_summary'),
            'key_findings': report.get('key_findings'),
            'validation_cases': report.get('validation_cases'),
            'weight_calibration': report.get('weight_calibration'),
            'airline_profiles': report.get('airline_profiles'),
            'limitations': report.get('limitations'),
            'full_results': report.get('full_results'),
            'report_metadata': report.get('report_metadata'),
            'summary_text': summary_text,
            'timestamp': datetime.now().isoformat(),
            'response_time_ms': round(response_time, 1)
        })

    except Exception as e:
        logger.error(f"❌ Error generating backtest report: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/credit-scores/backtest/<code>', methods=['GET'])
@require_auth
@require_role('admin')
def get_historical_score(code):
    """
    Get historical score for a specific airline at a specific date.

    Query params:
        - as_of: Date string (YYYY-MM-DD) - required

    Returns: Point-in-time historical score
    """
    start_time = datetime.now()

    try:
        if not backtest_runner:
            return jsonify({
                'success': False,
                'error': 'Backtest runner service not available'
            }), 503

        as_of_date = request.args.get('as_of')
        if not as_of_date:
            return jsonify({
                'success': False,
                'error': 'Missing required parameter: as_of (YYYY-MM-DD)'
            }), 400

        logger.info(f"📊 Getting historical score for {code} at {as_of_date}...")
        result = backtest_runner.run_single_backtest(
            airline_code=code.upper(),
            as_of_date=as_of_date
        )

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        if result.get('success'):
            obs = result.get('observation', {})
            return jsonify({
                'success': True,
                'airline_code': obs.get('airline_code'),
                'airline_name': obs.get('airline_name'),
                'as_of_date': obs.get('as_of_date'),
                'composite_score': obs.get('composite_score'),
                'letter_grade': obs.get('letter_grade'),
                'dimension_scores': obs.get('dimension_scores'),
                'actual_rating_at_time': obs.get('actual_rating_at_time'),
                'actual_rating_moodys': obs.get('actual_rating_moodys'),
                'actual_rating_numeric': obs.get('actual_rating_numeric'),
                'is_investment_grade': obs.get('is_investment_grade'),
                'hurdle_adjustment_bps': obs.get('hurdle_adjustment_bps'),
                'had_credit_event_next_6m': obs.get('had_credit_event_next_6m'),
                'had_credit_event_next_12m': obs.get('had_credit_event_next_12m'),
                'weights_used': result.get('weights_used'),
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': round(response_time, 1)
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Could not calculate historical score'),
                'timestamp': datetime.now().isoformat()
            }), 404

    except Exception as e:
        logger.error(f"❌ Error getting historical score for {code}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# ============================================================================
# PIPELINE MONITORING ENDPOINTS
# ============================================================================

@app.route('/api/pipelines/status', methods=['GET'])
@limiter.limit(RATE_TIERS['public'])
def get_pipelines_status():
    """
    Get pipeline freshness status.

    Returns overall health status and individual pipeline freshness.
    Public endpoint - no authentication required.
    ---
    tags:
      - Pipeline Monitoring
    responses:
      200:
        description: Pipeline freshness status
        schema:
          type: object
          properties:
            overall_status:
              type: string
              enum: [healthy, degraded, critical]
            checked_at:
              type: string
              format: date-time
            pipelines:
              type: object
    """
    try:
        from app.services.freshness_service import FreshnessService
        freshness = FreshnessService(db_service)
        return jsonify(freshness.get_freshness_status())
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        return jsonify({
            'overall_status': 'unknown',
            'error': str(e),
            'checked_at': datetime.now().isoformat() + 'Z'
        }), 500


@app.route('/api/pipelines/runs', methods=['GET'])
@require_auth_or_api_key
def get_pipeline_runs():
    """
    Get recent pipeline runs.

    Query parameters:
    - pipeline: Filter by pipeline name (optional)
    - limit: Max number of runs to return (default 50, max 100)
    ---
    tags:
      - Pipeline Monitoring
    parameters:
      - name: X-API-Key
        in: header
        type: string
        required: true
      - name: pipeline
        in: query
        type: string
        required: false
      - name: limit
        in: query
        type: integer
        default: 50
    responses:
      200:
        description: List of pipeline runs
    """
    try:
        pipeline = request.args.get('pipeline')
        limit = min(int(request.args.get('limit', 50)), 100)
        runs = db_service.get_pipeline_runs(pipeline_name=pipeline, limit=limit)
        return jsonify({
            'runs': runs,
            'count': len(runs),
            'filter': {'pipeline': pipeline, 'limit': limit}
        })
    except Exception as e:
        logger.error(f"Error getting pipeline runs: {e}")
        return jsonify({
            'error': str(e),
            'runs': [],
            'count': 0
        }), 500


@app.route('/api/pipelines/check-freshness', methods=['POST'])
@require_auth_or_api_key
def check_and_alert_freshness():
    """
    Check freshness and send alerts for stale pipelines.

    Designed for Cloud Scheduler to run every 4 hours.
    Sends Slack alerts if pipelines are stale.
    ---
    tags:
      - Pipeline Monitoring
    parameters:
      - name: X-API-Key
        in: header
        type: string
        required: true
    responses:
      200:
        description: Staleness check result
    """
    try:
        from app.services.freshness_service import FreshnessService
        from app.utils.alerting import send_staleness_alert

        freshness = FreshnessService(db_service)
        stale = freshness.get_stale_pipelines()

        if stale:
            send_staleness_alert(stale)
            logger.warning(f"⚠️ {len(stale)} stale pipelines detected and alerted")

        return jsonify({
            'success': True,
            'stale_count': len(stale),
            'stale_pipelines': stale,
            'checked_at': datetime.now().isoformat() + 'Z'
        })
    except Exception as e:
        logger.error(f"Error checking freshness: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/pipelines/<pipeline_name>', methods=['GET'])
@require_auth_or_api_key
def get_pipeline_details(pipeline_name):
    """
    Get detailed status for a specific pipeline.

    Returns recent runs, last success, and configuration.
    ---
    tags:
      - Pipeline Monitoring
    parameters:
      - name: X-API-Key
        in: header
        type: string
        required: true
      - name: pipeline_name
        in: path
        type: string
        required: true
    responses:
      200:
        description: Pipeline details
    """
    try:
        from app.services.freshness_service import FRESHNESS_THRESHOLDS

        runs = db_service.get_pipeline_runs(pipeline_name=pipeline_name, limit=10)
        last_success = db_service.get_last_successful_run(pipeline_name)
        stats = db_service.get_pipeline_stats(pipeline_name)

        return jsonify({
            'pipeline_name': pipeline_name,
            'recent_runs': runs,
            'last_success': last_success,
            'stats': stats,
            'config': FRESHNESS_THRESHOLDS.get(pipeline_name, {}),
            'timestamp': datetime.now().isoformat() + 'Z'
        })
    except Exception as e:
        logger.error(f"Error getting pipeline details for {pipeline_name}: {e}")
        return jsonify({
            'pipeline_name': pipeline_name,
            'error': str(e)
        }), 500


# ============================================================
# User Management Endpoints (Firebase Auth)
# ============================================================

@app.route('/api/users/me', methods=['GET'])
@require_auth
def get_current_user():
    """
    Get current authenticated user's profile.
    ---
    tags:
      - Users
    security:
      - BearerAuth: []
    responses:
      200:
        description: User profile
      401:
        description: Not authenticated
    """
    from flask import g

    uid = g.firebase_uid
    email = g.firebase_email
    name = g.firebase_name

    # Get or create user profile
    user = user_service.get_or_create_user(uid, email, name)

    return jsonify({
        'success': True,
        'user': {
            'uid': user.get('uid'),
            'email': user.get('email'),
            'display_name': user.get('display_name'),
            'picture': user.get('picture'),
            'company': user.get('company'),
            'role': user.get('role'),
            'status': user.get('status'),
            'created_at': user.get('created_at').isoformat() if user.get('created_at') else None,
            'last_login': user.get('last_login').isoformat() if user.get('last_login') else None,
            'usage': user.get('usage'),
            'preferences': user.get('preferences')
        }
    })


@app.route('/api/users/me', methods=['PATCH'])
@require_auth
def update_current_user():
    """
    Update current user's profile.

    Allowed fields: display_name, company, preferences
    ---
    tags:
      - Users
    security:
      - BearerAuth: []
    parameters:
      - name: body
        in: body
        schema:
          type: object
          properties:
            display_name:
              type: string
            company:
              type: string
            preferences:
              type: object
    responses:
      200:
        description: Updated user profile
      401:
        description: Not authenticated
    """
    from flask import g

    uid = g.firebase_uid
    data = request.get_json() or {}

    # Only allow specific fields to be updated
    allowed_fields = ['display_name', 'company', 'preferences']
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    user = user_service.update_user_profile(
        uid,
        display_name=update_data.get('display_name'),
        company=update_data.get('company'),
        preferences=update_data.get('preferences')
    )

    if not user:
        return jsonify({
            'success': False,
            'error': 'Failed to update profile'
        }), 500

    return jsonify({
        'success': True,
        'user': {
            'uid': user.get('uid'),
            'email': user.get('email'),
            'display_name': user.get('display_name'),
            'company': user.get('company'),
            'role': user.get('role'),
            'preferences': user.get('preferences')
        }
    })


@app.route('/api/admin/users', methods=['GET'])
@require_auth
@require_role('admin')
def list_all_users():
    """
    List all users (admin only).
    ---
    tags:
      - Admin
    security:
      - BearerAuth: []
    parameters:
      - name: limit
        in: query
        type: integer
        default: 50
      - name: offset
        in: query
        type: integer
        default: 0
      - name: role
        in: query
        type: string
        enum: [viewer, analyst, admin]
      - name: status
        in: query
        type: string
        enum: [active, disabled]
    responses:
      200:
        description: List of users
      403:
        description: Insufficient permissions
    """
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    role = request.args.get('role')
    status = request.args.get('status')

    users = user_service.list_users(
        limit=min(limit, 100),  # Cap at 100
        offset=offset,
        role=role,
        status=status
    )

    total = user_service.get_user_count()

    return jsonify({
        'success': True,
        'users': [{
            'uid': u.get('uid'),
            'email': u.get('email'),
            'display_name': u.get('display_name'),
            'company': u.get('company'),
            'role': u.get('role'),
            'status': u.get('status'),
            'created_at': u.get('created_at').isoformat() if u.get('created_at') else None,
            'last_login': u.get('last_login').isoformat() if u.get('last_login') else None
        } for u in users],
        'total': total,
        'limit': limit,
        'offset': offset
    })


@app.route('/api/admin/users/<uid>/role', methods=['PATCH'])
@require_auth
@require_role('admin')
def update_user_role(uid):
    """
    Change a user's role (admin only).
    ---
    tags:
      - Admin
    security:
      - BearerAuth: []
    parameters:
      - name: uid
        in: path
        type: string
        required: true
      - name: body
        in: body
        schema:
          type: object
          required:
            - role
          properties:
            role:
              type: string
              enum: [viewer, analyst, admin]
    responses:
      200:
        description: Updated user
      400:
        description: Invalid role
      403:
        description: Insufficient permissions
      404:
        description: User not found
    """
    from flask import g

    data = request.get_json() or {}
    new_role = data.get('role')

    if not new_role or new_role not in ['viewer', 'analyst', 'admin']:
        return jsonify({
            'success': False,
            'error': 'Invalid role. Must be: viewer, analyst, or admin'
        }), 400

    # Prevent self-demotion from admin
    if uid == g.firebase_uid and new_role != 'admin':
        return jsonify({
            'success': False,
            'error': 'Cannot demote yourself from admin'
        }), 400

    user = user_service.update_user_role(uid, new_role, g.firebase_uid)

    if not user:
        return jsonify({
            'success': False,
            'error': 'User not found or update failed'
        }), 404

    return jsonify({
        'success': True,
        'user': {
            'uid': user.get('uid'),
            'email': user.get('email'),
            'role': user.get('role')
        }
    })


@app.route('/api/admin/users/<uid>/status', methods=['PATCH'])
@require_auth
@require_role('admin')
def update_user_status(uid):
    """
    Enable or disable a user (admin only).
    ---
    tags:
      - Admin
    security:
      - BearerAuth: []
    parameters:
      - name: uid
        in: path
        type: string
        required: true
      - name: body
        in: body
        schema:
          type: object
          required:
            - status
          properties:
            status:
              type: string
              enum: [active, disabled]
    responses:
      200:
        description: Updated user
      400:
        description: Invalid status
      403:
        description: Insufficient permissions
      404:
        description: User not found
    """
    from flask import g

    data = request.get_json() or {}
    new_status = data.get('status')

    if not new_status or new_status not in ['active', 'disabled']:
        return jsonify({
            'success': False,
            'error': 'Invalid status. Must be: active or disabled'
        }), 400

    # Prevent self-disable
    if uid == g.firebase_uid:
        return jsonify({
            'success': False,
            'error': 'Cannot disable yourself'
        }), 400

    user = user_service.update_user_status(uid, new_status, g.firebase_uid)

    if not user:
        return jsonify({
            'success': False,
            'error': 'User not found or update failed'
        }), 404

    return jsonify({
        'success': True,
        'user': {
            'uid': user.get('uid'),
            'email': user.get('email'),
            'status': user.get('status')
        }
    })


# ============================================================
# API v1 Route Registration
# Duplicate all /api/ routes to /api/v1/ for versioning
# ============================================================
def register_v1_routes():
    """
    Register all /api/ routes with /api/v1/ prefix.
    This maintains backward compatibility while enabling versioned API access.
    """
    # Get all existing rules
    rules_to_add = []
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith('/api/') and not rule.rule.startswith('/api/v1/') and not rule.rule.startswith('/api/docs'):
            # Create the v1 version of the route
            v1_rule = rule.rule.replace('/api/', '/api/v1/', 1)
            rules_to_add.append((v1_rule, rule.endpoint, rule.methods - {'OPTIONS', 'HEAD'}))

    # Add v1 routes
    for v1_rule, endpoint, methods in rules_to_add:
        try:
            # Skip if already registered
            existing_rules = [r.rule for r in app.url_map.iter_rules()]
            if v1_rule not in existing_rules:
                app.add_url_rule(v1_rule, endpoint=f"v1_{endpoint}", view_func=app.view_functions[endpoint], methods=list(methods))
        except Exception as e:
            logger.warning(f"Could not register v1 route {v1_rule}: {e}")

    logger.info(f"✅ Registered {len(rules_to_add)} API v1 routes")


# Register v1 routes
register_v1_routes()

# ============================================================
# Legacy API Redirects
# Redirect old /api/ paths to /api/v1/ with deprecation warning
# Note: Legacy redirects are optional - both paths work for now
# ============================================================
from app.api.legacy import legacy_bp
# Uncomment the line below to enable legacy redirects (will break direct /api/ access)
# app.register_blueprint(legacy_bp)

logger.info("🚀 Aviation Intelligence API initialized with API Hardening v1.0")
logger.info(f"📚 API Documentation available at /api/docs")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

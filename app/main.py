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
            'monitoring': 'enhanced' if monitor else 'basic'
        },
        'endpoints': [
            '/health',
            '/api/status', 
            '/api/credit-spread/current',
            '/api/tsa/current',
            '/api/monitoring/health',
            '/api/monitoring/metrics'
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
            'monitoring': 'active' if monitor else 'disabled'
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

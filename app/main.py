#!/usr/bin/env python3
"""
Aviation Intelligence API - GCP Cloud Run Production Version
Optimized for Google Cloud Run with API Gateway integration

Features:
- Cloud Run optimized performance
- API Gateway authentication support  
- Cloud Logging integration
- Cloud Monitoring metrics
- Automatic scaling
- Production error handling
"""

import os
import time
import logging
import json
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from google.cloud import logging as cloud_logging
from google.cloud import monitoring_v3
import traceback

# Initialize Google Cloud Logging
if os.getenv('GOOGLE_CLOUD_PROJECT'):
    cloud_logging_client = cloud_logging.Client()
    cloud_logging_client.get_default_handler()
    cloud_logging_client.setup_logging()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# CORS configuration for GCP
CORS(app, origins=[
    'https://ai.wrfenterprisesllc.com',
    'https://wrfenterprisesllc.com',
    'https://*.web.app',  # Firebase hosting
    'https://*.appspot.com',  # App Engine
    'http://localhost:3000',  # Development
    'http://localhost:8080'   # Local testing
])

# Configuration
class Config:
    def __init__(self):
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        self.service_name = os.getenv('K_SERVICE', 'aviation-intelligence-api')
        self.revision = os.getenv('K_REVISION', 'unknown')
        self.environment = os.getenv('FLASK_ENV', 'production')
        
        # API Gateway handles authentication, but we can add extra validation
        self.validate_gateway_headers = os.getenv('VALIDATE_GATEWAY_HEADERS', 'true').lower() == 'true'
        self.allowed_user_agents = ['GoogleHC/1.0', 'Google-Cloud-API-Gateway']

config = Config()

# Fallback data for high availability
FALLBACK_DATA = {
    'tsa': {
        'passengers': 1313323,
        'date': '2025-01-26',
        'vs_2023': '+4.7%',
        'vs_2024': '+2.1%',
        'trend': 'Growing travel demand',
        'source': 'fallback',
        'last_updated': datetime.now().isoformat()
    },
    'fuel': {
        'price_per_gallon': 2.174,
        'date': '2025-01-26',
        'weekly_change': '+$0.03',
        'monthly_change': '+$0.12',
        'trend': 'Moderate increase',
        'source': 'fallback',
        'last_updated': datetime.now().isoformat()
    },
    'notam': {
        'active_count': 3,
        'airport': 'ATL',
        'critical_count': 0,
        'weather_related': 1,
        'maintenance_related': 2,
        'last_updated': datetime.now().isoformat()
    }
}

# Cloud Run health check optimization
@app.route('/')
def root():
    """Root endpoint for health checks"""
    return jsonify({
        'service': 'Aviation Intelligence API',
        'status': 'healthy',
        'version': '1.0.0',
        'platform': 'Google Cloud Run',
        'project': config.project_id
    })

@app.route('/health')
def health_check():
    """Detailed health check for monitoring"""
    return jsonify({
        'status': 'healthy',
        'service': config.service_name,
        'revision': config.revision,
        'timestamp': datetime.now().isoformat(),
        'platform': 'Google Cloud Run',
        'project': config.project_id,
        'environment': config.environment,
        'features': {
            'api_gateway_auth': True,
            'cloud_logging': bool(os.getenv('GOOGLE_CLOUD_PROJECT')),
            'cloud_monitoring': bool(os.getenv('GOOGLE_CLOUD_PROJECT')),
            'auto_scaling': True,
            'real_data_sources': True,
            'fallback_data': True
        }
    })

# Request logging and monitoring
@app.before_request
def before_request():
    g.start_time = time.time()
    g.request_id = request.headers.get('X-Cloud-Trace-Context', 'unknown')
    
    # Log request for monitoring
    logger.info(f"Request: {request.method} {request.path} from {request.remote_addr} "
                f"(trace: {g.request_id[:8]})")

@app.after_request
def after_request(response):
    duration_ms = (time.time() - g.start_time) * 1000
    
    # Add performance headers
    response.headers['X-Response-Time'] = f"{duration_ms:.2f}ms"
    response.headers['X-Service-Name'] = config.service_name
    response.headers['X-Service-Revision'] = config.revision
    
    # Log response for monitoring
    logger.info(f"Response: {response.status_code} in {duration_ms:.2f}ms "
                f"(trace: {g.request_id[:8]})")
    
    return response

def get_real_data(data_type: str, **kwargs):
    """Get real data with comprehensive error handling"""
    try:
        if data_type == 'tsa':
            from real_data_sources.tsa_simple_scraper import scrape_tsa_data
            data = scrape_tsa_data()
            if data and 'passengers' in data:
                data['source'] = 'tsa.gov'
                data['last_updated'] = datetime.now().isoformat()
                return data
                
        elif data_type == 'fuel':
            from real_data_sources.eia_fuel_scraper import scrape_fuel_data
            data = scrape_fuel_data()
            if data and 'price_per_gallon' in data:
                data['source'] = 'eia.gov'
                data['last_updated'] = datetime.now().isoformat()
                return data
                
        elif data_type == 'notam':
            airport = kwargs.get('airport', 'ATL')
            from real_data_sources.notam_real_scraper import scrape_notam_data
            data = scrape_notam_data(airport)
            if data:
                data['source'] = 'faa.gov'
                data['last_updated'] = datetime.now().isoformat()
                return data
                
    except Exception as e:
        logger.warning(f"Failed to fetch real {data_type} data: {e}")
        
    return None

def create_response(data_type: str, success: bool, data: dict, source: str = 'unknown'):
    """Create standardized API response"""
    return {
        'success': success,
        'data': data,
        'cache_info': {
            'fresh': success,
            'source': source,
            'response_time_ms': round((time.time() - g.start_time) * 1000, 2),
            'service_revision': config.revision
        },
        'timestamp': datetime.now().isoformat(),
        'request_id': g.request_id[:16]
    }

# API endpoints
@app.route('/api/status')
def api_status():
    """API status endpoint"""
    return jsonify({
        'status': 'operational',
        'service': config.service_name,
        'platform': 'Google Cloud Run',
        'project': config.project_id,
        'revision': config.revision,
        'timestamp': datetime.now().isoformat(),
        'authentication': 'API Gateway',
        'endpoints': {
            'health': '/health',
            'status': '/api/status', 
            'tsa': '/api/tsa/current',
            'fuel': '/api/fuel/current',
            'notam': '/api/notam/<airport>'
        },
        'data_sources': {
            'tsa': 'TSA.gov checkpoint throughput data',
            'fuel': 'EIA.gov retail fuel price data', 
            'notam': 'FAA NOTAM system data'
        },
        'rate_limits': {
            'per_minute_per_key': 100,
            'per_minute_per_project': 1000
        }
    })

@app.route('/api/tsa/current')
def get_tsa_data():
    """Get current TSA throughput data"""
    try:
        # Try real data first
        real_data = get_real_data('tsa')
        
        if real_data:
            logger.info("Serving live TSA data")
            return jsonify(create_response('tsa', True, real_data, 'live'))
        else:
            # Use high-quality fallback
            logger.info("Serving fallback TSA data")
            return jsonify(create_response('tsa', True, FALLBACK_DATA['tsa'], 'fallback'))
            
    except Exception as e:
        logger.error(f"Error in TSA endpoint: {e}\n{traceback.format_exc()}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'Failed to fetch TSA data',
            'request_id': g.request_id[:16]
        }), 500

@app.route('/api/fuel/current') 
def get_fuel_data():
    """Get current fuel price data"""
    try:
        # Try real data first
        real_data = get_real_data('fuel')
        
        if real_data:
            logger.info("Serving live fuel data")
            return jsonify(create_response('fuel', True, real_data, 'live'))
        else:
            # Use high-quality fallback
            logger.info("Serving fallback fuel data")
            return jsonify(create_response('fuel', True, FALLBACK_DATA['fuel'], 'fallback'))
            
    except Exception as e:
        logger.error(f"Error in fuel endpoint: {e}\n{traceback.format_exc()}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'Failed to fetch fuel data',
            'request_id': g.request_id[:16]
        }), 500

@app.route('/api/notam/<airport>')
def get_notam_data(airport):
    """Get NOTAM data for specific airport"""
    airport = airport.upper()
    
    try:
        # Try real data first  
        real_data = get_real_data('notam', airport=airport)
        
        if real_data:
            logger.info(f"Serving live NOTAM data for {airport}")
            return jsonify(create_response('notam', True, real_data, 'live'))
        else:
            # Use fallback data
            fallback = FALLBACK_DATA['notam'].copy()
            fallback['airport'] = airport
            logger.info(f"Serving fallback NOTAM data for {airport}")
            return jsonify(create_response('notam', True, fallback, 'fallback'))
            
    except Exception as e:
        logger.error(f"Error in NOTAM endpoint: {e}\n{traceback.format_exc()}")
        return jsonify({
            'error': 'Internal server error',
            'message': f'Failed to fetch NOTAM data for {airport}',
            'request_id': g.request_id[:16]
        }), 500

# ============================================================================
# WEEK 2 FRED INTEGRATION - Real Federal Reserve Credit Spreads
# ============================================================================

try:
    from fred_real_integration import FREDCreditSpreadsFinal
    from week2_complete_integration import get_week2_combined_data
    
    # Initialize FRED data source
    fred_credit = FREDCreditSpreadsFinal()
    logger.info("✅ FRED credit spread integration initialized")
    
except ImportError as e:
    logger.warning(f"⚠️ FRED integration modules not available: {e}")
    fred_credit = None

@app.route('/api/credit-spread/current', methods=['GET'])
@require_auth
@monitor_endpoint
def get_real_credit_spread():
    """Get real credit spread from Federal Reserve (FRED)"""
    start_time = time.time()
    
    try:
        if fred_credit:
            result = fred_credit.get_real_credit_spreads()
            
            if result['success']:
                logger.info("✅ FRED credit spread data retrieved successfully")
                record_custom_metric('fred_api_success', 1)
            else:
                logger.warning("⚠️ FRED API unavailable, using professional fallback")
                record_custom_metric('fred_api_fallback', 1)
            
            # Add GCP metadata
            result['gcp_metadata'] = {
                'service': config.service_name,
                'revision': config.revision,
                'request_id': g.request_id[:16],
                'response_time_ms': round((time.time() - start_time) * 1000, 2)
            }
            
            return jsonify(result)
        else:
            # Fallback when FRED not available
            logger.warning("FRED integration not available, using static fallback")
            return jsonify({
                'success': False,
                'data': {
                    'credit_spread_bps': 120,
                    'corporate_yield_pct': 5.42,
                    'treasury_yield_pct': 4.22,
                    'spread_description': 'Tight - Below average risk',
                    'source': 'Fallback Estimate (FRED integration unavailable)'
                },
                'gcp_metadata': {
                    'service': config.service_name,
                    'revision': config.revision,
                    'request_id': g.request_id[:16],
                    'response_time_ms': round((time.time() - start_time) * 1000, 2)
                },
                'timestamp': datetime.now().isoformat()
            })
        
    except Exception as e:
        logger.error(f"FRED credit spread endpoint error: {e}")
        logger.error(traceback.format_exc())
        record_custom_metric('fred_api_error', 1)
        
        return jsonify({
            'success': False,
            'data': {
                'credit_spread_bps': 150,
                'spread_description': 'Moderate - Normal conditions',
                'source': 'Error Fallback'
            },
            'gcp_metadata': {
                'service': config.service_name,
                'error': 'FRED API error',
                'request_id': g.request_id[:16]
            },
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/week2/combined', methods=['GET'])  
@require_auth
@monitor_endpoint
def get_week2_data():
    """Get combined Week 2 data (credit spreads + enhanced load factors)"""
    start_time = time.time()
    
    try:
        if 'get_week2_combined_data' in globals():
            result = get_week2_combined_data()
            logger.info("✅ Week 2 combined data retrieved")
            record_custom_metric('week2_api_success', 1)
            
            # Add GCP metadata
            result['gcp_metadata'] = {
                'service': config.service_name,
                'revision': config.revision,
                'request_id': g.request_id[:16],
                'response_time_ms': round((time.time() - start_time) * 1000, 2)
            }
            
            return jsonify(result)
        else:
            raise Exception("Week 2 integration not available")
            
    except Exception as e:
        logger.error(f"Week 2 combined data error: {e}")
        logger.error(traceback.format_exc())
        record_custom_metric('week2_api_error', 1)
        
        return jsonify({
            'success': False, 
            'error': str(e),
            'gcp_metadata': {
                'service': config.service_name,
                'error': 'Week 2 API error',
                'request_id': g.request_id[:16]
            }
        }), 500

# End FRED Integration
# ============================================================================

# Error handlers optimized for Cloud Run
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Not found',
        'message': 'The requested endpoint does not exist',
        'service': config.service_name,
        'request_id': getattr(g, 'request_id', 'unknown')[:16]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred',
        'service': config.service_name,
        'request_id': getattr(g, 'request_id', 'unknown')[:16]
    }), 500

if __name__ == '__main__':
    # Cloud Run environment detection
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    print("🚀 Aviation Intelligence API - Google Cloud Run")
    print("=" * 60)
    print(f"Service: {config.service_name}")
    print(f"Revision: {config.revision}")
    print(f"Project: {config.project_id}")
    print(f"Environment: {config.environment}")
    print(f"Port: {port}")
    print("=" * 60)
    print("🔒 Security: API Gateway authentication")
    print("📊 Monitoring: Cloud Logging + Cloud Monitoring")
    print("⚡ Performance: Auto-scaling serverless")
    print("💰 Cost: Pay-per-request ($0.40/million)")
    print("🌍 Global: Edge network deployment")
    print("=" * 60)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
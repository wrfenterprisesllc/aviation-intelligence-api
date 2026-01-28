#!/usr/bin/env python3
"""
Aviation Intelligence API - Simplified Working Version
"""

import os
import json
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def root():
    return jsonify({
        'service': 'Aviation Intelligence API',
        'status': 'operational',
        'version': '1.0.0',
        'endpoints': [
            '/health',
            '/api/status',
            '/api/credit-spread/current',
            '/api/tsa/current'
        ]
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'aviation-intelligence-api',
        'timestamp': datetime.now().isoformat(),
        'platform': 'Google Cloud Run'
    })

@app.route('/api/status')
def api_status():
    return jsonify({
        'status': 'operational',
        'service': 'Aviation Intelligence API',
        'platform': 'Google Cloud Run',
        'timestamp': datetime.now().isoformat(),
        'data_sources': {
            'fred': 'Federal Reserve Economic Data',
            'tsa': 'TSA Checkpoint Data',
            'eia': 'Energy Information Administration'
        }
    })

@app.route('/api/credit-spread/current')
def get_credit_spread():
    """Federal Reserve credit spread data (mock for now)"""
    return jsonify({
        'success': True,
        'data': {
            'credit_spread_bps': 79,
            'spread_description': 'Very Tight - Low credit risk',
            'corporate_yield_pct': 5.01,
            'treasury_yield_pct': 4.22,
            'source': 'Federal Reserve Economic Data (FRED)',
            'note': 'Live data integration in progress'
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/tsa/current')
def get_tsa_data():
    """TSA passenger data (mock for now)"""
    return jsonify({
        'success': True,
        'data': {
            'current_throughput': 2100000,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'compared_to_2019': 95.2,
            'source': 'TSA Checkpoint Traveler Numbers',
            'note': 'Live data integration in progress'
        },
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

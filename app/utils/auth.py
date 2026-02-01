#!/usr/bin/env python3
"""
Authentication utilities for Aviation Intelligence API
Provides API key authentication via X-API-Key header
"""

import os
from functools import wraps
from flask import request, jsonify


def require_api_key(f):
    """
    Decorator to require API key authentication via X-API-Key header

    Usage:
        @app.route('/api/protected', methods=['POST'])
        @require_api_key
        def protected_endpoint():
            return jsonify({'message': 'Success'})

    Returns:
        - 500 if ADMIN_API_KEY not configured in environment
        - 401 if X-API-Key header is missing
        - 403 if X-API-Key header is invalid
        - Calls wrapped function if authentication succeeds
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get API key from environment (injected via Secret Manager)
        valid_api_key = os.getenv('ADMIN_API_KEY')

        if not valid_api_key:
            return jsonify({
                'success': False,
                'error': 'Server configuration error - API key not configured'
            }), 500

        # Get API key from request header
        provided_key = request.headers.get('X-API-Key')

        if not provided_key:
            return jsonify({
                'success': False,
                'error': 'API key required. Include X-API-Key header in your request.'
            }), 401

        if provided_key != valid_api_key:
            return jsonify({
                'success': False,
                'error': 'Invalid API key'
            }), 403

        # Authentication successful, call the wrapped function
        return f(*args, **kwargs)

    return decorated_function

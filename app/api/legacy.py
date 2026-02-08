"""
Legacy API Redirects
Aviation Intelligence Platform - API Hardening

Provides 301 redirects from legacy /api/ paths to new /api/v1/ paths
with deprecation warning headers.
"""

from flask import Blueprint, redirect, request
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

legacy_bp = Blueprint('legacy', __name__)

# Deprecation notice
DEPRECATION_DATE = "2025-08-01"
DEPRECATION_MESSAGE = f"This endpoint is deprecated. Use /api/v1/ prefix instead. Legacy endpoints will be removed after {DEPRECATION_DATE}."


def make_v1_redirect(path: str):
    """
    Create a 301 redirect to the v1 API path with deprecation warning.

    Args:
        path: The path after /api/ (e.g., 'credit-scores' or 'deals/evaluate')

    Returns:
        Response with 301 redirect and X-Deprecation-Warning header
    """
    # Build the new v1 URL
    new_url = f"/api/v1/{path}"

    # Preserve query string if present
    if request.query_string:
        new_url += f"?{request.query_string.decode()}"

    # Log the legacy access
    logger.info(f"Legacy redirect: /api/{path} -> {new_url}")

    # Create redirect response
    response = redirect(new_url, code=301)
    response.headers['X-Deprecation-Warning'] = DEPRECATION_MESSAGE

    return response


# Catch-all route for legacy /api/ paths
# This must be registered AFTER the v1 blueprint to avoid conflicts
@legacy_bp.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def legacy_catch_all(path):
    """
    Catch-all handler for legacy API paths.
    Redirects to the equivalent /api/v1/ path with deprecation warning.
    """
    # Don't redirect paths that start with 'v1/' (already versioned)
    if path.startswith('v1/'):
        # This shouldn't happen, but safety check
        return redirect(f"/api/{path}", code=308)

    return make_v1_redirect(path)


# Explicit redirects for root /api paths without trailing content
@legacy_bp.route('/api', methods=['GET'])
def legacy_api_root():
    """Redirect /api to /api/v1/status"""
    return make_v1_redirect('status')

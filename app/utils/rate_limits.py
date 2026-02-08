"""
Rate Limiting Configuration
Aviation Intelligence Platform - API Hardening
"""

from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging

logger = logging.getLogger(__name__)


def get_rate_limit_key():
    """
    Get rate limit key based on API key or IP address.
    Prioritize API key for authenticated requests.
    """
    api_key = request.headers.get('X-API-Key')
    if api_key:
        # Use first 16 chars of API key as identifier
        return f"api_key:{api_key[:16]}"
    return get_remote_address()


def is_cloud_scheduler():
    """Check if request is from Cloud Scheduler (exempt from rate limits)."""
    user_agent = request.headers.get('User-Agent', '')
    return 'Google-Cloud-Scheduler' in user_agent


def exempt_cloud_scheduler():
    """Exemption function for Cloud Scheduler requests."""
    return is_cloud_scheduler()


# Rate limit tier definitions
RATE_TIERS = {
    'public': "60 per minute",          # Public GET endpoints, no computation
    'auth_read': "200 per minute",       # Authenticated read operations
    'auth_write': "30 per minute",       # Authenticated write operations
    'heavy': "5 per minute",             # Heavy computation (backtest, optimize)
    'scheduler': "10 per minute",        # Cloud Scheduler jobs
    'unlimited': None                    # No rate limit (health checks)
}

# Initialize limiter (will be attached to app in main.py)
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["60 per minute"],
    storage_uri="memory://",
    strategy="fixed-window",
    headers_enabled=True,  # Add X-RateLimit-* headers to responses
    header_name_mapping={
        "HEADER_LIMIT": "X-RateLimit-Limit",
        "HEADER_REMAINING": "X-RateLimit-Remaining",
        "HEADER_RESET": "X-RateLimit-Reset"
    }
)


# Decorator shortcuts for common rate limit tiers
def rate_limit_public(f):
    """Apply public tier rate limit (60/min)."""
    return limiter.limit(RATE_TIERS['public'])(f)


def rate_limit_auth_read(f):
    """Apply authenticated read tier rate limit (200/min)."""
    return limiter.limit(RATE_TIERS['auth_read'])(f)


def rate_limit_auth_write(f):
    """Apply authenticated write tier rate limit (30/min)."""
    return limiter.limit(RATE_TIERS['auth_write'])(f)


def rate_limit_heavy(f):
    """Apply heavy computation tier rate limit (5/min)."""
    return limiter.limit(RATE_TIERS['heavy'])(f)


def rate_limit_scheduler(f):
    """Apply scheduler tier rate limit (10/min), exempt Cloud Scheduler."""
    return limiter.limit(
        RATE_TIERS['scheduler'],
        exempt_when=exempt_cloud_scheduler
    )(f)


def init_rate_limiter(app):
    """Initialize rate limiter with Flask app."""
    limiter.init_app(app)
    logger.info("✅ Rate limiter initialized with tiers: " + ", ".join(RATE_TIERS.keys()))
    return limiter

"""
Standardized API Error Classes and Handlers
Aviation Intelligence Platform - API Hardening
"""

from flask import jsonify
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base API error class for all custom exceptions."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self._default_error_code()
        self.details = details or {}
        super().__init__(self.message)

    def _default_error_code(self) -> str:
        """Generate default error code from status code."""
        codes = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            422: "validation_error",
            429: "rate_limit_exceeded",
            500: "internal_error",
            503: "service_unavailable"
        }
        return codes.get(self.status_code, f"error_{self.status_code}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to JSON-serializable dict."""
        response = {
            'success': False,
            'error': self.error_code,
            'message': self.message,
            'status_code': self.status_code,
            'timestamp': datetime.utcnow().isoformat()
        }
        if self.details:
            response['details'] = self.details
        return response


class BadRequestError(APIError):
    """400 Bad Request - Invalid input or malformed request."""

    def __init__(self, message: str = "Bad request", **kwargs):
        super().__init__(message, status_code=400, **kwargs)


class UnauthorizedError(APIError):
    """401 Unauthorized - Authentication required."""

    def __init__(self, message: str = "Authentication required", **kwargs):
        super().__init__(message, status_code=401, error_code="auth_required", **kwargs)


class ForbiddenError(APIError):
    """403 Forbidden - Invalid credentials or insufficient permissions."""

    def __init__(self, message: str = "Access forbidden", **kwargs):
        super().__init__(message, status_code=403, error_code="auth_invalid", **kwargs)


class NotFoundError(APIError):
    """404 Not Found - Resource does not exist."""

    def __init__(self, message: str = "Resource not found", resource: str = None, **kwargs):
        if resource:
            message = f"{resource} not found"
        super().__init__(message, status_code=404, **kwargs)


class ConflictError(APIError):
    """409 Conflict - Resource already exists or state conflict."""

    def __init__(self, message: str = "Resource conflict", **kwargs):
        super().__init__(message, status_code=409, **kwargs)


class ValidationError(APIError):
    """422 Unprocessable Entity - Validation failed."""

    def __init__(
        self,
        message: str = "Validation failed",
        fields: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        details = kwargs.pop('details', {})
        if fields:
            details['fields'] = fields
        super().__init__(message, status_code=422, error_code="validation_error", details=details, **kwargs)


class RateLimitError(APIError):
    """429 Too Many Requests - Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = None,
        limit: str = None,
        **kwargs
    ):
        details = kwargs.pop('details', {})
        if retry_after:
            details['retry_after'] = retry_after
        if limit:
            details['limit'] = limit
        super().__init__(message, status_code=429, error_code="rate_limit_exceeded", details=details, **kwargs)


class ServiceUnavailableError(APIError):
    """503 Service Unavailable - External dependency not available."""

    def __init__(self, service: str = None, message: str = None, **kwargs):
        if service and not message:
            message = f"{service} service is currently unavailable"
        elif not message:
            message = "Service temporarily unavailable"
        super().__init__(message, status_code=503, error_code="service_unavailable", **kwargs)


def register_error_handlers(app):
    """Register global error handlers with Flask app."""

    @app.errorhandler(APIError)
    def handle_api_error(error):
        """Handle custom APIError exceptions."""
        logger.warning(f"API Error: {error.error_code} - {error.message}")
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    @app.errorhandler(400)
    def handle_bad_request(error):
        """Handle 400 Bad Request."""
        return jsonify({
            'success': False,
            'error': 'bad_request',
            'message': str(error.description) if hasattr(error, 'description') else 'Bad request',
            'status_code': 400,
            'timestamp': datetime.utcnow().isoformat()
        }), 400

    @app.errorhandler(401)
    def handle_unauthorized(error):
        """Handle 401 Unauthorized."""
        return jsonify({
            'success': False,
            'error': 'unauthorized',
            'message': 'Authentication required',
            'status_code': 401,
            'timestamp': datetime.utcnow().isoformat()
        }), 401

    @app.errorhandler(403)
    def handle_forbidden(error):
        """Handle 403 Forbidden."""
        return jsonify({
            'success': False,
            'error': 'forbidden',
            'message': 'Access forbidden',
            'status_code': 403,
            'timestamp': datetime.utcnow().isoformat()
        }), 403

    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 Not Found."""
        return jsonify({
            'success': False,
            'error': 'not_found',
            'message': 'The requested resource was not found',
            'status_code': 404,
            'timestamp': datetime.utcnow().isoformat()
        }), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        """Handle 405 Method Not Allowed."""
        return jsonify({
            'success': False,
            'error': 'method_not_allowed',
            'message': 'Method not allowed for this endpoint',
            'status_code': 405,
            'timestamp': datetime.utcnow().isoformat()
        }), 405

    @app.errorhandler(429)
    def handle_rate_limit(error):
        """Handle 429 Too Many Requests."""
        return jsonify({
            'success': False,
            'error': 'rate_limit_exceeded',
            'message': 'Rate limit exceeded. Please try again later.',
            'status_code': 429,
            'timestamp': datetime.utcnow().isoformat()
        }), 429

    @app.errorhandler(500)
    def handle_internal_error(error):
        """Handle 500 Internal Server Error."""
        logger.exception("Unhandled exception")
        return jsonify({
            'success': False,
            'error': 'internal_error',
            'message': 'An unexpected error occurred. Please try again later.',
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

    @app.errorhandler(503)
    def handle_service_unavailable(error):
        """Handle 503 Service Unavailable."""
        return jsonify({
            'success': False,
            'error': 'service_unavailable',
            'message': 'Service temporarily unavailable',
            'status_code': 503,
            'timestamp': datetime.utcnow().isoformat()
        }), 503

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Catch-all handler for unexpected exceptions."""
        logger.exception(f"Unexpected error: {str(error)}")
        return jsonify({
            'success': False,
            'error': 'internal_error',
            'message': 'An unexpected error occurred. Please try again later.',
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

    logger.info("✅ Error handlers registered")

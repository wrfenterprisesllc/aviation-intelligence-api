"""
Firebase Authentication utilities for Aviation Intelligence API.

Provides decorators for verifying Firebase ID tokens and role-based access control.
"""
import os
import logging
from functools import wraps
from flask import request, g, jsonify

import firebase_admin
from firebase_admin import auth as firebase_auth

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
# On Cloud Run, this uses the default service account automatically
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        logger.info("Firebase Admin SDK initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")


def verify_firebase_token(id_token: str) -> dict:
    """
    Verify a Firebase ID token and return the decoded claims.

    Returns:
        dict: Decoded token claims including uid, email, name, picture, email_verified, etc.

    Raises:
        firebase_admin.auth.InvalidIdTokenError: If token is invalid
        firebase_admin.auth.ExpiredIdTokenError: If token has expired
        firebase_admin.auth.RevokedIdTokenError: If token has been revoked
    """
    decoded = firebase_auth.verify_id_token(id_token)
    return decoded


def require_auth(f):
    """
    Decorator that verifies Firebase ID token and sets user info in Flask g object.

    Sets:
        g.firebase_uid: The user's Firebase UID
        g.firebase_email: The user's email address
        g.firebase_name: The user's display name (if available)
        g.auth_type: 'user' to indicate Firebase auth

    Returns 401 if:
        - Authorization header is missing
        - Token format is invalid
        - Token verification fails
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return jsonify({
                "error": "unauthorized",
                "message": "Missing Authorization header"
            }), 401

        if not auth_header.startswith("Bearer "):
            return jsonify({
                "error": "unauthorized",
                "message": "Invalid Authorization header format. Expected: Bearer <token>"
            }), 401

        id_token = auth_header.split("Bearer ")[1]

        try:
            decoded = verify_firebase_token(id_token)
            g.firebase_uid = decoded["uid"]
            g.firebase_email = decoded.get("email")
            g.firebase_name = decoded.get("name")
            g.auth_type = "user"

            logger.debug(f"Authenticated user: {g.firebase_email} ({g.firebase_uid})")

        except firebase_auth.InvalidIdTokenError as e:
            logger.warning(f"Invalid Firebase token: {e}")
            return jsonify({
                "error": "unauthorized",
                "message": "Invalid token"
            }), 401
        except firebase_auth.ExpiredIdTokenError as e:
            logger.warning(f"Expired Firebase token: {e}")
            return jsonify({
                "error": "unauthorized",
                "message": "Token has expired. Please refresh your session."
            }), 401
        except firebase_auth.RevokedIdTokenError as e:
            logger.warning(f"Revoked Firebase token: {e}")
            return jsonify({
                "error": "unauthorized",
                "message": "Token has been revoked. Please log in again."
            }), 401
        except Exception as e:
            logger.error(f"Firebase token verification failed: {e}")
            return jsonify({
                "error": "unauthorized",
                "message": "Token verification failed"
            }), 401

        return f(*args, **kwargs)
    return decorated


def require_role(role: str):
    """
    Decorator that checks if the authenticated user has the required role.

    Must be used AFTER @require_auth decorator.

    Role hierarchy: admin > analyst > viewer
    - admin: Can do everything
    - analyst: Can do analyst + viewer actions
    - viewer: Can only view

    Args:
        role: Minimum required role ('viewer', 'analyst', or 'admin')

    Returns 403 if user doesn't have sufficient role.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from app.services.user_service import get_user_by_uid

            uid = getattr(g, 'firebase_uid', None)
            if not uid:
                return jsonify({
                    "error": "forbidden",
                    "message": "User not authenticated"
                }), 403

            user = get_user_by_uid(uid)
            if not user:
                return jsonify({
                    "error": "forbidden",
                    "message": "User profile not found. Please complete registration."
                }), 403

            user_role = user.get("role", "viewer")
            if user_role not in _role_hierarchy(role):
                logger.warning(f"User {g.firebase_email} with role '{user_role}' attempted to access '{role}'-restricted endpoint")
                return jsonify({
                    "error": "forbidden",
                    "message": f"This action requires '{role}' role. Your role: '{user_role}'"
                }), 403

            # Store user info in g for use in the endpoint
            g.user = user
            g.user_role = user_role

            return f(*args, **kwargs)
        return decorated
    return decorator


def require_auth_or_api_key(f):
    """
    Decorator that accepts either a Firebase ID token OR an API key.

    Use this for endpoints that are called by both:
    - Users (via frontend with Firebase token)
    - Cloud Scheduler jobs (with X-API-Key)

    Checks Bearer token first, then falls back to X-API-Key.

    Sets:
        g.firebase_uid: User's Firebase UID (if user auth) or None (if API key)
        g.firebase_email: User's email (if user auth) or None (if API key)
        g.auth_type: 'user' or 'api_key'
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Try Firebase token first (user auth)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            id_token = auth_header.split("Bearer ")[1]
            try:
                decoded = verify_firebase_token(id_token)
                g.firebase_uid = decoded["uid"]
                g.firebase_email = decoded.get("email")
                g.firebase_name = decoded.get("name")
                g.auth_type = "user"
                logger.debug(f"Authenticated via Firebase: {g.firebase_email}")
                return f(*args, **kwargs)
            except Exception as e:
                logger.debug(f"Firebase token invalid, trying API key: {e}")
                # Fall through to API key check

        # Try API key (machine auth)
        api_key = request.headers.get("X-API-Key")
        valid_key = os.getenv("ADMIN_API_KEY")

        if api_key and valid_key and api_key == valid_key:
            g.firebase_uid = None
            g.firebase_email = None
            g.auth_type = "api_key"
            logger.debug("Authenticated via API key")
            return f(*args, **kwargs)

        # Neither auth method worked
        return jsonify({
            "error": "unauthorized",
            "message": "Authentication required. Provide either 'Authorization: Bearer <token>' or 'X-API-Key: <key>'"
        }), 401

    return decorated


def _role_hierarchy(minimum_role: str) -> list:
    """
    Returns list of roles that satisfy the minimum role requirement.

    Role hierarchy: admin > analyst > viewer

    Args:
        minimum_role: The minimum required role

    Returns:
        List of roles that meet or exceed the minimum requirement
    """
    hierarchy = {
        "viewer": ["viewer", "analyst", "admin"],
        "analyst": ["analyst", "admin"],
        "admin": ["admin"],
    }
    return hierarchy.get(minimum_role, [])


def get_current_user_uid() -> str:
    """
    Get the current authenticated user's Firebase UID.

    Returns:
        str: Firebase UID or None if not authenticated
    """
    return getattr(g, 'firebase_uid', None)


def get_current_user_email() -> str:
    """
    Get the current authenticated user's email.

    Returns:
        str: Email address or None if not authenticated
    """
    return getattr(g, 'firebase_email', None)


def is_api_key_auth() -> bool:
    """
    Check if the current request was authenticated via API key.

    Returns:
        bool: True if API key auth, False otherwise
    """
    return getattr(g, 'auth_type', None) == "api_key"

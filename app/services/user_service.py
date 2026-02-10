"""
User Service - Firebase User Management
Handles user CRUD operations for the Aviation Intelligence API
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from app.services.database_service import DatabaseService

logger = logging.getLogger(__name__)

# Singleton database service instance
_db_service: Optional[DatabaseService] = None


def _get_db() -> DatabaseService:
    """Get or create database service instance."""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service


def get_user_by_uid(uid: str) -> Optional[Dict[str, Any]]:
    """
    Get user by Firebase UID.

    Args:
        uid: Firebase user ID

    Returns:
        User dictionary or None if not found
    """
    try:
        db = _get_db()
        doc_ref = db.db.collection('users').document(uid)
        doc = doc_ref.get()

        if doc.exists:
            user_data = doc.to_dict()
            user_data['uid'] = doc.id
            return user_data
        return None

    except Exception as e:
        logger.error(f"Error getting user {uid}: {e}")
        return None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Get user by email address.

    Args:
        email: User's email address

    Returns:
        User dictionary or None if not found
    """
    try:
        db = _get_db()
        query = db.db.collection('users').where('email', '==', email).limit(1)
        docs = list(query.stream())

        if docs:
            user_data = docs[0].to_dict()
            user_data['uid'] = docs[0].id
            return user_data
        return None

    except Exception as e:
        logger.error(f"Error getting user by email {email}: {e}")
        return None


def get_or_create_user(
    uid: str,
    email: str,
    name: Optional[str] = None,
    picture: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get existing user or create new one on first login.

    Auto-assigns admin role if email is in ADMIN_EMAILS env var.

    Args:
        uid: Firebase user ID
        email: User's email address
        name: Display name (optional)
        picture: Profile picture URL (optional)

    Returns:
        User dictionary (existing or newly created)
    """
    try:
        # Check if user already exists
        existing_user = get_user_by_uid(uid)
        if existing_user:
            # Update last login
            update_user_login(uid)
            return existing_user

        # Determine role and status based on ADMIN_EMAILS
        admin_emails = os.getenv('ADMIN_EMAILS', '').split(',')
        admin_emails = [e.strip().lower() for e in admin_emails if e.strip()]

        is_admin = email.lower() in admin_emails
        role = 'admin' if is_admin else 'viewer'
        # Admins are auto-approved, others require admin approval
        status = 'active' if is_admin else 'pending'

        # Create new user
        user_data = {
            'email': email,
            'display_name': name or email.split('@')[0],
            'picture': picture,
            'company': None,
            'role': role,
            'status': status,
            'created_at': datetime.utcnow(),
            'last_login': datetime.utcnow(),
            'usage': {
                'deal_evaluations': 0,
                'reports_generated': 0,
                'api_calls': 0,
                'last_reset': datetime.utcnow()
            },
            'preferences': {
                'email_notifications': True,
                'newsletter_subscribed': False
            }
        }

        db = _get_db()
        db.db.collection('users').document(uid).set(user_data)

        user_data['uid'] = uid
        logger.info(f"Created new user: {email} with role '{role}'")

        return user_data

    except Exception as e:
        logger.error(f"Error in get_or_create_user for {email}: {e}")
        raise


def update_user_login(uid: str) -> bool:
    """
    Update user's last login timestamp.

    Args:
        uid: Firebase user ID

    Returns:
        True if updated successfully
    """
    try:
        db = _get_db()
        db.db.collection('users').document(uid).update({
            'last_login': datetime.utcnow()
        })
        return True
    except Exception as e:
        logger.error(f"Error updating login for {uid}: {e}")
        return False


def update_user_profile(
    uid: str,
    display_name: Optional[str] = None,
    company: Optional[str] = None,
    preferences: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Update user profile fields.

    Args:
        uid: Firebase user ID
        display_name: New display name (optional)
        company: Company name (optional)
        preferences: User preferences dict (optional)

    Returns:
        Updated user dictionary or None on error
    """
    try:
        updates = {}
        if display_name is not None:
            updates['display_name'] = display_name
        if company is not None:
            updates['company'] = company
        if preferences is not None:
            # Merge preferences instead of replacing
            user = get_user_by_uid(uid)
            if user:
                existing_prefs = user.get('preferences', {})
                existing_prefs.update(preferences)
                updates['preferences'] = existing_prefs

        if not updates:
            return get_user_by_uid(uid)

        updates['updated_at'] = datetime.utcnow()

        db = _get_db()
        db.db.collection('users').document(uid).update(updates)

        logger.info(f"Updated profile for user {uid}")
        return get_user_by_uid(uid)

    except Exception as e:
        logger.error(f"Error updating profile for {uid}: {e}")
        return None


def update_user_role(uid: str, new_role: str, admin_uid: str) -> Optional[Dict[str, Any]]:
    """
    Update user's role (admin only).

    Args:
        uid: Target user's Firebase UID
        new_role: New role ('viewer', 'analyst', or 'admin')
        admin_uid: UID of admin making the change

    Returns:
        Updated user dictionary or None on error
    """
    valid_roles = ['viewer', 'analyst', 'admin']
    if new_role not in valid_roles:
        logger.error(f"Invalid role: {new_role}")
        return None

    try:
        db = _get_db()
        db.db.collection('users').document(uid).update({
            'role': new_role,
            'role_updated_at': datetime.utcnow(),
            'role_updated_by': admin_uid
        })

        user = get_user_by_uid(uid)
        logger.info(f"Updated role for {user.get('email')} to '{new_role}' by admin {admin_uid}")
        return user

    except Exception as e:
        logger.error(f"Error updating role for {uid}: {e}")
        return None


def update_user_status(uid: str, status: str, admin_uid: str) -> Optional[Dict[str, Any]]:
    """
    Update a user's status (admin only).

    Args:
        uid: Target user's Firebase UID
        status: 'active', 'disabled', or 'pending'
        admin_uid: UID of admin making the change

    Returns:
        Updated user dictionary or None on error
    """
    if status not in ['active', 'disabled', 'pending']:
        logger.error(f"Invalid status: {status}")
        return None

    try:
        db = _get_db()
        db.db.collection('users').document(uid).update({
            'status': status,
            'status_updated_at': datetime.utcnow(),
            'status_updated_by': admin_uid
        })

        user = get_user_by_uid(uid)
        logger.info(f"Updated status for {user.get('email')} to '{status}' by admin {admin_uid}")
        return user

    except Exception as e:
        logger.error(f"Error updating status for {uid}: {e}")
        return None


def list_users(
    limit: int = 50,
    offset: int = 0,
    role: Optional[str] = None,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all users with optional filters.

    Args:
        limit: Maximum number of users to return
        offset: Number of users to skip
        role: Filter by role
        status: Filter by status

    Returns:
        List of user dictionaries
    """
    try:
        db = _get_db()
        query = db.db.collection('users')

        if role:
            query = query.where('role', '==', role)
        if status:
            query = query.where('status', '==', status)

        query = query.order_by('created_at', direction='DESCENDING')

        if offset > 0:
            query = query.offset(offset)
        query = query.limit(limit)

        docs = query.stream()

        users = []
        for doc in docs:
            user_data = doc.to_dict()
            user_data['uid'] = doc.id
            users.append(user_data)

        logger.info(f"Retrieved {len(users)} users")
        return users

    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return []


def increment_usage(uid: str, field: str, amount: int = 1) -> bool:
    """
    Increment a user's usage counter.

    Args:
        uid: Firebase user ID
        field: Usage field to increment ('deal_evaluations', 'reports_generated', 'api_calls')
        amount: Amount to increment by

    Returns:
        True if updated successfully
    """
    valid_fields = ['deal_evaluations', 'reports_generated', 'api_calls']
    if field not in valid_fields:
        logger.error(f"Invalid usage field: {field}")
        return False

    try:
        from google.cloud.firestore import Increment

        db = _get_db()
        db.db.collection('users').document(uid).update({
            f'usage.{field}': Increment(amount)
        })

        logger.debug(f"Incremented {field} by {amount} for user {uid}")
        return True

    except Exception as e:
        logger.error(f"Error incrementing usage for {uid}: {e}")
        return False


def get_user_count() -> int:
    """
    Get total number of users.

    Returns:
        Total user count
    """
    try:
        db = _get_db()
        # Use aggregation query for efficiency
        from google.cloud.firestore_v1.aggregation import AggregationQuery

        collection_ref = db.db.collection('users')
        aggregate_query = AggregationQuery(collection_ref)
        aggregate_query.count(alias='total')

        results = list(aggregate_query.get())
        if results:
            return results[0][0].value
        return 0

    except Exception as e:
        logger.error(f"Error counting users: {e}")
        # Fallback to manual count
        try:
            db = _get_db()
            docs = db.db.collection('users').stream()
            return sum(1 for _ in docs)
        except:
            return 0

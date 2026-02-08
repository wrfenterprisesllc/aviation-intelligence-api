"""
API Module - Blueprint Registration
Aviation Intelligence Platform
"""

from flask import Blueprint

# Import v1 blueprint
from app.api.v1 import v1_bp

# Import legacy redirect blueprint
from app.api.legacy import legacy_bp

__all__ = ['v1_bp', 'legacy_bp']

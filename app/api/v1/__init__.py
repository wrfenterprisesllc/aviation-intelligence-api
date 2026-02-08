"""
API v1 Blueprint - Versioned API Endpoints
Aviation Intelligence Platform

This blueprint provides the /api/v1/ prefix for all API endpoints.
The actual endpoint logic is defined in main.py and registered here.
"""

from flask import Blueprint

# Create the v1 blueprint - routes will be registered in main.py
v1_bp = Blueprint('v1', __name__)

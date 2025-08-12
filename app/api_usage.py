"""
Usage API for mdraft.

This module provides endpoints for retrieving user usage statistics
for display in the header badge. It handles authentication via Flask-Login
or session fallback, and retrieves usage data from Redis.
"""
from __future__ import annotations

import os
import redis
from datetime import datetime
from typing import Any, Dict

from flask import Blueprint, jsonify, session
from flask_login import current_user

bp = Blueprint("usage_api", __name__, url_prefix="/api")


def _get_redis_client() -> redis.Redis | None:
    """Get Redis client from environment URL.
    
    Returns:
        Redis client instance or None if REDIS_URL is not configured
    """
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return None
    
    try:
        return redis.Redis.from_url(redis_url)
    except Exception:
        return None


def _get_user_plan_cap(user_id: int) -> int:
    """Get the page cap for a user's plan.
    
    Args:
        user_id: The user ID to check
        
    Returns:
        The page cap for the user's plan
    """
    redis_client = _get_redis_client()
    if not redis_client:
        # Default caps by plan if Redis unavailable
        return 300
    
    try:
        # Check Redis for user plan cap
        cap_pages = redis_client.hget(f"userplan:{user_id}", "cap_pages")
        if cap_pages is not None:
            return int(cap_pages)
    except Exception:
        pass
    
    # Fallback to default caps by plan
    plan_defaults = {
        "F&F": 300,
        "Pro": 2000,
        "Team": 10000
    }
    
    # Try to get user's plan from Redis
    try:
        if redis_client:
            plan = redis_client.hget(f"userplan:{user_id}", "plan")
            if plan and plan.decode() in plan_defaults:
                return plan_defaults[plan.decode()]
    except Exception:
        pass
    
    # Final fallback
    return 300


def _get_used_pages(user_id: int) -> int:
    """Get the number of pages used by a user this month.
    
    Args:
        user_id: The user ID to check
        
    Returns:
        The number of pages used this month
    """
    redis_client = _get_redis_client()
    if not redis_client:
        return 0
    
    try:
        # Get current month in YYYYMM format
        current_month = datetime.utcnow().strftime("%Y%m")
        usage_key = f"usage:pages:{user_id}:{current_month}"
        
        used_pages = redis_client.get(usage_key)
        if used_pages is not None:
            return int(used_pages)
    except Exception:
        pass
    
    return 0


def _get_user_plan(user_id: int) -> str:
    """Get the user's plan name.
    
    Args:
        user_id: The user ID to check
        
    Returns:
        The user's plan name
    """
    redis_client = _get_redis_client()
    if not redis_client:
        return "F&F"
    
    try:
        plan = redis_client.hget(f"userplan:{user_id}", "plan")
        if plan is not None:
            return plan.decode()
    except Exception:
        pass
    
    return "F&F"


@bp.route("/me/usage", methods=["GET"])
def get_usage() -> Any:
    """Get current user's usage statistics.
    
    Returns:
        JSON response with used_pages, cap_pages, and plan
    """
    # Check authentication - try Flask-Login first
    user_id = None
    
    try:
        if current_user.is_authenticated:
            user_id = current_user.id
    except Exception:
        # Flask-Login not available or error, try session fallback
        user_id = session.get("user_id")
    
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    
    # Get usage data with defensive error handling
    try:
        used_pages = _get_used_pages(user_id)
        cap_pages = _get_user_plan_cap(user_id)
        plan = _get_user_plan(user_id)
        
        return jsonify({
            "used_pages": used_pages,
            "cap_pages": cap_pages,
            "plan": plan
        })
    except Exception:
        # Return safe defaults if anything fails
        return jsonify({
            "used_pages": 0,
            "cap_pages": 300,
            "plan": "F&F"
        })

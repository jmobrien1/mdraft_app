"""
Visitor session management for anonymous users.

This module provides utilities for managing anonymous visitor sessions
using secure cookies to enable anonymous proposal creation and management.
"""
import uuid
import datetime
from typing import Optional, Tuple
from flask import request, g, make_response, current_app


COOKIE_NAME = "visitor_session_id"
# Reduced TTL from 30 days to 7-14 days for security
DEFAULT_TTL_DAYS = 7  # Configurable via environment variable


def get_or_create_visitor_session_id(response: Optional[make_response] = None, 
                                   secret: Optional[str] = None) -> Tuple[str, make_response]:
    """
    Get or create a visitor session ID for anonymous users.
    
    This function ensures every anonymous visitor has a unique session ID
    stored in a secure HTTP-only cookie. The session ID is used to scope
    anonymous proposals and files to the specific visitor.
    
    Args:
        response: Optional Flask response object to set cookie on
        secret: Optional secret for cookie signing (uses app SECRET_KEY if not provided)
        
    Returns:
        Tuple of (visitor_session_id, response_object)
    """
    # Get existing visitor session ID from cookie
    vid = request.cookies.get(COOKIE_NAME)
    
    if not vid:
        # Generate new visitor session ID
        vid = str(uuid.uuid4())
        
        # Create response object if not provided
        if response is None:
            response = make_response()
        
        # Get secret for cookie signing
        if secret is None:
            secret = current_app.config.get("SECRET_KEY", "default-secret")
        
        # Set secure cookie with hardened security attributes
        response.set_cookie(
            COOKIE_NAME, 
            vid, 
            httponly=True,  # Always HttpOnly
            secure=True,    # Always Secure (HTTPS only)
            samesite="Lax", # SameSite=Lax for better security
            max_age=60 * 60 * 24 * get_visitor_ttl_days(),  # Configurable TTL
            path="/"
        )
    
    # Store in Flask g for request context
    g.visitor_session_id = vid
    
    return vid, response


def get_visitor_session_id() -> Optional[str]:
    """
    Get the current visitor session ID without creating a new one.
    
    Returns:
        Visitor session ID if exists, None otherwise
    """
    return getattr(g, "visitor_session_id", None)


def clear_visitor_session(response: make_response) -> make_response:
    """
    Clear the visitor session cookie.
    
    This is typically called when an anonymous user logs in
    to convert their session to an authenticated user session.
    
    Args:
        response: Flask response object to clear cookie on
        
    Returns:
        Response object with cleared cookie
    """
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


def rotate_visitor_session(response: make_response) -> Tuple[str, make_response]:
    """
    Rotate the visitor session ID and set a new cookie.
    
    This function is called when a user logs in to invalidate
    the previous anonymous session and create a new one.
    
    Args:
        response: Flask response object to set new cookie on
        
    Returns:
        Tuple of (new_visitor_session_id, response_object)
    """
    # Clear existing cookie
    response = clear_visitor_session(response)
    
    # Generate new visitor session ID
    new_vid = str(uuid.uuid4())
    
    # Set new secure cookie with hardened attributes
    response.set_cookie(
        COOKIE_NAME, 
        new_vid, 
        httponly=True,  # Always HttpOnly
        secure=True,    # Always Secure (HTTPS only)
        samesite="Lax", # SameSite=Lax for better security
        max_age=60 * 60 * 24 * get_visitor_ttl_days(),  # Configurable TTL
        path="/"
    )
    
    # Store in Flask g for request context
    g.visitor_session_id = new_vid
    
    return new_vid, response


def get_visitor_ttl_days() -> int:
    """
    Get the visitor session TTL in days from configuration.
    
    Returns:
        TTL in days (defaults to 7 days)
    """
    return int(current_app.config.get("VISITOR_SESSION_TTL_DAYS", DEFAULT_TTL_DAYS))

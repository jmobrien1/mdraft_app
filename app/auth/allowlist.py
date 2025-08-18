"""
Allowlist utilities for the mdraft application.

This module provides functions to check if emails are allowed to register
or login based on the allowlist configuration.
"""
import os
from typing import List, Optional
from ..models import Allowlist
from ..extensions import db


def is_email_allowed(email: str) -> bool:
    """
    Check if an email is allowed to register or login.
    
    This function checks both the database allowlist and the environment
    variable ALLOWLIST for allowed emails and domains.
    
    Args:
        email: The email address to check
        
    Returns:
        True if the email is allowed, False otherwise
    """
    if not email:
        return False
    
    email = email.strip().lower()
    
    # Check database allowlist first
    allowlist_entry = Allowlist.query.filter_by(email=email).first()
    if allowlist_entry and allowlist_entry.status == "invited":
        return True
    
    # Check environment variable ALLOWLIST
    env_allowlist = os.getenv("ALLOWLIST", "").strip()
    if not env_allowlist:
        return True  # If no allowlist configured, allow all emails
    
    allowed_items = [item.strip().lower() for item in env_allowlist.split(",") if item.strip()]
    
    # Check exact email match
    if email in allowed_items:
        return True
    
    # Check domain match (e.g., "example.org" matches "user@example.org")
    email_domain = email.split("@")[-1] if "@" in email else ""
    if email_domain in allowed_items:
        return True
    
    return False


def add_to_allowlist(email: str, status: str = "invited", plan: str = "F&F", notes: Optional[str] = None) -> Allowlist:
    """
    Add an email to the allowlist.
    
    Args:
        email: The email address to add
        status: The status (default: "invited")
        plan: The plan (default: "F&F")
        notes: Optional notes
        
    Returns:
        The created Allowlist entry
    """
    email = email.strip().lower()
    
    # Check if already exists
    existing = Allowlist.query.filter_by(email=email).first()
    if existing:
        return existing
    
    # Create new entry
    allowlist_entry = Allowlist(
        email=email,
        status=status,
        plan=plan,
        notes=notes
    )
    
    db.session.add(allowlist_entry)
    db.session.commit()
    
    return allowlist_entry


def get_allowlist_entries() -> List[Allowlist]:
    """
    Get all allowlist entries.
    
    Returns:
        List of Allowlist entries
    """
    return Allowlist.query.order_by(Allowlist.created_at.desc()).all()

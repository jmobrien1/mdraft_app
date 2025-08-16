"""
Ownership and access control utilities for proposals and files.

This module provides utilities for determining resource ownership
and enforcing access control for both authenticated and anonymous users.
"""
from typing import Optional, Tuple, Union
from flask import g
from flask_login import current_user

from .visitor import get_visitor_session_id


def get_owner_tuple() -> Tuple[str, Union[int, str, None]]:
    """
    Get the current request owner as a tuple.
    
    Returns:
        Tuple of (owner_type, owner_id) where:
        - owner_type: "user" or "visitor"
        - owner_id: user_id (int), visitor_session_id (str), or None
    """
    if getattr(current_user, "is_authenticated", False):
        return ("user", current_user.id)
    return ("visitor", getattr(g, "visitor_session_id", None))


def get_request_owner() -> Tuple[str, Union[int, str]]:
    """
    Get the current request owner (user or visitor).
    
    Returns:
        Tuple of (owner_type, owner_id) where:
        - owner_type: "user" or "visitor"
        - owner_id: user_id (int) or visitor_session_id (str)
    """
    if getattr(current_user, "is_authenticated", False):
        return ("user", current_user.id)
    
    vid = get_visitor_session_id()
    return ("visitor", vid)


def get_owner_filter() -> dict:
    """
    Get database filter conditions for the current request owner.
    
    Returns:
        Dictionary with appropriate filter conditions for the current owner
    """
    if getattr(current_user, "is_authenticated", False) and current_user.id is not None:
        return {"user_id": current_user.id}
    else:
        vid = get_visitor_session_id()
        if vid:
            return {"visitor_session_id": vid}
        else:
            return {"user_id": None}  # No access for unauthenticated users without session


def validate_proposal_access(proposal) -> bool:
    """
    Validate that the current request owner has access to a proposal.
    
    Args:
        proposal: Proposal model instance
        
    Returns:
        True if access is allowed, False otherwise
    """
    owner_type, owner_id = get_request_owner()
    
    if owner_type == "user":
        return proposal.user_id == owner_id
    else:
        return proposal.visitor_session_id == owner_id


def can_access_proposal(proposal_id: int) -> bool:
    """
    Check if the current request owner can access a proposal by ID.
    
    Args:
        proposal_id: ID of the proposal to check access for
        
    Returns:
        True if access is allowed, False otherwise
    """
    from ..models import Proposal
    
    if getattr(current_user, "is_authenticated", False) and current_user.id is not None:
        proposal = Proposal.query.filter_by(id=proposal_id, user_id=current_user.id).first()
        return proposal is not None
    
    return False


def get_owner_id_for_creation() -> Optional[int]:
    """
    Get the owner ID to use when creating new resources.
    
    Returns:
        user_id (int) for authenticated users, or None if no valid owner can be determined
    """
    if getattr(current_user, "is_authenticated", False) and current_user.id is not None:
        return current_user.id
    
    return None

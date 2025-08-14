"""
Ownership and access control utilities for proposals and files.

This module provides utilities for determining resource ownership
and enforcing access control for both authenticated and anonymous users.
"""
from typing import Optional, Tuple, Union
from flask import g
from flask_login import current_user

from .visitor import get_visitor_session_id


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
    owner_type, owner_id = get_request_owner()
    
    if owner_type == "user":
        return {"user_id": owner_id}
    else:
        return {"visitor_session_id": owner_id}


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
    
    owner_type, owner_id = get_request_owner()
    
    if owner_type == "user":
        proposal = Proposal.query.filter_by(id=proposal_id, user_id=owner_id).first()
    else:
        proposal = Proposal.query.filter_by(id=proposal_id, visitor_session_id=owner_id).first()
    
    return proposal is not None


def get_owner_id_for_creation() -> Optional[Union[int, str]]:
    """
    Get the owner ID to use when creating new resources.
    
    Returns:
        user_id (int) for authenticated users, visitor_session_id (str) for anonymous,
        or None if no valid owner can be determined
    """
    owner_type, owner_id = get_request_owner()
    
    if owner_type == "user" and owner_id is not None:
        return owner_id
    elif owner_type == "visitor" and owner_id is not None:
        return owner_id
    
    return None

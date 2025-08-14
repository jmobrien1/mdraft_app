"""
Cleanup tasks for the mdraft application.

This module provides functions for cleaning up expired data,
including anonymous proposals that have exceeded their TTL.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from . import db
from .models import Proposal, ProposalDocument, Requirement

logger = logging.getLogger(__name__)


def cleanup_expired_anonymous_proposals() -> int:
    """
    Clean up anonymous proposals that have expired.
    
    This function removes proposals created by anonymous users that have
    exceeded their TTL (time-to-live) period.
    
    Returns:
        Number of proposals cleaned up
    """
    try:
        # Get current time
        now = datetime.utcnow()
        
        # Find expired anonymous proposals
        expired_proposals = Proposal.query.filter(
            Proposal.visitor_session_id.isnot(None),
            Proposal.expires_at.isnot(None),
            Proposal.expires_at < now
        ).all()
        
        cleanup_count = 0
        
        for proposal in expired_proposals:
            try:
                # Delete associated documents and requirements (cascade)
                logger.info(f"Cleaning up expired anonymous proposal {proposal.id} ({proposal.name})")
                
                # The cascade delete should handle documents and requirements
                db.session.delete(proposal)
                cleanup_count += 1
                
            except Exception as e:
                logger.error(f"Failed to cleanup proposal {proposal.id}: {e}")
                continue
        
        if cleanup_count > 0:
            db.session.commit()
            logger.info(f"Cleaned up {cleanup_count} expired anonymous proposals")
        
        return cleanup_count
        
    except Exception as e:
        logger.error(f"Failed to cleanup expired anonymous proposals: {e}")
        db.session.rollback()
        return 0


def cleanup_orphaned_documents() -> int:
    """
    Clean up orphaned proposal documents.
    
    This function removes documents that are not associated with any proposal.
    
    Returns:
        Number of documents cleaned up
    """
    try:
        # Find orphaned documents
        orphaned_docs = ProposalDocument.query.filter(
            ~ProposalDocument.proposal_id.in_(
                db.session.query(Proposal.id)
            )
        ).all()
        
        cleanup_count = 0
        
        for doc in orphaned_docs:
            try:
                logger.info(f"Cleaning up orphaned document {doc.id} ({doc.filename})")
                db.session.delete(doc)
                cleanup_count += 1
                
            except Exception as e:
                logger.error(f"Failed to cleanup document {doc.id}: {e}")
                continue
        
        if cleanup_count > 0:
            db.session.commit()
            logger.info(f"Cleaned up {cleanup_count} orphaned documents")
        
        return cleanup_count
        
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned documents: {e}")
        db.session.rollback()
        return 0


def cleanup_orphaned_requirements() -> int:
    """
    Clean up orphaned requirements.
    
    This function removes requirements that are not associated with any proposal.
    
    Returns:
        Number of requirements cleaned up
    """
    try:
        # Find orphaned requirements
        orphaned_reqs = Requirement.query.filter(
            ~Requirement.proposal_id.in_(
                db.session.query(Proposal.id)
            )
        ).all()
        
        cleanup_count = 0
        
        for req in orphaned_reqs:
            try:
                logger.info(f"Cleaning up orphaned requirement {req.id} ({req.requirement_id})")
                db.session.delete(req)
                cleanup_count += 1
                
            except Exception as e:
                logger.error(f"Failed to cleanup requirement {req.id}: {e}")
                continue
        
        if cleanup_count > 0:
            db.session.commit()
            logger.info(f"Cleaned up {cleanup_count} orphaned requirements")
        
        return cleanup_count
        
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned requirements: {e}")
        db.session.rollback()
        return 0


def run_cleanup_tasks() -> dict:
    """
    Run all cleanup tasks.
    
    Returns:
        Dictionary with cleanup results
    """
    results = {
        "expired_proposals": cleanup_expired_anonymous_proposals(),
        "orphaned_documents": cleanup_orphaned_documents(),
        "orphaned_requirements": cleanup_orphaned_requirements(),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    logger.info(f"Cleanup completed: {results}")
    return results

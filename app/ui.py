"""
UI routes for the mdraft application.

This module contains the main UI routes for the web interface.
"""
from __future__ import annotations

from typing import Any
from flask import Blueprint, render_template, request, jsonify, current_app, make_response
from flask_login import login_required, current_user

from . import db
from .models import Job, User, Proposal

bp = Blueprint("ui", __name__)


@bp.route("/")
def index() -> Any:
    """Render the main application page."""
    try:
        current_app.logger.info("Rendering index page")
        return render_template("index.html")
    except Exception as e:
        current_app.logger.error(f"Error rendering index page: {e}")
        current_app.logger.error(f"Error type: {type(e).__name__}")
        current_app.logger.error(f"Error details: {str(e)}")
        # Return a simple error page instead of letting the exception bubble up
        return render_template("errors/500.html"), 500


@bp.route("/compliance-matrix/<int:proposal_id>")
@login_required
def compliance_matrix(proposal_id: int) -> Any:
    """Render the compliance matrix page for a specific proposal."""
    try:
        from .auth.ownership import can_access_proposal
        
        # Validate proposal exists and user has access
        if not can_access_proposal(proposal_id):
            return render_template("errors/404.html"), 404
        
        return render_template("compliance_matrix.html", proposal_id=proposal_id)
    except Exception as e:
        current_app.logger.error(f"Compliance matrix error: {e}")
        return jsonify({"error": "id"}), 500


@bp.route("/proposals")
@login_required
def proposals() -> Any:
    """Render the proposals list page."""
    return render_template("proposals.html")


@bp.route("/api/proposals")
@login_required
def get_proposals() -> Any:
    """Get proposals for the current authenticated user."""
    try:
        from .auth.ownership import get_owner_filter
        
        # Get filter conditions for current owner
        owner_filter = get_owner_filter()
        
        # Query proposals with owner filter
        proposals = Proposal.query.filter_by(**owner_filter).order_by(Proposal.created_at.desc()).all()
        
        result = []
        for proposal in proposals:
            # Get document and requirement counts
            from .models import ProposalDocument, Requirement
            doc_count = ProposalDocument.query.filter_by(proposal_id=proposal.id).count()
            req_count = Requirement.query.filter_by(proposal_id=proposal.id).count()
            
            result.append({
                "id": proposal.id,
                "name": proposal.name,
                "description": proposal.description,
                "status": proposal.status,
                "document_count": doc_count,
                "requirement_count": req_count,
                "created_at": proposal.created_at.isoformat(),
                "is_anonymous": False
            })
        
        return jsonify({"proposals": result}), 200
        
    except Exception as e:
        current_app.logger.error(f"Failed to get proposals: {e}")
        return jsonify({"error": str(e)}), 500

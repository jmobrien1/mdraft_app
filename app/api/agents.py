"""
API endpoints for AI agents including the Compliance Matrix Agent.

This module provides RESTful endpoints for running AI agents on RFP documents
and managing the results.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy.orm import Session

from .. import db
from ..models import Proposal, ProposalDocument, Requirement, User
from ..services.rfp_data_layer import RFPDataLayer
from ..agents.compliance_agent import ComplianceAgent
from ..conversion import process_job
from ..auth.utils import get_request_user_id_or_none


bp = Blueprint("agents", __name__, url_prefix="/api/agents")
logger = logging.getLogger(__name__)


@bp.route("/compliance-matrix/run", methods=["POST"])
@login_required
def run_compliance_matrix_agent() -> Any:
    """Run the Compliance Matrix Agent on a proposal.
    
    This endpoint processes RFP documents to extract requirements and create
    a compliance matrix with stable IDs and citations.
    
    Request body:
    {
        "proposal_id": 123,
        "target_sections": ["C", "PWS"],  # Optional, defaults to ["C"]
        "force_reprocess": false  # Optional, defaults to false
    }
    
    Returns:
    {
        "status": "success",
        "proposal_id": 123,
        "total_requirements": 45,
        "requirements": [...],
        "processing_time": 12.5
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        proposal_id = data.get("proposal_id")
        if not proposal_id:
            return jsonify({"error": "proposal_id is required"}), 400
        
        target_sections = data.get("target_sections", ["C"])
        force_reprocess = data.get("force_reprocess", False)
        
        # Get user ID safely (handles anonymous users)
        user_id = get_request_user_id_or_none()
        if not user_id:
            return jsonify({"error": "Authentication required for this endpoint"}), 401
        
        # Validate proposal exists and user has access
        proposal = Proposal.query.filter_by(id=proposal_id, user_id=user_id).first()
        if not proposal:
            return jsonify({"error": "Proposal not found or access denied"}), 404
        
        # Check if requirements already exist and force_reprocess is False
        if not force_reprocess:
            existing_requirements = Requirement.query.filter_by(proposal_id=proposal_id).count()
            if existing_requirements > 0:
                return jsonify({
                    "error": f"Proposal already has {existing_requirements} requirements. Use force_reprocess=true to reprocess."
                }), 409
        
        # Initialize services
        rfp_data_layer = RFPDataLayer()
        compliance_agent = ComplianceAgent(rfp_data_layer)
        
        # Process requirements
        start_time = datetime.utcnow()
        result = compliance_agent.process_proposal_requirements(proposal_id, target_sections)
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Add processing time to result
        result["status"] = "success"
        result["processing_time"] = processing_time
        
        logger.info(f"Compliance matrix agent completed for proposal {proposal_id} in {processing_time:.2f}s")
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Compliance matrix agent failed: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/compliance-matrix/proposals", methods=["POST"])
@login_required
def create_proposal() -> Any:
    """Create a new proposal for compliance matrix processing.
    
    Request body:
    {
        "name": "RFP-2024-001",
        "description": "Software development services RFP"
    }
    
    Returns:
    {
        "id": 123,
        "name": "RFP-2024-001",
        "description": "Software development services RFP",
        "user_id": 456,
        "status": "active",
        "created_at": "2024-01-01T00:00:00Z"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        name = data.get("name")
        if not name:
            return jsonify({"error": "name is required"}), 400
        
        description = data.get("description")
        
        # Get user ID safely
        user_id = get_request_user_id_or_none()
        if not user_id:
            return jsonify({"error": "Authentication required for this endpoint"}), 401
        
        # Create proposal
        rfp_data_layer = RFPDataLayer()
        proposal = rfp_data_layer.create_proposal(
            user_id=user_id,
            name=name,
            description=description
        )
        
        return jsonify({
            "id": proposal.id,
            "name": proposal.name,
            "description": proposal.description,
            "user_id": proposal.user_id,
            "status": proposal.status,
            "created_at": proposal.created_at.isoformat()
        }), 201
        
    except Exception as e:
        logger.error(f"Failed to create proposal: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/compliance-matrix/proposals", methods=["GET"])
@login_required
def list_proposals() -> Any:
    """List all proposals for the current user.
    
    Query parameters:
    - status: Filter by status (active, archived)
    
    Returns:
    {
        "proposals": [
            {
                "id": 123,
                "name": "RFP-2024-001",
                "description": "Software development services RFP",
                "status": "active",
                "document_count": 3,
                "requirement_count": 45,
                "created_at": "2024-01-01T00:00:00Z"
            }
        ]
    }
    """
    try:
        status = request.args.get("status")
        
        # Get user ID safely
        user_id = get_request_user_id_or_none()
        if not user_id:
            return jsonify({"error": "Authentication required for this endpoint"}), 401
        
        query = Proposal.query.filter_by(user_id=user_id)
        if status:
            query = query.filter_by(status=status)
        
        proposals = query.order_by(Proposal.created_at.desc()).all()
        
        result = []
        for proposal in proposals:
            # Get document and requirement counts
            doc_count = ProposalDocument.query.filter_by(proposal_id=proposal.id).count()
            req_count = Requirement.query.filter_by(proposal_id=proposal.id).count()
            
            result.append({
                "id": proposal.id,
                "name": proposal.name,
                "description": proposal.description,
                "status": proposal.status,
                "document_count": doc_count,
                "requirement_count": req_count,
                "created_at": proposal.created_at.isoformat()
            })
        
        return jsonify({"proposals": result}), 200
        
    except Exception as e:
        logger.error(f"Failed to list proposals: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/compliance-matrix/proposals/<int:proposal_id>/documents", methods=["POST"])
@login_required
def add_document_to_proposal(proposal_id: int) -> Any:
    """Add a document to a proposal for processing.
    
    This endpoint handles file upload and document processing for proposals.
    
    Request: multipart/form-data
    - file: The document file
    - document_type: Type of document (main_rfp, pws, soo, spec, etc.)
    
    Returns:
    {
        "id": 456,
        "filename": "RFP-2024-001.pdf",
        "document_type": "main_rfp",
        "status": "processing",
        "created_at": "2024-01-01T00:00:00Z"
    }
    """
    try:
        # Get user ID safely
        user_id = get_request_user_id_or_none()
        if not user_id:
            return jsonify({"error": "Authentication required for this endpoint"}), 401
        
        # Validate proposal exists and user has access
        proposal = Proposal.query.filter_by(id=proposal_id, user_id=user_id).first()
        if not proposal:
            return jsonify({"error": "Proposal not found or access denied"}), 404
        
        # Check for file upload
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        
        document_type = request.form.get("document_type", "main_rfp")
        
        # Process the file using existing conversion pipeline
        from ..utils import generate_job_id, is_file_allowed
        
        if not is_file_allowed(file.stream):
            return jsonify({"error": "File type not allowed"}), 400
        
        # Generate unique filename
        job_id_str = generate_job_id()
        filename = f"{job_id_str}_{file.filename}"
        
        # Upload to GCS
        bucket_name = current_app.config.get("GCS_BUCKET_NAME")
        gcs_uri = None
        if bucket_name:
            from ..storage import upload_stream_to_gcs
            gcs_uri = upload_stream_to_gcs(file.stream, bucket_name, filename)
        
        # Create job for processing
        from ..models import Job
        job = Job(
            user_id=user_id,
            filename=filename,
            status="queued",
            gcs_uri=gcs_uri or filename
        )
        db.session.add(job)
        db.session.commit()
        
        # Process the document
        try:
            markdown_content = process_job(job.id, gcs_uri or filename)
            
            # Add document to proposal
            rfp_data_layer = RFPDataLayer()
            doc = rfp_data_layer.add_document_to_proposal(
                proposal_id=proposal_id,
                filename=filename,
                document_type=document_type,
                gcs_uri=gcs_uri,
                parsed_text=markdown_content
            )
            
            return jsonify({
                "id": doc.id,
                "filename": doc.filename,
                "document_type": doc.document_type,
                "status": "completed",
                "created_at": doc.created_at.isoformat()
            }), 201
            
        except Exception as e:
            logger.error(f"Failed to process document: {e}")
            return jsonify({"error": f"Document processing failed: {str(e)}"}), 500
        
    except Exception as e:
        logger.error(f"Failed to add document to proposal: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/compliance-matrix/proposals/<int:proposal_id>/requirements", methods=["GET"])
@login_required
def get_proposal_requirements(proposal_id: int) -> Any:
    """Get all requirements for a proposal.
    
    Query parameters:
    - status: Filter by status (pending, in_progress, completed)
    - assigned_owner: Filter by assigned owner
    
    Returns:
    {
        "proposal_id": 123,
        "total_requirements": 45,
        "requirements": [
            {
                "id": "R-1",
                "text": "The contractor shall provide...",
                "section_ref": "C.1.2",
                "page_number": 5,
                "source_document": "RFP-2024-001.pdf",
                "assigned_owner": "John Doe",
                "status": "pending",
                "created_at": "2024-01-01T00:00:00Z"
            }
        ]
    }
    """
    try:
        # Get user ID safely
        user_id = get_request_user_id_or_none()
        if not user_id:
            return jsonify({"error": "Authentication required for this endpoint"}), 401
        
        # Validate proposal exists and user has access
        proposal = Proposal.query.filter_by(id=proposal_id, user_id=user_id).first()
        if not proposal:
            return jsonify({"error": "Proposal not found or access denied"}), 404
        
        # Get filter parameters
        status = request.args.get("status")
        assigned_owner = request.args.get("assigned_owner")
        
        # Build query
        query = Requirement.query.filter_by(proposal_id=proposal_id)
        if status:
            query = query.filter_by(status=status)
        if assigned_owner:
            query = query.filter_by(assigned_owner=assigned_owner)
        
        requirements = query.order_by(Requirement.requirement_id).all()
        
        result = {
            "proposal_id": proposal_id,
            "total_requirements": len(requirements),
            "requirements": [
                {
                    "id": req.requirement_id,
                    "text": req.requirement_text,
                    "section_ref": req.section_ref,
                    "page_number": req.page_number,
                    "source_document": req.source_document,
                    "assigned_owner": req.assigned_owner,
                    "status": req.status,
                    "notes": req.notes,
                    "created_at": req.created_at.isoformat()
                }
                for req in requirements
            ]
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Failed to get proposal requirements: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/compliance-matrix/requirements/<string:requirement_id>", methods=["PUT"])
@login_required
def update_requirement(requirement_id: str) -> Any:
    """Update a requirement (assign owner, change status, add notes).
    
    Request body:
    {
        "proposal_id": 123,
        "assigned_owner": "John Doe",
        "status": "in_progress",
        "notes": "Working on this requirement"
    }
    
    Returns:
    {
        "id": "R-1",
        "assigned_owner": "John Doe",
        "status": "in_progress",
        "notes": "Working on this requirement",
        "updated_at": "2024-01-01T00:00:00Z"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        proposal_id = data.get("proposal_id")
        if not proposal_id:
            return jsonify({"error": "proposal_id is required"}), 400
        
        # Get user ID safely
        user_id = get_request_user_id_or_none()
        if not user_id:
            return jsonify({"error": "Authentication required for this endpoint"}), 401
        
        # Validate proposal exists and user has access
        proposal = Proposal.query.filter_by(id=proposal_id, user_id=user_id).first()
        if not proposal:
            return jsonify({"error": "Proposal not found or access denied"}), 404
        
        # Update requirement
        rfp_data_layer = RFPDataLayer()
        requirement = rfp_data_layer.update_requirement(
            requirement_id=requirement_id,
            proposal_id=proposal_id,
            assigned_owner=data.get("assigned_owner"),
            status=data.get("status"),
            notes=data.get("notes")
        )
        
        if not requirement:
            return jsonify({"error": "Requirement not found"}), 404
        
        return jsonify({
            "id": requirement.requirement_id,
            "assigned_owner": requirement.assigned_owner,
            "status": requirement.status,
            "notes": requirement.notes,
            "updated_at": requirement.updated_at.isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to update requirement: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/compliance-matrix/proposals/<int:proposal_id>/export", methods=["GET"])
@login_required
def export_compliance_matrix(proposal_id: int) -> Any:
    """Export compliance matrix as CSV, XLSX, or PDF.
    
    Query parameters:
    - format: Export format (csv, xlsx, pdf) - defaults to csv
    
    Returns:
    - CSV/XLSX: File download
    - PDF: File download
    """
    try:
        # Get user ID safely
        user_id = get_request_user_id_or_none()
        if not user_id:
            return jsonify({"error": "Authentication required for this endpoint"}), 401
        
        # Validate proposal exists and user has access
        proposal = Proposal.query.filter_by(id=proposal_id, user_id=user_id).first()
        if not proposal:
            return jsonify({"error": "Proposal not found or access denied"}), 404
        
        export_format = request.args.get("format", "csv").lower()
        
        if export_format not in ["csv", "xlsx", "pdf"]:
            return jsonify({"error": "Unsupported export format"}), 400
        
        # Get requirements
        requirements = Requirement.query.filter_by(proposal_id=proposal_id).order_by(Requirement.requirement_id).all()
        
        if export_format == "csv":
            return _export_csv(requirements, proposal.name)
        elif export_format == "xlsx":
            return _export_xlsx(requirements, proposal.name)
        else:  # pdf
            return _export_pdf(requirements, proposal.name)
        
    except Exception as e:
        logger.error(f"Failed to export compliance matrix: {e}")
        return jsonify({"error": str(e)}), 500


def _export_csv(requirements: List[Requirement], proposal_name: str) -> Any:
    """Export requirements as CSV."""
    import io
    import csv
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Requirement ID", "Requirement Text", "Section Reference", 
        "Page Number", "Source Document", "Assigned Owner", "Status", "Notes"
    ])
    
    # Write data
    for req in requirements:
        writer.writerow([
            req.requirement_id,
            req.requirement_text,
            req.section_ref,
            req.page_number or "",
            req.source_document,
            req.assigned_owner or "",
            req.status,
            req.notes or ""
        ])
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=compliance_matrix_{proposal_name}.csv"}
    )


def _export_xlsx(requirements: List[Requirement], proposal_name: str) -> Any:
    """Export requirements as XLSX."""
    try:
        import pandas as pd
        
        data = []
        for req in requirements:
            data.append({
                "Requirement ID": req.requirement_id,
                "Requirement Text": req.requirement_text,
                "Section Reference": req.section_ref,
                "Page Number": req.page_number or "",
                "Source Document": req.source_document,
                "Assigned Owner": req.assigned_owner or "",
                "Status": req.status,
                "Notes": req.notes or ""
            })
        
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Compliance Matrix', index=False)
        
        output.seek(0)
        
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment;filename=compliance_matrix_{proposal_name}.xlsx"}
        )
        
    except ImportError:
        return jsonify({"error": "XLSX export requires pandas and openpyxl packages"}), 500


def _export_pdf(requirements: List[Requirement], proposal_name: str) -> Any:
    """Export requirements as PDF."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
        from reportlab.lib import colors
        
        import io
        output = io.BytesIO()
        
        doc = SimpleDocTemplate(output, pagesize=letter)
        elements = []
        
        # Create table data
        data = [["Requirement ID", "Requirement Text", "Section", "Owner", "Status"]]
        
        for req in requirements:
            data.append([
                req.requirement_id,
                req.requirement_text[:100] + "..." if len(req.requirement_text) > 100 else req.requirement_text,
                req.section_ref,
                req.assigned_owner or "",
                req.status
            ])
        
        # Create table
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        doc.build(elements)
        
        output.seek(0)
        
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment;filename=compliance_matrix_{proposal_name}.pdf"}
        )
        
    except ImportError:
        return jsonify({"error": "PDF export requires reportlab package"}), 500

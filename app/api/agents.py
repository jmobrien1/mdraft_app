"""
API endpoints for AI agents including the Compliance Matrix Agent.

This module provides RESTful endpoints for running AI agents on RFP documents
and managing the results.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app, make_response
from flask_login import login_required, current_user
from sqlalchemy.orm import Session

from ..extensions import db
from ..models import Proposal, ProposalDocument, Requirement, User
from ..services.rfp_data_layer import RFPDataLayer
from ..agents.compliance_agent import ComplianceAgent
from ..conversion import process_job
from ..auth.utils import get_request_user_id_or_none
from ..utils.csrf import csrf_exempt_for_api


bp = Blueprint("agents", __name__, url_prefix="/api/agents")
logger = logging.getLogger(__name__)


@bp.route("/compliance-matrix/run", methods=["POST"])
@login_required
@csrf_exempt_for_api
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
        
        # Get owner filter and validate proposal access
        from ..auth.ownership import get_owner_filter
        from ..auth.visitor import get_or_create_visitor_session_id
        
        if not getattr(current_user, "is_authenticated", False):
            resp = make_response()
            vid, resp = get_or_create_visitor_session_id(resp)
        
        owner_filter = get_owner_filter()
        proposal = Proposal.query.filter_by(id=proposal_id, **owner_filter).first()
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
        
        # Check if there was an error (like no documents)
        if "error" in result:
            logger.warning(f"Compliance matrix agent warning for proposal {proposal_id}: {result['error']}")
            return jsonify(result), 422
        
        logger.info(f"Compliance matrix agent completed for proposal {proposal_id} in {processing_time:.2f}s")
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Compliance matrix agent failed: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/compliance-matrix/proposals", methods=["POST"])
@login_required
@csrf_exempt_for_api
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
        "visitor_session_id": null,
        "status": "active",
        "created_at": "2024-01-01T00:00:00Z"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        name = data.get("name")
        if not name or not name.strip():
            return jsonify({"error": "name is required and cannot be empty"}), 400
        
        description = data.get("description", "").strip()
        
        # Get owner ID for creation (authenticated users only)
        from ..auth.ownership import get_owner_id_for_creation
        
        owner_id = get_owner_id_for_creation()
        logger.info(f"Owner ID for creation: {owner_id}")
        if not owner_id:
            return jsonify({"error": "Unable to determine owner for proposal creation"}), 400
        
        # Create proposal for authenticated user
        from ..models import Proposal
        
        proposal = Proposal(
            name=name.strip(),
            description=description,
            status="active",
            user_id=owner_id
        )
        
        db.session.add(proposal)
        db.session.commit()
        
        response_data = {
            "id": proposal.id,
            "name": proposal.name,
            "description": proposal.description,
            "user_id": proposal.user_id,
            "visitor_session_id": proposal.visitor_session_id,
            "status": proposal.status,
            "created_at": proposal.created_at.isoformat(),
            "is_anonymous": False
        }
        
        return jsonify(response_data), 201
        
    except Exception as e:
        logger.error(f"Failed to create proposal: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/compliance-matrix/proposals", methods=["GET"])
@login_required
@csrf_exempt_for_api
def list_proposals() -> Any:
    """List all proposals for the current authenticated user.
    
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
                "created_at": "2024-01-01T00:00:00Z",
                "is_anonymous": false
            }
        ]
    }
    """
    try:
        status = request.args.get("status")
        
        # Get owner filter for authenticated user
        from ..auth.ownership import get_owner_filter
        
        owner_filter = get_owner_filter()
        query = Proposal.query.filter_by(**owner_filter)
        
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
                "created_at": proposal.created_at.isoformat(),
                "is_anonymous": False
            })
        
        return jsonify({"proposals": result}), 200
        
    except Exception as e:
        logger.error(f"Failed to list proposals: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/compliance-matrix/proposals/<int:proposal_id>/documents", methods=["GET"])
@login_required
@csrf_exempt_for_api
def get_proposal_documents(proposal_id: int) -> Any:
    """Get all documents for a proposal.
    
    Returns:
    {
        "documents": [
            {
                "id": 456,
                "filename": "RFP-2024-001.pdf",
                "document_type": "main_rfp",
                "created_at": "2024-01-01T00:00:00Z"
            }
        ]
    }
    """
    try:
        # Get owner filter and validate proposal access
        from ..auth.ownership import get_owner_filter
        from ..auth.visitor import get_or_create_visitor_session_id
        
        if not getattr(current_user, "is_authenticated", False):
            resp = make_response()
            vid, resp = get_or_create_visitor_session_id(resp)
        
        owner_filter = get_owner_filter()
        proposal = Proposal.query.filter_by(id=proposal_id, **owner_filter).first()
        if not proposal:
            return jsonify({"error": "Proposal not found or access denied"}), 404
        
        # Get documents for the proposal
        documents = ProposalDocument.query.filter_by(proposal_id=proposal_id).all()
        
        result = []
        for doc in documents:
            result.append({
                "id": doc.id,
                "filename": doc.filename,
                "document_type": doc.document_type,
                "created_at": doc.created_at.isoformat()
            })
        
        return jsonify({
            "documents": result
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get proposal documents: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/compliance-matrix/proposals/<int:proposal_id>/documents", methods=["POST"])
@login_required
@csrf_exempt_for_api
def add_document_to_proposal(proposal_id: int) -> Any:
    """Add a document to a proposal for processing.
    
    This endpoint handles file upload and document processing for proposals.
    
    Request: multipart/form-data OR JSON
    - file: The document file (for direct upload)
    - document_type: Type of document (main_rfp, pws, soo, spec, etc.)
    - conversion_id: ID of existing conversion (alternative to file upload)
    - conversion_ids: Array of conversion IDs (for bulk attachment)
    
    Returns:
    {
        "attached": [
            {
                "id": 456,
                "filename": "RFP-2024-001.pdf",
                "document_type": "main_rfp",
                "status": "completed",
                "created_at": "2024-01-01T00:00:00Z"
            }
        ]
    }
    """
    try:
        # Get owner filter for authenticated user
        from ..auth.ownership import get_owner_filter
        
        owner_filter = get_owner_filter()
        proposal = Proposal.query.filter_by(id=proposal_id, **owner_filter).first()
        if not proposal:
            return jsonify({"error": "Proposal not found or access denied"}), 404
        
        attached_documents = []
        
        # Check if this is a bulk attachment of existing conversions
        if request.is_json:
            data = request.get_json()
            conversion_ids = data.get("conversion_ids", [])
            single_conversion_id = data.get("conversion_id")
            
            if single_conversion_id:
                conversion_ids = [single_conversion_id]
            
            if conversion_ids:
                # Attach existing conversions
                from ..models_conversion import Conversion
                
                for conv_id in conversion_ids:
                    try:
                        conv_id = str(conv_id).strip()
                        conversion = Conversion.query.get(conv_id)
                        
                        if not conversion:
                            continue
                        
                        # Check ownership
                        if not (conversion.user_id == proposal.user_id or 
                               conversion.visitor_session_id == proposal.visitor_session_id):
                            continue
                        
                        document_type = data.get("document_type", "main_rfp")
                        
                        # Check for existing association (idempotence)
                        existing_doc = ProposalDocument.query.filter_by(
                            proposal_id=proposal_id,
                            filename=conversion.filename
                        ).first()
                        
                        if existing_doc:
                            # Document already attached - return existing
                            attached_documents.append({
                                "id": existing_doc.id,
                                "filename": existing_doc.filename,
                                "document_type": existing_doc.document_type,
                                "status": "already_attached",
                                "created_at": existing_doc.created_at.isoformat()
                            })
                            continue
                        
                        # Add document to proposal
                        rfp_data_layer = RFPDataLayer()
                        doc = rfp_data_layer.add_document_to_proposal(
                            proposal_id=proposal_id,
                            filename=conversion.filename,
                            document_type=document_type,
                            gcs_uri=conversion.stored_uri,
                            parsed_text=conversion.markdown
                        )
                        
                        attached_documents.append({
                            "id": doc.id,
                            "filename": doc.filename,
                            "document_type": doc.document_type,
                            "status": "completed",
                            "created_at": doc.created_at.isoformat()
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to attach conversion {conv_id}: {e}")
                        continue
                
                return jsonify({"attached": attached_documents}), 201
        
        # Handle file upload (existing logic)
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        
        document_type = request.form.get("document_type", "main_rfp")
        if not document_type or not document_type.strip():
            return jsonify({"error": "document_type is required"}), 400
        
        # Process the file using existing conversion pipeline
        from ..utils import generate_job_id, is_file_allowed
        from ..auth.ownership import get_owner_id_for_creation
        
        if not is_file_allowed(file.filename):
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
        
        # Get owner ID for job creation
        owner_id = get_owner_id_for_creation()
        if not owner_id:
            return jsonify({"error": "Unable to determine owner for job creation"}), 400
        
        # Create job for processing
        from ..models import Job
        job = Job(
            user_id=owner_id,
            filename=filename,
            status="PENDING",
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
                document_type=document_type.strip(),
                gcs_uri=gcs_uri,
                parsed_text=markdown_content
            )
            
            attached_documents.append({
                "id": doc.id,
                "filename": doc.filename,
                "document_type": doc.document_type,
                "status": "completed",
                "created_at": doc.created_at.isoformat()
            })
            
            return jsonify({"attached": attached_documents}), 201
            
        except Exception as e:
            logger.error(f"Failed to process document: {e}")
            db.session.rollback()
            return jsonify({"error": f"Document processing failed: {str(e)}"}), 500
        
    except Exception as e:
        logger.error(f"Failed to add document to proposal: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/compliance-matrix/proposals/<int:proposal_id>/requirements", methods=["GET"])
@login_required
@csrf_exempt_for_api
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
        # Get owner filter and validate proposal access
        from ..auth.ownership import get_owner_filter
        from ..auth.visitor import get_or_create_visitor_session_id
        
        if not getattr(current_user, "is_authenticated", False):
            resp = make_response()
            vid, resp = get_or_create_visitor_session_id(resp)
        
        owner_filter = get_owner_filter()
        proposal = Proposal.query.filter_by(id=proposal_id, **owner_filter).first()
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
        
        # Build response
        result = []
        for req in requirements:
            result.append({
                "id": req.requirement_id,
                "text": req.requirement_text,
                "section_ref": req.section_ref,
                "page_number": req.page_number,
                "source_document": req.source_document,
                "assigned_owner": req.assigned_owner,
                "status": req.status,
                "notes": req.notes,
                "created_at": req.created_at.isoformat()
            })
        
        return jsonify({
            "proposal_id": proposal_id,
            "total_requirements": len(result),
            "requirements": result
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get proposal requirements: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/compliance-matrix/requirements/<string:requirement_id>", methods=["PUT"])
@login_required
@csrf_exempt_for_api
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
        
        # Get owner filter and validate proposal access
        from ..auth.ownership import get_owner_filter
        
        owner_filter = get_owner_filter()
        proposal = Proposal.query.filter_by(id=proposal_id, **owner_filter).first()
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
@csrf_exempt_for_api
def export_compliance_matrix(proposal_id: int) -> Any:
    """Export compliance matrix as CSV, XLSX, or PDF.
    
    Query parameters:
    - format: Export format (csv, xlsx, pdf) - defaults to csv
    
    Returns:
    - CSV/XLSX: File download
    - PDF: File download
    """
    try:
        # Get owner filter and validate proposal access
        from ..auth.ownership import get_owner_filter
        
        owner_filter = get_owner_filter()
        proposal = Proposal.query.filter_by(id=proposal_id, **owner_filter).first()
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


@bp.route("/compliance-matrix/proposals/<int:proposal_id>", methods=["GET"])
@login_required
@csrf_exempt_for_api
def get_proposal_detail(proposal_id: int) -> Any:
    """Get detailed information about a specific proposal.
    
    Returns:
    {
        "id": 123,
        "name": "RFP-2024-001",
        "description": "Software development services RFP",
        "status": "active",
        "user_id": 456,
        "visitor_session_id": null,
        "document_count": 3,
        "requirement_count": 45,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "is_anonymous": false
    }
    """
    try:
        # Get owner filter and validate proposal access
        from ..auth.ownership import get_owner_filter
        
        owner_filter = get_owner_filter()
        proposal = Proposal.query.filter_by(id=proposal_id, **owner_filter).first()
        if not proposal:
            return jsonify({"error": "Proposal not found or access denied"}), 404
        
        # Get document and requirement counts
        doc_count = ProposalDocument.query.filter_by(proposal_id=proposal.id).count()
        req_count = Requirement.query.filter_by(proposal_id=proposal.id).count()
        
        result = {
            "id": proposal.id,
            "name": proposal.name,
            "description": proposal.description,
            "status": proposal.status,
            "user_id": proposal.user_id,
            "visitor_session_id": proposal.visitor_session_id,
            "document_count": doc_count,
            "requirement_count": req_count,
            "created_at": proposal.created_at.isoformat(),
            "updated_at": proposal.updated_at.isoformat(),
            "is_anonymous": proposal.user_id is None
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Failed to get proposal detail: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/compliance-matrix/proposals/<int:proposal_id>", methods=["DELETE"])
@login_required
@csrf_exempt_for_api
def delete_proposal(proposal_id: int) -> Any:
    """Delete a proposal and all its associated documents and requirements.
    
    Returns:
    {
        "status": "success",
        "message": "Proposal deleted successfully"
    }
    """
    try:
        # Get owner filter and validate proposal access
        from ..auth.ownership import get_owner_filter
        
        owner_filter = get_owner_filter()
        proposal = Proposal.query.filter_by(id=proposal_id, **owner_filter).first()
        if not proposal:
            return jsonify({"error": "Proposal not found or access denied"}), 404
        
        # Delete the proposal (cascade will handle documents and requirements)
        db.session.delete(proposal)
        db.session.commit()
        
        logger.info(f"Proposal {proposal_id} deleted successfully")
        return jsonify({
            "status": "success",
            "message": "Proposal deleted successfully"
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to delete proposal: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/compliance-matrix/proposals/<int:proposal_id>/documents/<int:document_id>", methods=["DELETE"])
@login_required
@csrf_exempt_for_api
def detach_document_from_proposal(proposal_id: int, document_id: int) -> Any:
    """Detach a document from a proposal.
    
    This endpoint removes the association between a document and a proposal.
    The document file itself is not deleted from storage.
    
    Returns:
    {
        "status": "success",
        "message": "Document detached successfully"
    }
    """
    try:
        # Get owner filter and validate proposal access
        from ..auth.ownership import get_owner_filter
        
        owner_filter = get_owner_filter()
        proposal = Proposal.query.filter_by(id=proposal_id, **owner_filter).first()
        if not proposal:
            return jsonify({"error": "Proposal not found or access denied"}), 404
        
        # Find the document within this proposal
        document = ProposalDocument.query.filter_by(
            id=document_id, 
            proposal_id=proposal_id
        ).first()
        if not document:
            return jsonify({"error": "Document not found in this proposal"}), 404
        
        # Delete the document (this removes the association)
        db.session.delete(document)
        db.session.commit()
        
        logger.info(f"Document {document_id} detached from proposal {proposal_id}")
        return jsonify({
            "status": "success",
            "message": "Document detached successfully"
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to detach document: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

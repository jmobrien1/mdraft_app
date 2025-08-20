"""
Document Ingestion Service for mdraft.

This module provides utilities for ingesting documents, extracting text,
detecting UCF sections, and building content indexes for the compliance agent.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from flask import current_app
from sqlalchemy.orm import Session

from ..extensions import db
from ..models import ProposalDocument
from ..storage_adapter import get_storage


@dataclass
class SectionInfo:
    """Information about a detected UCF section."""
    section_id: str  # A, B, C, etc.
    title: str
    start_page: int
    end_page: Optional[int] = None
    content: str = ""


class DocumentIngestionService:
    """Service for ingesting documents and extracting structured content."""
    
    def __init__(self, db_session: Optional[Session] = None):
        self.db_session = db_session or db.session
        self.logger = logging.getLogger(__name__)
        
        # UCF section patterns
        self.section_patterns = {
            'A': r'^SECTION A\s*[-–—]\s*(.+)$',
            'B': r'^SECTION B\s*[-–—]\s*(.+)$', 
            'C': r'^SECTION C\s*[-–—]\s*(.+)$',
            'D': r'^SECTION D\s*[-–—]\s*(.+)$',
            'E': r'^SECTION E\s*[-–—]\s*(.+)$',
            'F': r'^SECTION F\s*[-–—]\s*(.+)$',
            'G': r'^SECTION G\s*[-–—]\s*(.+)$',
            'H': r'^SECTION H\s*[-–—]\s*(.+)$',
            'I': r'^SECTION I\s*[-–—]\s*(.+)$',
            'J': r'^SECTION J\s*[-–—]\s*(.+)$',
            'K': r'^SECTION K\s*[-–—]\s*(.+)$',
            'L': r'^SECTION L\s*[-–—]\s*(.+)$',
            'M': r'^SECTION M\s*[-–—]\s*(.+)$',
        }
    
    def ingest_document(self, doc_id: int) -> Dict[str, Any]:
        """Ingest a document and extract structured content."""
        try:
            doc = ProposalDocument.query.get(doc_id)
            if not doc:
                raise ValueError(f"Document {doc_id} not found")
            
            self.logger.info(f"Starting ingestion for document {doc_id}: {doc.filename}")
            
            # Extract text from the document
            text_content = self._extract_text(doc)
            if not text_content:
                self.logger.warning(f"No text content extracted from document {doc_id}")
                return {"status": "error", "message": "No text content extracted"}
            
            # Detect UCF sections
            sections = self._detect_ucf_sections(text_content)
            
            # Update document with parsed content
            doc.parsed_text = text_content
            doc.ingestion_status = "ready"
            doc.available_sections = list(sections.keys()) or []  # Ensure it's never None
            
            # Store section mapping as JSON
            section_mapping = {
                section_id: {
                    "title": section.title,
                    "start_page": section.start_page,
                    "end_page": section.end_page,
                    "content_length": len(section.content)
                }
                for section_id, section in sections.items()
            }
            doc.section_mapping = section_mapping
            
            self.db_session.commit()
            
            self.logger.info(f"Document {doc_id} ingested successfully. Found sections: {list(sections.keys())}")
            
            return {
                "status": "ready",
                "available_sections": list(sections.keys()),
                "total_content_length": len(text_content)
            }
            
        except Exception as e:
            # Rollback first to avoid PendingRollbackError
            try:
                self.db_session.rollback()
            except Exception:
                pass  # Ignore rollback errors
            
            # Log the error with the doc_id we captured earlier
            self.logger.exception(f"Failed to ingest document {doc_id}")
            
            # Try to update document status to error (in a new transaction)
            try:
                if doc:
                    doc.ingestion_status = "error"
                    doc.ingestion_error = str(e)[:500]
                    self.db_session.commit()
            except Exception as update_error:
                self.logger.error(f"Failed to update document {doc_id} error status: {update_error}")
                # Don't let this error propagate
            
            return {"status": "error", "message": str(e)}
    
    def _extract_text(self, doc: ProposalDocument) -> str:
        """Extract text content from a document."""
        try:
            storage = get_storage()
            
            if not doc.gcs_uri:
                self.logger.error(f"No storage URI for document {doc.id}")
                return ""
            
            # Check if file exists
            if not storage.exists(doc.gcs_uri):
                self.logger.error(f"Document file not found: {doc.gcs_uri}")
                return ""
            
            # Extract text based on file type
            if doc.filename.lower().endswith('.pdf'):
                return self._extract_pdf_text(doc.gcs_uri)
            else:
                # For non-PDF files, try to read as text
                return self._extract_text_file(doc.gcs_uri)
                
        except Exception as e:
            self.logger.exception(f"Error extracting text from document {doc.id}")
            return ""
    
    def _extract_pdf_text(self, storage_uri: str) -> str:
        """Extract text from PDF using the PDF backend service."""
        try:
            from app.services.pdf_backend import extract_text_from_pdf
            
            storage = get_storage()
            with storage.open(storage_uri) as file_stream:
                # Save to temporary file for PDF processing
                import tempfile
                import os
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    # Copy file stream to temporary file
                    while True:
                        chunk = file_stream.read(8192)
                        if not chunk:
                            break
                        tmp_file.write(chunk)
                    tmp_file.flush()
                    
                    try:
                        # Extract text using PDF backend
                        text = extract_text_from_pdf(tmp_file.name)
                        return text
                    finally:
                        # Clean up temporary file
                        try:
                            os.unlink(tmp_file.name)
                        except Exception:
                            pass
                
        except ImportError:
            self.logger.error("PDF backend service not available")
            raise RuntimeError("PDF backend service not available. Install pdfminer.six, PyMuPDF, or pypdf")
        except Exception as e:
            self.logger.exception(f"Error extracting PDF text from {storage_uri}")
            if "No PDF text backend available" in str(e):
                raise RuntimeError("No PDF text backend available. Install pdfminer.six, PyMuPDF, or pypdf")
            else:
                raise RuntimeError(f"PDF text extraction failed: {str(e)}")
    
    def _extract_text_file(self, storage_uri: str) -> str:
        """Extract text from a text file."""
        try:
            storage = get_storage()
            with storage.open(storage_uri) as file_stream:
                return file_stream.read().decode('utf-8', errors='ignore')
        except Exception as e:
            self.logger.exception(f"Error extracting text from file {storage_uri}")
            return ""
    
    def _detect_ucf_sections(self, text: str) -> Dict[str, SectionInfo]:
        """Detect UCF sections in the text content."""
        sections = {}
        lines = text.split('\n')
        
        current_section = None
        current_content = []
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            
            # Check for section headers
            for section_id, pattern in self.section_patterns.items():
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    # Save previous section if exists
                    if current_section:
                        sections[current_section.section_id] = current_section
                    
                    # Start new section
                    title = match.group(1).strip()
                    current_section = SectionInfo(
                        section_id=section_id,
                        title=title,
                        start_page=self._estimate_page_number(line_num, lines),
                        content=""
                    )
                    current_content = []
                    break
            else:
                # Not a section header, add to current section content
                if current_section:
                    current_content.append(line)
        
        # Save the last section
        if current_section:
            current_section.content = '\n'.join(current_content)
            current_section.end_page = self._estimate_page_number(len(lines), lines)
            sections[current_section.section_id] = current_section
        
        return sections
    
    def _estimate_page_number(self, line_index: int, all_lines: List[str]) -> int:
        """Estimate page number based on line position."""
        # Rough estimate: 50 lines per page
        return (line_index // 50) + 1


def ingest_document_async(doc_id: int) -> None:
    """Async wrapper for document ingestion."""
    try:
        # Propagate request ID for logging correlation
        from flask import g
        request_id = getattr(g, 'request_id', None)
        if request_id:
            current_app.logger.info(f"Starting async ingestion for document {doc_id} (request_id: {request_id})")
        
        service = DocumentIngestionService()
        result = service.ingest_document(doc_id)
        
        if request_id:
            current_app.logger.info(f"Async ingestion completed for document {doc_id} (request_id: {request_id}): {result}")
        else:
            current_app.logger.info(f"Async ingestion completed for document {doc_id}: {result}")
            
    except Exception as e:
        from flask import g
        request_id = getattr(g, 'request_id', None)
        if request_id:
            current_app.logger.exception(f"Async ingestion failed for document {doc_id} (request_id: {request_id})")
        else:
            current_app.logger.exception(f"Async ingestion failed for document {doc_id}")


def ingest_document_sync(doc_id: int) -> Dict[str, Any]:
    """Synchronous document ingestion."""
    # Propagate request ID for logging correlation
    from flask import g
    request_id = getattr(g, 'request_id', None)
    if request_id:
        current_app.logger.info(f"Starting sync ingestion for document {doc_id} (request_id: {request_id})")
    
    service = DocumentIngestionService()
    result = service.ingest_document(doc_id)
    
    if request_id:
        current_app.logger.info(f"Sync ingestion completed for document {doc_id} (request_id: {request_id}): {result}")
    else:
        current_app.logger.info(f"Sync ingestion completed for document {doc_id}: {result}")
    
    return result

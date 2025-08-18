"""
RFP Data Layer Service for Compliance Matrix Agent.

This module provides utilities for managing multi-file RFP packages,
detecting UCF sections (A-M), following Section J pointers to PWS/SOO/specs,
and collating document content for requirement extraction.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from flask import current_app
from sqlalchemy.orm import Session

from ..extensions import db
from ..models import Proposal, ProposalDocument, Requirement


@dataclass
class SectionInfo:
    """Information about a detected UCF section."""
    section_id: str  # A, B, C, etc.
    title: str
    start_page: int
    end_page: Optional[int] = None
    content: str = ""


@dataclass
class DocumentReference:
    """Reference to a document mentioned in Section J."""
    filename: str
    document_type: str  # 'pws', 'soo', 'spec', etc.
    section_ref: str  # J.1, J.2, etc.


class RFPDataLayer:
    """Service for managing RFP data and document collation."""
    
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
        
        # Section J attachment patterns
        self.attachment_patterns = {
            'pws': r'(?:PWS|Performance Work Statement|Statement of Work)',
            'soo': r'(?:SOO|Statement of Objectives)',
            'spec': r'(?:Specification|Spec|Technical Specification)',
            'attachment': r'(?:Attachment|Att\.|Appendix)',
        }
    
    def create_proposal(self, user_id: int, name: str, description: Optional[str] = None) -> Proposal:
        """Create a new proposal record."""
        proposal = Proposal(
            user_id=user_id,
            name=name,
            description=description
        )
        self.db_session.add(proposal)
        self.db_session.commit()
        self.logger.info(f"Created proposal {proposal.id}: {name}")
        return proposal
    
    def add_document_to_proposal(self, proposal_id: int, filename: str, 
                                document_type: str, gcs_uri: Optional[str] = None,
                                parsed_text: Optional[str] = None) -> ProposalDocument:
        """Add a document to a proposal."""
        doc = ProposalDocument(
            proposal_id=proposal_id,
            filename=filename,
            document_type=document_type,
            gcs_uri=gcs_uri,
            parsed_text=parsed_text
        )
        self.db_session.add(doc)
        self.db_session.commit()
        self.logger.info(f"Added document {doc.id} to proposal {proposal_id}: {filename}")
        return doc
    
    def detect_ucf_sections(self, text: str) -> Dict[str, SectionInfo]:
        """Detect UCF sections (A-M) in document text."""
        sections = {}
        lines = text.split('\n')
        current_section = None
        current_content = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Check for section headers
            section_found = False
            for section_id, pattern in self.section_patterns.items():
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    # Save previous section if exists
                    if current_section:
                        current_section.content = '\n'.join(current_content)
                        sections[current_section.section_id] = current_section
                    
                    # Start new section
                    title = match.group(1).strip()
                    current_section = SectionInfo(
                        section_id=section_id,
                        title=title,
                        start_page=self._estimate_page_number(i, lines),
                        content=""
                    )
                    current_content = []
                    section_found = True
                    break
            
            # Add line to current section content (if not a section header)
            if current_section and not section_found:
                current_content.append(line)
        
        # Save final section
        if current_section:
            current_section.content = '\n'.join(current_content)
            sections[current_section.section_id] = current_section
        
        self.logger.info(f"Detected {len(sections)} UCF sections: {list(sections.keys())}")
        return sections
    
    def extract_section_j_references(self, section_j_content: str) -> List[DocumentReference]:
        """Extract document references from Section J content."""
        references = []
        lines = section_j_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for attachment patterns
            for doc_type, pattern in self.attachment_patterns.items():
                if re.search(pattern, line, re.IGNORECASE):
                    # Try to extract filename
                    filename_match = re.search(r'([A-Za-z0-9_\-\s]+\.(?:pdf|docx?|txt))', line)
                    if filename_match:
                        filename = filename_match.group(1).strip()
                        # Try to extract section reference
                        section_match = re.search(r'([A-Z]\.\d+)', line)
                        section_ref = section_match.group(1) if section_match else "J.1"
                        
                        references.append(DocumentReference(
                            filename=filename,
                            document_type=doc_type,
                            section_ref=section_ref
                        ))
                        break
        
        self.logger.info(f"Extracted {len(references)} document references from Section J")
        return references
    
    def get_proposal_documents(self, proposal_id: int) -> List[ProposalDocument]:
        """Get all documents for a proposal."""
        return ProposalDocument.query.filter_by(proposal_id=proposal_id).all()
    
    def get_section_content(self, proposal_id: int, section_id: str) -> Optional[str]:
        """Get content for a specific UCF section across all proposal documents."""
        documents = self.get_proposal_documents(proposal_id)
        
        for doc in documents:
            if not doc.parsed_text:
                continue
                
            sections = self.detect_ucf_sections(doc.parsed_text)
            if section_id in sections:
                return sections[section_id].content
        
        return None
    
    def get_requirements_for_proposal(self, proposal_id: int) -> List[Requirement]:
        """Get all requirements for a proposal."""
        return Requirement.query.filter_by(proposal_id=proposal_id).order_by(Requirement.requirement_id).all()
    
    def save_section_mapping(self, document_id: int, section_mapping: Dict[str, Any]) -> None:
        """Save section mapping as JSON for a document."""
        doc = ProposalDocument.query.get(document_id)
        if doc:
            doc.section_mapping = json.dumps(section_mapping)
            self.db_session.commit()
            self.logger.info(f"Saved section mapping for document {document_id}")
    
    def get_next_requirement_id(self, proposal_id: int) -> str:
        """Get the next available requirement ID (R-1, R-2, etc.)."""
        existing_requirements = Requirement.query.filter_by(proposal_id=proposal_id).all()
        existing_ids = {req.requirement_id for req in existing_requirements}
        
        counter = 1
        while f"R-{counter}" in existing_ids:
            counter += 1
        
        return f"R-{counter}"
    
    def create_requirement(self, proposal_id: int, requirement_text: str, 
                          section_ref: str, source_document: str,
                          page_number: Optional[int] = None) -> Requirement:
        """Create a new requirement record."""
        requirement_id = self.get_next_requirement_id(proposal_id)
        
        requirement = Requirement(
            proposal_id=proposal_id,
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            section_ref=section_ref,
            page_number=page_number,
            source_document=source_document
        )
        
        self.db_session.add(requirement)
        self.db_session.commit()
        self.logger.info(f"Created requirement {requirement_id} for proposal {proposal_id}")
        return requirement
    
    def update_requirement(self, requirement_id: str, proposal_id: int, 
                          **kwargs) -> Optional[Requirement]:
        """Update a requirement record."""
        requirement = Requirement.query.filter_by(
            requirement_id=requirement_id,
            proposal_id=proposal_id
        ).first()
        
        if requirement:
            for key, value in kwargs.items():
                if hasattr(requirement, key):
                    setattr(requirement, key, value)
            
            self.db_session.commit()
            self.logger.info(f"Updated requirement {requirement_id}")
            return requirement
        
        return None
    
    def _estimate_page_number(self, line_index: int, all_lines: List[str]) -> int:
        """Estimate page number based on line position."""
        # Rough estimate: 50 lines per page
        return (line_index // 50) + 1
    
    def collate_proposal_content(self, proposal_id: int, target_sections: List[str] = None) -> Dict[str, str]:
        """Collate content from all proposal documents for specified sections."""
        if target_sections is None:
            target_sections = ['C']  # Default to Section C for requirements
        
        documents = self.get_proposal_documents(proposal_id)
        collated_content = {}
        
        for section_id in target_sections:
            section_content = []
            
            for doc in documents:
                if not doc.parsed_text:
                    continue
                
                sections = self.detect_ucf_sections(doc.parsed_text)
                if section_id in sections:
                    section_content.append({
                        'document': doc.filename,
                        'content': sections[section_id].content
                    })
            
            if section_content:
                # Combine content from all documents for this section
                combined_content = []
                for item in section_content:
                    combined_content.append(f"--- From {item['document']} ---")
                    combined_content.append(item['content'])
                    combined_content.append("")
                
                collated_content[section_id] = '\n'.join(combined_content)
        
        self.logger.info(f"Collated content for sections {list(collated_content.keys())}")
        return collated_content

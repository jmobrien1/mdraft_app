"""
Compliance Matrix Agent for extracting requirements from RFP documents.

This module provides the core logic for extracting explicit requirements
("shall", "must", "will") from RFP documents using LLM processing,
assigning stable IDs, and recording exact citations.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from flask import current_app

from ..services.llm_client import chat_json
from ..services.rfp_data_layer import RFPDataLayer


@dataclass
class ExtractedRequirement:
    """A requirement extracted from RFP documents."""
    requirement_text: str
    section_ref: str
    page_number: Optional[int]
    source_document: str
    confidence: float = 1.0


class ComplianceAgent:
    """Agent for extracting compliance requirements from RFP documents."""
    
    def __init__(self, rfp_data_layer: Optional[RFPDataLayer] = None):
        self.rfp_data_layer = rfp_data_layer or RFPDataLayer()
        self.logger = logging.getLogger(__name__)
        
        # Requirement extraction patterns
        self.requirement_patterns = [
            r'\b(?:shall|must|will)\b.*?[.!?]',
            r'\b(?:required|requirement|specification)\b.*?[.!?]',
            r'\b(?:contractor\s+(?:shall|must|will))\b.*?[.!?]',
            r'\b(?:vendor\s+(?:shall|must|will))\b.*?[.!?]',
            r'\b(?:offeror\s+(?:shall|must|will))\b.*?[.!?]',
        ]
        
        # Section reference patterns
        self.section_ref_patterns = [
            r'\b([A-Z]\.\d+(?:\.\d+)*)\b',  # C.1.2, PWS 3.1, etc.
            r'\b(Section\s+[A-Z]\.\d+)\b',
            r'\b([A-Z]\s+\.\s*\d+)\b',
        ]
    
    def extract_requirements_from_proposal(self, proposal_id: int, 
                                         target_sections: List[str] = None) -> List[ExtractedRequirement]:
        """Extract requirements from a proposal's documents."""
        if target_sections is None:
            target_sections = ['C']  # Default to Section C
        
        self.logger.info(f"Extracting requirements from proposal {proposal_id} for sections {target_sections}")
        
        # Get collated content for target sections
        collated_content = self.rfp_data_layer.collate_proposal_content(proposal_id, target_sections)
        
        all_requirements = []
        
        for section_id, content in collated_content.items():
            self.logger.info(f"Processing section {section_id} ({len(content)} characters)")
            
            # Extract requirements using LLM
            section_requirements = self._extract_requirements_with_llm(
                content, section_id, proposal_id
            )
            
            all_requirements.extend(section_requirements)
        
        # Remove duplicates and sort
        unique_requirements = self._deduplicate_requirements(all_requirements)
        
        self.logger.info(f"Extracted {len(unique_requirements)} unique requirements from proposal {proposal_id}")
        return unique_requirements
    
    def _extract_requirements_with_llm(self, content: str, section_id: str, 
                                     proposal_id: int) -> List[ExtractedRequirement]:
        """Use LLM to extract requirements from document content."""
        try:
            # Prepare the prompt for LLM
            prompt = self._build_extraction_prompt(content, section_id)
            
            # Call LLM with structured output
            response = chat_json(
                messages=[
                    {"role": "system", "content": "You are a compliance matrix expert. Extract explicit requirements from RFP documents."},
                    {"role": "user", "content": prompt}
                ],
                response_json_hint=True,
                max_tokens=4000
            )
            
            # Parse the response
            requirements = self._parse_llm_response(response, section_id)
            
            return requirements
            
        except Exception as e:
            self.logger.error(f"LLM extraction failed for section {section_id}: {e}")
            # Fallback to pattern-based extraction
            return self._extract_requirements_with_patterns(content, section_id)
    
    def _build_extraction_prompt(self, content: str, section_id: str) -> str:
        """Build the prompt for LLM requirement extraction."""
        return f"""
Extract all explicit requirements from the following RFP section content. Focus on statements that use "shall", "must", "will", "required", or similar mandatory language.

Section: {section_id}
Content:
{content[:8000]}  # Limit content length for LLM

Return a JSON array of requirements with the following structure:
{{
  "requirements": [
    {{
      "requirement_text": "The exact requirement text as written in the document",
      "section_ref": "Section reference (e.g., C.1.2, PWS 3.1)",
      "page_number": null,
      "source_document": "Document name or identifier",
      "confidence": 1.0
    }}
  ]
}}

Guidelines:
1. Only extract explicit requirements (shall, must, will, required)
2. Keep the original wording exactly as written
3. Include section references when available
4. Set source_document to the document name if identifiable
5. Set confidence to 1.0 for clear requirements, 0.8 for ambiguous ones
6. Do not include requirements that are already satisfied or optional

Return only valid JSON.
"""
    
    def _parse_llm_response(self, response: str, section_id: str) -> List[ExtractedRequirement]:
        """Parse LLM response into ExtractedRequirement objects."""
        try:
            data = json.loads(response)
            requirements = []
            
            for req_data in data.get('requirements', []):
                requirement = ExtractedRequirement(
                    requirement_text=req_data.get('requirement_text', '').strip(),
                    section_ref=req_data.get('section_ref', section_id),
                    page_number=req_data.get('page_number'),
                    source_document=req_data.get('source_document', 'Unknown'),
                    confidence=req_data.get('confidence', 1.0)
                )
                
                if requirement.requirement_text:
                    requirements.append(requirement)
            
            return requirements
            
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Failed to parse LLM response: {e}")
            return []
    
    def _extract_requirements_with_patterns(self, content: str, section_id: str) -> List[ExtractedRequirement]:
        """Fallback pattern-based requirement extraction."""
        requirements = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Check for requirement patterns
            for pattern in self.requirement_patterns:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    requirement_text = match.group(0).strip()
                    
                    # Extract section reference
                    section_ref = self._extract_section_ref(line, section_id)
                    
                    # Estimate page number
                    page_number = (i // 50) + 1
                    
                    requirement = ExtractedRequirement(
                        requirement_text=requirement_text,
                        section_ref=section_ref,
                        page_number=page_number,
                        source_document='Pattern Extraction',
                        confidence=0.7
                    )
                    
                    requirements.append(requirement)
        
        return requirements
    
    def _extract_section_ref(self, text: str, default_section: str) -> str:
        """Extract section reference from text."""
        for pattern in self.section_ref_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return default_section
    
    def _deduplicate_requirements(self, requirements: List[ExtractedRequirement]) -> List[ExtractedRequirement]:
        """Remove duplicate requirements based on text similarity."""
        unique_requirements = []
        seen_texts = set()
        
        for req in requirements:
            # Normalize text for comparison
            normalized_text = self._normalize_text(req.requirement_text)
            
            if normalized_text not in seen_texts:
                seen_texts.add(normalized_text)
                unique_requirements.append(req)
        
        return unique_requirements
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for duplicate detection."""
        # Remove extra whitespace and convert to lowercase
        normalized = re.sub(r'\s+', ' ', text.strip().lower())
        # Remove punctuation for comparison
        normalized = re.sub(r'[^\w\s]', '', normalized)
        return normalized
    
    def save_requirements_to_database(self, proposal_id: int, 
                                    requirements: List[ExtractedRequirement]) -> List[Requirement]:
        """Save extracted requirements to the database."""
        saved_requirements = []
        
        for req in requirements:
            # Check if requirement already exists (by text similarity)
            existing = self._find_existing_requirement(proposal_id, req.requirement_text)
            
            if existing:
                # Update existing requirement if needed
                self.logger.info(f"Requirement already exists: {existing.requirement_id}")
                saved_requirements.append(existing)
            else:
                # Create new requirement
                requirement = self.rfp_data_layer.create_requirement(
                    proposal_id=proposal_id,
                    requirement_text=req.requirement_text,
                    section_ref=req.section_ref,
                    source_document=req.source_document,
                    page_number=req.page_number
                )
                saved_requirements.append(requirement)
        
        self.logger.info(f"Saved {len(saved_requirements)} requirements to database")
        return saved_requirements
    
    def _find_existing_requirement(self, proposal_id: int, requirement_text: str) -> Optional[Any]:
        """Find existing requirement by text similarity."""
        existing_requirements = self.rfp_data_layer.get_requirements_for_proposal(proposal_id)
        
        normalized_new_text = self._normalize_text(requirement_text)
        
        for req in existing_requirements:
            normalized_existing_text = self._normalize_text(req.requirement_text)
            
            # Check for exact match or high similarity
            if (normalized_new_text == normalized_existing_text or 
                self._calculate_similarity(normalized_new_text, normalized_existing_text) > 0.9):
                return req
        
        return None
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using simple word overlap."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def process_proposal_requirements(self, proposal_id: int, 
                                   target_sections: List[str] = None) -> Dict[str, Any]:
        """Complete workflow for processing proposal requirements."""
        try:
            # Check if proposal has documents before processing
            docs = self.rfp_data_layer.get_proposal_documents(proposal_id)
            if not docs:
                self.logger.warning(f"No documents uploaded for proposal {proposal_id}")
                return {
                    'proposal_id': proposal_id,
                    'total_requirements': 0,
                    'requirements': [],
                    'error': 'No documents uploaded for this proposal'
                }
            
            # Extract requirements
            requirements = self.extract_requirements_from_proposal(proposal_id, target_sections)
            
            # Save to database
            saved_requirements = self.save_requirements_to_database(proposal_id, requirements)
            
            # Prepare response
            result = {
                'proposal_id': proposal_id,
                'total_requirements': len(saved_requirements),
                'requirements': [
                    {
                        'id': req.requirement_id,
                        'text': req.requirement_text,
                        'section_ref': req.section_ref,
                        'page_number': req.page_number,
                        'source_document': req.source_document,
                        'assigned_owner': req.assigned_owner,
                        'status': req.status
                    }
                    for req in saved_requirements
                ]
            }
            
            self.logger.info(f"Successfully processed {len(saved_requirements)} requirements for proposal {proposal_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to process requirements for proposal {proposal_id}: {e}")
            raise

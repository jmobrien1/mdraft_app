#!/usr/bin/env python3
"""
Smoke test for Compliance Matrix Agent functionality.

This script tests the basic functionality of the compliance matrix feature
without requiring a full test environment.
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / 'app'))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    
    try:
        from models import Proposal, ProposalDocument, Requirement
        print("✓ Database models imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import database models: {e}")
        return False
    
    try:
        from services.rfp_data_layer import RFPDataLayer, SectionInfo, DocumentReference
        print("✓ RFP data layer imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import RFP data layer: {e}")
        return False
    
    try:
        from agents.compliance_agent import ComplianceAgent, ExtractedRequirement
        print("✓ Compliance agent imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import compliance agent: {e}")
        return False
    
    return True

def test_rfp_data_layer():
    """Test RFP data layer functionality."""
    print("\nTesting RFP data layer...")
    
    try:
        from services.rfp_data_layer import RFPDataLayer
        
        rfp_layer = RFPDataLayer()
        
        # Test section detection
        text = """
        SECTION A - INTRODUCTION
        This is the introduction section.
        
        SECTION C - STATEMENT OF WORK
        The contractor shall provide services.
        
        SECTION J - ATTACHMENTS
        See attached documents.
        """
        
        sections = rfp_layer.detect_ucf_sections(text)
        
        if "A" in sections and "C" in sections and "J" in sections:
            print("✓ UCF section detection works")
        else:
            print("✗ UCF section detection failed")
            return False
        
        # Test section J reference extraction
        section_j_content = """
        J.1 Performance Work Statement (PWS.pdf)
        J.2 Statement of Objectives (SOO.pdf)
        """
        
        references = rfp_layer.extract_section_j_references(section_j_content)
        
        if len(references) >= 2:
            print("✓ Section J reference extraction works")
        else:
            print("✗ Section J reference extraction failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ RFP data layer test failed: {e}")
        return False

def test_compliance_agent():
    """Test compliance agent functionality."""
    print("\nTesting compliance agent...")
    
    try:
        from agents.compliance_agent import ComplianceAgent
        
        agent = ComplianceAgent()
        
        # Test pattern-based extraction
        content = """
        C.1.2 The contractor shall provide technical support.
        C.1.3 The vendor must deliver on time.
        C.1.4 The offeror will submit monthly reports.
        """
        
        requirements = agent._extract_requirements_with_patterns(content, "C")
        
        if len(requirements) >= 3:
            print("✓ Pattern-based requirement extraction works")
        else:
            print("✗ Pattern-based requirement extraction failed")
            return False
        
        # Test deduplication
        from agents.compliance_agent import ExtractedRequirement
        
        test_requirements = [
            ExtractedRequirement(
                requirement_text="The contractor shall provide services.",
                section_ref="C.1",
                page_number=1,
                source_document="test.pdf"
            ),
            ExtractedRequirement(
                requirement_text="The contractor shall provide services.",
                section_ref="C.1",
                page_number=1,
                source_document="test.pdf"
            ),
            ExtractedRequirement(
                requirement_text="The vendor must deliver on time.",
                section_ref="C.2",
                page_number=2,
                source_document="test.pdf"
            )
        ]
        
        unique_requirements = agent._deduplicate_requirements(test_requirements)
        
        if len(unique_requirements) == 2:  # Duplicate should be removed
            print("✓ Requirement deduplication works")
        else:
            print("✗ Requirement deduplication failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Compliance agent test failed: {e}")
        return False

def test_api_endpoints():
    """Test API endpoint definitions."""
    print("\nTesting API endpoints...")
    
    try:
        from api.agents import bp as agents_bp
        
        # Check that the blueprint has the expected routes
        routes = [str(rule) for rule in agents_bp.url_map.iter_rules()]
        
        expected_routes = [
            '/api/agents/compliance-matrix/run',
            '/api/agents/compliance-matrix/proposals',
            '/api/agents/compliance-matrix/proposals/<int:proposal_id>/documents',
            '/api/agents/compliance-matrix/proposals/<int:proposal_id>/requirements',
            '/api/agents/compliance-matrix/requirements/<string:requirement_id>',
            '/api/agents/compliance-matrix/proposals/<int:proposal_id>/export'
        ]
        
        for route in expected_routes:
            if route in routes:
                print(f"✓ Route {route} exists")
            else:
                print(f"✗ Route {route} missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ API endpoints test failed: {e}")
        return False

def test_ui_routes():
    """Test UI route definitions."""
    print("\nTesting UI routes...")
    
    try:
        from ui import bp as ui_bp
        
        # Check that the blueprint has the expected routes
        routes = [str(rule) for rule in ui_bp.url_map.iter_rules()]
        
        expected_routes = [
            '/',
            '/compliance-matrix/<int:proposal_id>',
            '/proposals',
            '/api/proposals'
        ]
        
        for route in expected_routes:
            if route in routes:
                print(f"✓ Route {route} exists")
            else:
                print(f"✗ Route {route} missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ UI routes test failed: {e}")
        return False

def test_templates():
    """Test that templates exist."""
    print("\nTesting templates...")
    
    template_dir = Path(__file__).parent / 'app' / 'templates'
    
    required_templates = [
        'compliance_matrix.html',
        'proposals.html'
    ]
    
    for template in required_templates:
        template_path = template_dir / template
        if template_path.exists():
            print(f"✓ Template {template} exists")
        else:
            print(f"✗ Template {template} missing")
            return False
    
    return True

def main():
    """Run all smoke tests."""
    print("Compliance Matrix Agent - Smoke Test")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_rfp_data_layer,
        test_compliance_agent,
        test_api_endpoints,
        test_ui_routes,
        test_templates
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print(f"✗ {test.__name__} failed")
    
    print("\n" + "=" * 50)
    print(f"Smoke test results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Compliance Matrix Agent is ready.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

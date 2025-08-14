"""
Tests for schema normalization functionality.
"""
import unittest
from app.schemas.free_capabilities import normalize_requirement, normalize_compliance_matrix


class TestRequirementNormalization(unittest.TestCase):
    
    def test_normalize_requirement_will_to_shall(self):
        """Test that 'will' requirements are normalized to 'shall'."""
        item = {
            "requirement_id": "TEST-1",
            "requirement_text": "The contractor will provide documentation",
            "rfp_reference": "Section C, p.5",
            "requirement_type": "will",
            "suggested_proposal_section": "Technical Approach"
        }
        
        normalized = normalize_requirement(item)
        self.assertEqual(normalized["requirement_type"], "shall")
        self.assertEqual(normalized["requirement_id"], "TEST-1")
    
    def test_normalize_requirement_case_insensitive(self):
        """Test that normalization is case insensitive."""
        item = {
            "requirement_id": "TEST-2",
            "requirement_text": "The contractor WILL provide documentation",
            "rfp_reference": "Section C, p.5",
            "requirement_type": "WILL",
            "suggested_proposal_section": "Technical Approach"
        }
        
        normalized = normalize_requirement(item)
        self.assertEqual(normalized["requirement_type"], "shall")
    
    def test_normalize_requirement_whitespace_handling(self):
        """Test that whitespace is handled properly."""
        item = {
            "requirement_id": "TEST-3",
            "requirement_text": "The contractor will provide documentation",
            "rfp_reference": "Section C, p.5",
            "requirement_type": "  will  ",
            "suggested_proposal_section": "Technical Approach"
        }
        
        normalized = normalize_requirement(item)
        self.assertEqual(normalized["requirement_type"], "shall")
    
    def test_normalize_requirement_preserves_other_types(self):
        """Test that other requirement types are preserved."""
        test_cases = ["shall", "must", "should", "deliverable", "format", "submission"]
        
        for req_type in test_cases:
            item = {
                "requirement_id": f"TEST-{req_type}",
                "requirement_text": "Test requirement",
                "rfp_reference": "Section C, p.5",
                "requirement_type": req_type,
                "suggested_proposal_section": "Technical Approach"
            }
            
            normalized = normalize_requirement(item)
            self.assertEqual(normalized["requirement_type"], req_type)
    
    def test_normalize_requirement_unknown_type(self):
        """Test that unknown requirement types are left unchanged."""
        item = {
            "requirement_id": "TEST-4",
            "requirement_text": "Test requirement",
            "rfp_reference": "Section C, p.5",
            "requirement_type": "unknown_type",
            "suggested_proposal_section": "Technical Approach"
        }
        
        normalized = normalize_requirement(item)
        self.assertEqual(normalized["requirement_type"], "unknown_type")
    
    def test_normalize_requirement_missing_type(self):
        """Test that missing requirement_type is handled gracefully."""
        item = {
            "requirement_id": "TEST-5",
            "requirement_text": "Test requirement",
            "rfp_reference": "Section C, p.5",
            "suggested_proposal_section": "Technical Approach"
        }
        
        normalized = normalize_requirement(item)
        self.assertNotIn("requirement_type", normalized)
    
    def test_normalize_compliance_matrix(self):
        """Test normalization of entire compliance matrix."""
        matrix = [
            {
                "requirement_id": "TEST-1",
                "requirement_text": "The contractor will provide documentation",
                "rfp_reference": "Section C, p.5",
                "requirement_type": "will",
                "suggested_proposal_section": "Technical Approach"
            },
            {
                "requirement_id": "TEST-2",
                "requirement_text": "The contractor must meet deadlines",
                "rfp_reference": "Section C, p.6",
                "requirement_type": "must",
                "suggested_proposal_section": "Project Management"
            }
        ]
        
        normalized = normalize_compliance_matrix(matrix)
        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]["requirement_type"], "shall")
        self.assertEqual(normalized[1]["requirement_type"], "must")
    
    def test_normalize_compliance_matrix_non_list(self):
        """Test that non-list input is handled gracefully."""
        result = normalize_compliance_matrix("not a list")
        self.assertEqual(result, "not a list")
        
        result = normalize_compliance_matrix(None)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

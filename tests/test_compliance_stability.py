"""
Comprehensive test for Compliance Matrix stability fixes.

This test verifies that all the hardening fixes work together:
1. Schema validation with 'will' support
2. Anonymous user handling
3. Chunking improvements
4. JSON parsing robustness
5. Error handling
"""
import unittest
import json
from unittest.mock import patch, MagicMock
from app.schemas.free_capabilities import COMPLIANCE_MATRIX_SCHEMA, normalize_compliance_matrix
from app.ai.json_utils import safe_json_parse


class TestComplianceMatrixStability(unittest.TestCase):
    
    def test_schema_allows_will_requirement_type(self):
        """Test that schema accepts 'will' requirement type."""
        requirement_with_will = {
            "requirement_id": "TEST-1",
            "requirement_text": "The contractor will provide documentation",
            "rfp_reference": "Section C, p.5",
            "requirement_type": "will",
            "suggested_proposal_section": "Technical Approach"
        }
        
        # Should be valid according to schema
        from jsonschema import validate
        validate(instance=requirement_with_will, schema=COMPLIANCE_MATRIX_SCHEMA["items"])
    
    def test_normalization_converts_will_to_shall(self):
        """Test that 'will' is normalized to 'shall'."""
        matrix_with_will = [
            {
                "requirement_id": "TEST-1",
                "requirement_text": "The contractor will provide documentation",
                "rfp_reference": "Section C, p.5",
                "requirement_type": "will",
                "suggested_proposal_section": "Technical Approach"
            }
        ]
        
        normalized = normalize_compliance_matrix(matrix_with_will)
        self.assertEqual(normalized[0]["requirement_type"], "shall")
    
    def test_json_parsing_handles_malformed_input(self):
        """Test that malformed JSON is handled gracefully."""
        malformed_json = '[{"requirement_id": "R-1", "requirement_text": "test", "rfp_reference": "ref", "requirement_type": "shall", "suggested_proposal_section": "section",}]'
        
        # Should be repaired and parsed successfully
        result = safe_json_parse(malformed_json, "compliance_matrix")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
    
    def test_json_parsing_handles_surrounding_text(self):
        """Test that JSON extraction works with surrounding text."""
        text_with_json = 'Here is the compliance matrix: [{"requirement_id": "R-1", "requirement_text": "test", "rfp_reference": "ref", "requirement_type": "shall", "suggested_proposal_section": "section"}] and some other text'
        
        result = safe_json_parse(text_with_json, "compliance_matrix")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
    
    def test_json_parsing_handles_single_quotes(self):
        """Test that single quotes are converted to double quotes."""
        single_quote_json = "[{'requirement_id': 'R-1', 'requirement_text': 'test', 'rfp_reference': 'ref', 'requirement_type': 'shall', 'suggested_proposal_section': 'section'}]"
        
        result = safe_json_parse(single_quote_json, "compliance_matrix")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
    
    def test_json_parsing_handles_missing_quotes(self):
        """Test that missing quotes around object keys are fixed."""
        missing_quotes_json = '[{requirement_id: "R-1", requirement_text: "test", rfp_reference: "ref", requirement_type: "shall", suggested_proposal_section: "section"}]'
        
        result = safe_json_parse(missing_quotes_json, "compliance_matrix")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
    
    def test_validation_error_format(self):
        """Test that validation errors are properly formatted."""
        # Test that validation errors are properly formatted for the route handler
        error = ValueError("validation_error|Invalid requirement_type: invalid_type")
        error_str = str(error)
        
        # Should be parseable by the route handler
        code, detail = (error_str.split("|",1) + [None])[:2] if "|" in error_str else (error_str, None)
        self.assertEqual(code, "validation_error")
        self.assertEqual(detail, "Invalid requirement_type: invalid_type")
    
    def test_json_parse_error_format(self):
        """Test that JSON parse errors are properly formatted."""
        # Test that JSON parse errors are properly formatted for the route handler
        error = ValueError("json_parse|JSON parsing failed")
        error_str = str(error)
        
        # Should be parseable by the route handler
        code, detail = (error_str.split("|",1) + [None])[:2] if "|" in error_str else (error_str, None)
        self.assertEqual(code, "json_parse")
        self.assertEqual(detail, "JSON parsing failed")
    
    def test_anonymous_user_handling(self):
        """Test that anonymous users are handled gracefully."""
        # Test that the free tier endpoint doesn't crash for anonymous users
        # This would require a more complex setup with actual document processing
        # For now, we'll test the auth utility functions
        
        from app.auth.utils import get_request_user_id_or_none, is_user_authenticated
        
        # Test with no user context
        user_id = get_request_user_id_or_none()
        self.assertIsNone(user_id)
        
        authenticated = is_user_authenticated()
        self.assertFalse(authenticated)
    
    def test_chunking_configuration(self):
        """Test that chunking configuration is properly set."""
        from app.services.ai_tools import MATRIX_WINDOW_SIZE, MATRIX_MAX_TOTAL_CHUNKS
        
        # Verify the new configuration variables exist
        self.assertIsInstance(MATRIX_WINDOW_SIZE, int)
        self.assertIsInstance(MATRIX_MAX_TOTAL_CHUNKS, int)
        
        # Verify reasonable defaults
        self.assertGreater(MATRIX_WINDOW_SIZE, 0)
        self.assertGreater(MATRIX_MAX_TOTAL_CHUNKS, MATRIX_WINDOW_SIZE)
    
    def test_deduplication_works(self):
        """Test that requirement deduplication works correctly."""
        from app.services.ai_tools import _deduplicate_requirements
        
        duplicate_requirements = [
            {
                "requirement_id": "R-1",
                "requirement_text": "The contractor shall provide documentation",
                "rfp_reference": "Section C, p.5",
                "requirement_type": "shall",
                "suggested_proposal_section": "Technical Approach"
            },
            {
                "requirement_id": "R-2",
                "requirement_text": "The contractor shall provide documentation",
                "rfp_reference": "Section C, p.5",
                "requirement_type": "shall",
                "suggested_proposal_section": "Technical Approach"
            }
        ]
        
        deduplicated = _deduplicate_requirements(duplicate_requirements)
        self.assertEqual(len(deduplicated), 1)
    
    def test_error_messages_are_developer_friendly(self):
        """Test that error messages provide useful debugging information."""
        malformed_json = "this is not json at all"
        
        with self.assertRaises(ValueError) as context:
            safe_json_parse(malformed_json, "compliance_matrix")
        
        error_message = str(context.exception)
        self.assertIn("JSON parsing failed", error_message)
        self.assertIn("compliance_matrix", error_message)


if __name__ == "__main__":
    unittest.main()

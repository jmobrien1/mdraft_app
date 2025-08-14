"""
Tests for robust JSON parsing utilities.
"""
import unittest
from app.ai.json_utils import (
    parse_strict, attempt_repair, parse_with_repair, 
    validate_compliance_matrix, safe_json_parse
)


class TestJSONParsing(unittest.TestCase):
    
    def test_parse_strict_valid_json(self):
        """Test strict parsing with valid JSON."""
        valid_json = '{"key": "value", "array": [1, 2, 3]}'
        success, parsed, error = parse_strict(valid_json)
        
        self.assertTrue(success)
        self.assertEqual(parsed["key"], "value")
        self.assertEqual(parsed["array"], [1, 2, 3])
        self.assertIsNone(error)
    
    def test_parse_strict_invalid_json(self):
        """Test strict parsing with invalid JSON."""
        invalid_json = '{"key": "value", "array": [1, 2, 3,]}'  # trailing comma
        success, parsed, error = parse_strict(invalid_json)
        
        self.assertFalse(success)
        self.assertIsNone(parsed)
        self.assertIsNotNone(error)
        self.assertIn("JSON decode error", error)
    
    def test_attempt_repair_trailing_comma(self):
        """Test repair of trailing comma in array."""
        malformed = '[1, 2, 3,]'
        success, repaired, error = attempt_repair(malformed)
        
        self.assertTrue(success)
        self.assertEqual(repaired, '[1, 2, 3]')
        self.assertIsNone(error)
    
    def test_attempt_repair_trailing_comma_object(self):
        """Test repair of trailing comma in object."""
        malformed = '{"a": 1, "b": 2,}'
        success, repaired, error = attempt_repair(malformed)
        
        self.assertTrue(success)
        self.assertEqual(repaired, '{"a": 1, "b": 2}')
        self.assertIsNone(error)
    
    def test_attempt_repair_single_quotes(self):
        """Test repair of single quotes to double quotes."""
        malformed = "{'key': 'value'}"
        success, repaired, error = attempt_repair(malformed)
        
        self.assertTrue(success)
        self.assertEqual(repaired, '{"key": "value"}')
        self.assertIsNone(error)
    
    def test_attempt_repair_missing_quotes(self):
        """Test repair of missing quotes around object keys."""
        malformed = '{key: "value", array: [1, 2, 3]}'
        success, repaired, error = attempt_repair(malformed)
    
        self.assertTrue(success)
        # Since we prioritize arrays, this extracts the array part
        self.assertEqual(repaired, '[1, 2, 3]')
        self.assertIsNone(error)
    
    def test_attempt_repair_extract_array(self):
        """Test extraction of JSON array from surrounding text."""
        text_with_array = 'Here is the result: [1, 2, 3] and some other text'
        success, repaired, error = attempt_repair(text_with_array)
        
        self.assertTrue(success)
        self.assertEqual(repaired, '[1, 2, 3]')
        self.assertIsNone(error)
    
    def test_attempt_repair_extract_object(self):
        """Test extraction of JSON object from surrounding text."""
        text_with_object = 'Here is the result: {"key": "value"} and some other text'
        success, repaired, error = attempt_repair(text_with_object)
        
        self.assertTrue(success)
        self.assertEqual(repaired, '{"key": "value"}')
        self.assertIsNone(error)
    
    def test_parse_with_repair_success(self):
        """Test parse_with_repair with successful repair."""
        malformed = '[1, 2, 3,]'
        success, parsed, error, diagnostics = parse_with_repair(malformed)
        
        self.assertTrue(success)
        self.assertEqual(parsed, [1, 2, 3])
        self.assertIsNone(error)
        self.assertTrue(diagnostics["repair_attempted"])
        self.assertTrue(diagnostics["repair_successful"])
    
    def test_parse_with_repair_failure(self):
        """Test parse_with_repair with failed repair."""
        malformed = 'this is not json at all'
        success, parsed, error, diagnostics = parse_with_repair(malformed)
        
        self.assertFalse(success)
        self.assertIsNone(parsed)
        self.assertIsNotNone(error)
        self.assertTrue(diagnostics["repair_attempted"])
        self.assertFalse(diagnostics["repair_successful"])
    
    def test_validate_compliance_matrix_valid(self):
        """Test validation of valid compliance matrix."""
        valid_matrix = [
            {
                "requirement_id": "R-1",
                "requirement_text": "The contractor shall provide documentation",
                "rfp_reference": "Section C, p.5",
                "requirement_type": "shall",
                "suggested_proposal_section": "Technical Approach"
            }
        ]
        
        is_valid, errors = validate_compliance_matrix(valid_matrix)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_compliance_matrix_invalid_type(self):
        """Test validation with invalid requirement_type."""
        invalid_matrix = [
            {
                "requirement_id": "R-1",
                "requirement_text": "The contractor shall provide documentation",
                "rfp_reference": "Section C, p.5",
                "requirement_type": "invalid_type",
                "suggested_proposal_section": "Technical Approach"
            }
        ]
        
        is_valid, errors = validate_compliance_matrix(invalid_matrix)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("invalid requirement_type" in error for error in errors))
    
    def test_validate_compliance_matrix_missing_field(self):
        """Test validation with missing required field."""
        invalid_matrix = [
            {
                "requirement_id": "R-1",
                "requirement_text": "The contractor shall provide documentation",
                "rfp_reference": "Section C, p.5",
                # missing requirement_type
                "suggested_proposal_section": "Technical Approach"
            }
        ]
        
        is_valid, errors = validate_compliance_matrix(invalid_matrix)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("missing required field" in error for error in errors))
    
    def test_safe_json_parse_valid(self):
        """Test safe_json_parse with valid JSON."""
        valid_json = '[{"requirement_id": "R-1", "requirement_text": "test", "rfp_reference": "ref", "requirement_type": "shall", "suggested_proposal_section": "section"}]'
        
        result = safe_json_parse(valid_json, "compliance_matrix")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["requirement_id"], "R-1")
    
    def test_safe_json_parse_invalid_raises_value_error(self):
        """Test that safe_json_parse raises ValueError for invalid JSON."""
        invalid_json = 'this is not json'
        
        with self.assertRaises(ValueError) as context:
            safe_json_parse(invalid_json, "compliance_matrix")
        
        self.assertIn("JSON parsing failed", str(context.exception))
    
    def test_safe_json_parse_validation_error(self):
        """Test that safe_json_parse raises ValueError for validation errors."""
        invalid_matrix = '[{"requirement_id": "R-1"}]'  # missing required fields
        
        with self.assertRaises(ValueError) as context:
            safe_json_parse(invalid_matrix, "compliance_matrix")
        
        self.assertIn("Compliance matrix validation failed", str(context.exception))


if __name__ == "__main__":
    unittest.main()

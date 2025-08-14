"""
Tests for AI tools module.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from app.services.ai_tools import run_prompt
from app.schemas.free_capabilities import COMPLIANCE_MATRIX_SCHEMA


class TestAITools(unittest.TestCase):
    
    def setUp(self):
        # Create a temporary prompt file
        self.temp_dir = tempfile.mkdtemp()
        self.prompt_path = os.path.join(self.temp_dir, "test_prompt.txt")
        
        with open(self.prompt_path, 'w', encoding='utf-8') as f:
            f.write("ROLE: Test Analyst\nGOAL: Extract test data\nOUTPUT (JSON Array): [{\"test\": \"string\"}]\n")
    
    def tearDown(self):
        # Clean up temporary files
        if os.path.exists(self.prompt_path):
            os.unlink(self.prompt_path)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    @patch('app.services.ai_tools._call_ai_model')
    def test_run_prompt_success(self, mock_call_ai):
        """Test successful prompt execution with valid JSON response."""
        # Mock AI response
        mock_response = json.dumps([
            {
                "requirement_id": "TEST-1",
                "requirement_text": "Test requirement",
                "rfp_reference": "Test Section",
                "requirement_type": "shall",
                "suggested_proposal_section": "Test Section"
            }
        ])
        mock_call_ai.return_value = mock_response
        
        # Test with compliance matrix schema
        result = run_prompt(self.prompt_path, "Test RFP text", COMPLIANCE_MATRIX_SCHEMA)
        
        # Verify result
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["requirement_id"], "TEST-1")
        
        # Verify AI was called
        mock_call_ai.assert_called_once()
        call_args = mock_call_ai.call_args
        self.assertIn("You are a proposal analysis expert", call_args[0][0])
        self.assertIn("Test RFP text", call_args[0][1])
    
    @patch('app.services.ai_tools._call_ai_model')
    def test_run_prompt_invalid_json_retry(self, mock_call_ai):
        """Test prompt execution with invalid JSON that gets corrected on retry."""
        # First call returns invalid JSON
        mock_call_ai.side_effect = [
            "Invalid JSON response",
            json.dumps([
                {
                    "requirement_id": "TEST-2",
                    "requirement_text": "Test requirement",
                    "rfp_reference": "Test Section",
                    "requirement_type": "shall",
                    "suggested_proposal_section": "Test Section"
                }
            ])
        ]
        
        # Test with compliance matrix schema
        result = run_prompt(self.prompt_path, "Test RFP text", COMPLIANCE_MATRIX_SCHEMA)
        
        # Verify result
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["requirement_id"], "TEST-2")
        
        # Verify AI was called twice (original + retry)
        self.assertEqual(mock_call_ai.call_count, 2)
    
    def test_run_prompt_file_not_found(self):
        """Test error handling when prompt file doesn't exist."""
        with self.assertRaises(FileNotFoundError):
            run_prompt("/nonexistent/prompt.txt", "Test RFP text", COMPLIANCE_MATRIX_SCHEMA)


if __name__ == '__main__':
    unittest.main()

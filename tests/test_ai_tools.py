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
    
    @patch('app.services.ai_tools.chat_json')
    def test_run_prompt_success(self, mock_chat_json):
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
        mock_chat_json.return_value = mock_response
        
        # Test with compliance matrix schema
        result = run_prompt(self.prompt_path, "Test RFP text", COMPLIANCE_MATRIX_SCHEMA)
        
        # Verify result
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["requirement_id"], "TEST-1")
        
        # Verify AI was called
        mock_chat_json.assert_called_once()
        call_args = mock_chat_json.call_args
        messages = call_args[0][0]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("Test RFP text", messages[1]["content"])
    
    @patch('app.services.ai_tools.chat_json')
    def test_run_prompt_invalid_json_error(self, mock_chat_json):
        """Test prompt execution with invalid JSON raises error."""
        # Mock AI response with invalid JSON
        mock_chat_json.return_value = "Invalid JSON response"
        
        # Test with compliance matrix schema - should raise ValueError
        with self.assertRaises(ValueError) as cm:
            run_prompt(self.prompt_path, "Test RFP text", COMPLIANCE_MATRIX_SCHEMA)
        
        # Verify error message contains json_parse
        self.assertIn("json_parse", str(cm.exception))
        
        # Verify AI was called once
        mock_chat_json.assert_called_once()
    
    def test_run_prompt_file_not_found(self):
        """Test error handling when prompt file doesn't exist."""
        with self.assertRaises(ValueError) as cm:
            run_prompt("/nonexistent/prompt.txt", "Test RFP text", COMPLIANCE_MATRIX_SCHEMA)
        self.assertEqual(str(cm.exception), "model_error")


if __name__ == '__main__':
    unittest.main()

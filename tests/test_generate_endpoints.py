"""
Tests for the generate endpoints.
"""

import json
import unittest
from unittest.mock import patch, MagicMock

from app import create_app
from app.models import Job, User
from app import db


class TestGenerateEndpoints(unittest.TestCase):
    
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
            
            # Create test user
            self.user = User(email="test@example.com")
            db.session.add(self.user)
            db.session.commit()
            
            # Create test job
            self.job = Job(
                user_id=self.user.id,
                filename="test_rfp.pdf",
                status="completed",
                gcs_uri="uploads/test/test_rfp.pdf",
                output_uri="processed/test_rfp.md"
            )
            db.session.add(self.job)
            db.session.commit()
    
    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
    
    @patch('app.services.text_loader.get_rfp_text')
    @patch('app.routes.run_prompt')
    def test_generate_compliance_matrix_success(self, mock_run_prompt, mock_get_text):
        """Test successful compliance matrix generation."""
        # Mock responses
        mock_get_text.return_value = "Test RFP content"
        mock_run_prompt.return_value = [
            {
                "requirement_id": "C-1",
                "requirement_text": "Test requirement",
                "rfp_reference": "Section C",
                "requirement_type": "shall",
                "suggested_proposal_section": "Technical Approach"
            }
        ]
        
        response = self.client.post(
            '/api/generate/compliance-matrix',
            json={'document_id': str(self.job.id)}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['requirement_id'], 'C-1')
        
        # Verify mocks were called
        mock_get_text.assert_called_once_with(str(self.job.id))
        mock_run_prompt.assert_called_once()
    
    def test_generate_compliance_matrix_missing_document_id(self):
        """Test error handling for missing document_id."""
        response = self.client.post(
            '/api/generate/compliance-matrix',
            json={}
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('document_id is required', data['error'])
    
    @patch('app.services.text_loader.get_rfp_text')
    def test_generate_compliance_matrix_document_not_found(self, mock_get_text):
        """Test error handling for document not found."""
        mock_get_text.side_effect = ValueError("Document not found")
        
        response = self.client.post(
            '/api/generate/compliance-matrix',
            json={'document_id': '999'}
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('Document not found', data['error'])
    
    @patch('app.services.text_loader.get_rfp_text')
    @patch('app.routes.run_prompt')
    def test_generate_evaluation_criteria_success(self, mock_run_prompt, mock_get_text):
        """Test successful evaluation criteria generation."""
        mock_get_text.return_value = "Test RFP content"
        mock_run_prompt.return_value = [
            {
                "criterion": "Technical Approach",
                "description": "Technical solution quality",
                "weight": 40.0,
                "basis": "Best Value",
                "source_section": "Section M"
            }
        ]
        
        response = self.client.post(
            '/api/generate/evaluation-criteria',
            json={'document_id': str(self.job.id)}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['criterion'], 'Technical Approach')
    
    @patch('app.services.text_loader.get_rfp_text')
    @patch('app.routes.run_prompt')
    def test_generate_annotated_outline_success(self, mock_run_prompt, mock_get_text):
        """Test successful annotated outline generation."""
        mock_get_text.return_value = "Test RFP content"
        mock_run_prompt.return_value = {
            "outline_markdown": "# Test Outline\n\n## Section 1\n\nContent here",
            "annotations": [
                {
                    "heading": "Section 1",
                    "rfp_reference": "Section L",
                    "notes": "Required section"
                }
            ]
        }
        
        response = self.client.post(
            '/api/generate/annotated-outline',
            json={'document_id': str(self.job.id)}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('outline_markdown', data)
        self.assertIn('annotations', data)
        self.assertIsInstance(data['annotations'], list)
    
    @patch('app.services.text_loader.get_rfp_text')
    @patch('app.routes.run_prompt')
    def test_generate_submission_checklist_success(self, mock_run_prompt, mock_get_text):
        """Test successful submission checklist generation."""
        mock_get_text.return_value = "Test RFP content"
        mock_run_prompt.return_value = [
            {
                "item": "Technical Volume",
                "category": "Volume",
                "details": "Submit technical approach",
                "rfp_reference": "Section L"
            }
        ]
        
        response = self.client.post(
            '/api/generate/submission-checklist',
            json={'document_id': str(self.job.id)}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['item'], 'Technical Volume')


if __name__ == '__main__':
    unittest.main()

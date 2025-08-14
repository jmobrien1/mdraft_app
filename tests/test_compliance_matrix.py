"""
Unit tests for Compliance Matrix Agent functionality.

This module tests the RFP data layer, compliance agent, and API endpoints
for the compliance matrix feature.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.models import Proposal, ProposalDocument, Requirement, User
from app.services.rfp_data_layer import RFPDataLayer, SectionInfo, DocumentReference
from app.agents.compliance_agent import ComplianceAgent, ExtractedRequirement


class TestRFPDataLayer:
    """Test the RFP Data Layer service."""
    
    def test_create_proposal(self, app, db_session):
        """Test creating a new proposal."""
        with app.app_context():
            rfp_layer = RFPDataLayer(db_session)
            
            proposal = rfp_layer.create_proposal(
                user_id=1,
                name="Test RFP",
                description="Test description"
            )
            
            assert proposal.id is not None
            assert proposal.name == "Test RFP"
            assert proposal.description == "Test description"
            assert proposal.user_id == 1
            assert proposal.status == "active"
    
    def test_add_document_to_proposal(self, app, db_session):
        """Test adding a document to a proposal."""
        with app.app_context():
            rfp_layer = RFPDataLayer(db_session)
            
            # Create proposal first
            proposal = rfp_layer.create_proposal(user_id=1, name="Test RFP")
            
            # Add document
            doc = rfp_layer.add_document_to_proposal(
                proposal_id=proposal.id,
                filename="test.pdf",
                document_type="main_rfp",
                gcs_uri="gs://bucket/test.pdf",
                parsed_text="Test document content"
            )
            
            assert doc.id is not None
            assert doc.filename == "test.pdf"
            assert doc.document_type == "main_rfp"
            assert doc.gcs_uri == "gs://bucket/test.pdf"
            assert doc.parsed_text == "Test document content"
    
    def test_detect_ucf_sections(self, app):
        """Test UCF section detection."""
        with app.app_context():
            rfp_layer = RFPDataLayer()
            
            text = """
            SECTION A - INTRODUCTION
            This is the introduction section.
            
            SECTION C - STATEMENT OF WORK
            The contractor shall provide services.
            
            SECTION J - ATTACHMENTS
            See attached documents.
            """
            
            sections = rfp_layer.detect_ucf_sections(text)
            
            assert "A" in sections
            assert "C" in sections
            assert "J" in sections
            assert sections["C"].title == "STATEMENT OF WORK"
            assert "contractor shall provide" in sections["C"].content.lower()
    
    def test_extract_section_j_references(self, app):
        """Test extracting document references from Section J."""
        with app.app_context():
            rfp_layer = RFPDataLayer()
            
            section_j_content = """
            J.1 Performance Work Statement (PWS.pdf)
            J.2 Statement of Objectives (SOO.pdf)
            J.3 Technical Specification (spec.pdf)
            """
            
            references = rfp_layer.extract_section_j_references(section_j_content)
            
            assert len(references) >= 3
            assert any(ref.document_type == "pws" for ref in references)
            assert any(ref.document_type == "soo" for ref in references)
            assert any(ref.document_type == "spec" for ref in references)
    
    def test_get_next_requirement_id(self, app, db_session):
        """Test getting next requirement ID."""
        with app.app_context():
            rfp_layer = RFPDataLayer(db_session)
            
            # Create proposal
            proposal = rfp_layer.create_proposal(user_id=1, name="Test RFP")
            
            # First requirement should be R-1
            req_id = rfp_layer.get_next_requirement_id(proposal.id)
            assert req_id == "R-1"
            
            # Create a requirement
            rfp_layer.create_requirement(
                proposal_id=proposal.id,
                requirement_text="Test requirement",
                section_ref="C.1",
                source_document="test.pdf"
            )
            
            # Next requirement should be R-2
            req_id = rfp_layer.get_next_requirement_id(proposal.id)
            assert req_id == "R-2"
    
    def test_create_requirement(self, app, db_session):
        """Test creating a requirement."""
        with app.app_context():
            rfp_layer = RFPDataLayer(db_session)
            
            # Create proposal
            proposal = rfp_layer.create_proposal(user_id=1, name="Test RFP")
            
            # Create requirement
            requirement = rfp_layer.create_requirement(
                proposal_id=proposal.id,
                requirement_text="The contractor shall provide services.",
                section_ref="C.1.2",
                source_document="RFP.pdf",
                page_number=5
            )
            
            assert requirement.requirement_id == "R-1"
            assert requirement.requirement_text == "The contractor shall provide services."
            assert requirement.section_ref == "C.1.2"
            assert requirement.source_document == "RFP.pdf"
            assert requirement.page_number == 5
            assert requirement.status == "pending"


class TestComplianceAgent:
    """Test the Compliance Agent."""
    
    def test_extract_requirements_with_patterns(self, app):
        """Test pattern-based requirement extraction."""
        with app.app_context():
            agent = ComplianceAgent()
            
            content = """
            C.1.2 The contractor shall provide technical support.
            C.1.3 The vendor must deliver on time.
            C.1.4 The offeror will submit monthly reports.
            """
            
            requirements = agent._extract_requirements_with_patterns(content, "C")
            
            assert len(requirements) >= 3
            assert any("shall provide technical support" in req.requirement_text for req in requirements)
            assert any("must deliver on time" in req.requirement_text for req in requirements)
            assert any("will submit monthly reports" in req.requirement_text for req in requirements)
    
    def test_deduplicate_requirements(self, app):
        """Test requirement deduplication."""
        with app.app_context():
            agent = ComplianceAgent()
            
            requirements = [
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
            
            unique_requirements = agent._deduplicate_requirements(requirements)
            
            assert len(unique_requirements) == 2  # Duplicate removed
    
    def test_calculate_similarity(self, app):
        """Test text similarity calculation."""
        with app.app_context():
            agent = ComplianceAgent()
            
            # Identical texts
            similarity = agent._calculate_similarity("hello world", "hello world")
            assert similarity == 1.0
            
            # Similar texts
            similarity = agent._calculate_similarity("hello world", "hello there world")
            assert similarity > 0.5
            
            # Different texts
            similarity = agent._calculate_similarity("hello world", "goodbye universe")
            assert similarity < 0.5
    
    @patch('app.agents.compliance_agent.chat_json')
    def test_extract_requirements_with_llm(self, mock_chat_json, app):
        """Test LLM-based requirement extraction."""
        with app.app_context():
            agent = ComplianceAgent()
            
            # Mock LLM response
            mock_response = {
                "requirements": [
                    {
                        "requirement_text": "The contractor shall provide technical support.",
                        "section_ref": "C.1.2",
                        "page_number": 5,
                        "source_document": "RFP.pdf",
                        "confidence": 1.0
                    }
                ]
            }
            mock_chat_json.return_value = json.dumps(mock_response)
            
            content = "C.1.2 The contractor shall provide technical support."
            requirements = agent._extract_requirements_with_llm(content, "C", 1)
            
            assert len(requirements) == 1
            assert requirements[0].requirement_text == "The contractor shall provide technical support."
            assert requirements[0].section_ref == "C.1.2"
            assert requirements[0].confidence == 1.0
    
    @patch('app.agents.compliance_agent.chat_json')
    def test_extract_requirements_with_llm_fallback(self, mock_chat_json, app):
        """Test LLM fallback to pattern-based extraction."""
        with app.app_context():
            agent = ComplianceAgent()
            
            # Mock LLM failure
            mock_chat_json.side_effect = Exception("LLM error")
            
            content = "C.1.2 The contractor shall provide technical support."
            requirements = agent._extract_requirements_with_llm(content, "C", 1)
            
            # Should fall back to pattern-based extraction
            assert len(requirements) >= 1
            assert any("shall provide" in req.requirement_text for req in requirements)


class TestComplianceMatrixAPI:
    """Test the Compliance Matrix API endpoints."""
    
    def test_create_proposal_endpoint(self, client, auth_headers):
        """Test creating a proposal via API."""
        response = client.post(
            '/api/agents/compliance-matrix/proposals',
            json={
                'name': 'Test RFP',
                'description': 'Test description'
            },
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['name'] == 'Test RFP'
        assert data['description'] == 'Test description'
        assert 'id' in data
    
    def test_list_proposals_endpoint(self, client, auth_headers):
        """Test listing proposals via API."""
        # Create a proposal first
        client.post(
            '/api/agents/compliance-matrix/proposals',
            json={'name': 'Test RFP'},
            headers=auth_headers
        )
        
        response = client.get('/api/agents/compliance-matrix/proposals', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'proposals' in data
        assert len(data['proposals']) >= 1
    
    def test_add_document_to_proposal(self, client, auth_headers):
        """Test adding a document to a proposal."""
        # Create proposal first
        proposal_response = client.post(
            '/api/agents/compliance-matrix/proposals',
            json={'name': 'Test RFP'},
            headers=auth_headers
        )
        proposal_id = proposal_response.get_json()['id']
        
        # Mock file upload
        with patch('app.api.agents.process_job') as mock_process:
            mock_process.return_value = "Mock document content"
            
            response = client.post(
                f'/api/agents/compliance-matrix/proposals/{proposal_id}/documents',
                data={
                    'file': (b'test content', 'test.pdf'),
                    'document_type': 'main_rfp'
                },
                headers=auth_headers
            )
            
            assert response.status_code == 201
            data = response.get_json()
            assert data['filename'] == 'test.pdf'
            assert data['document_type'] == 'main_rfp'
    
    @patch('app.agents.compliance_agent.ComplianceAgent.process_proposal_requirements')
    def test_run_compliance_matrix_agent(self, mock_process, client, auth_headers):
        """Test running the compliance matrix agent."""
        # Create proposal first
        proposal_response = client.post(
            '/api/agents/compliance-matrix/proposals',
            json={'name': 'Test RFP'},
            headers=auth_headers
        )
        proposal_id = proposal_response.get_json()['id']
        
        # Mock agent response
        mock_process.return_value = {
            'proposal_id': proposal_id,
            'total_requirements': 5,
            'requirements': [
                {
                    'id': 'R-1',
                    'text': 'Test requirement',
                    'section_ref': 'C.1',
                    'page_number': 1,
                    'source_document': 'test.pdf',
                    'assigned_owner': None,
                    'status': 'pending'
                }
            ]
        }
        
        response = client.post(
            '/api/agents/compliance-matrix/run',
            json={
                'proposal_id': proposal_id,
                'target_sections': ['C'],
                'force_reprocess': False
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert data['total_requirements'] == 5
        assert 'processing_time' in data
    
    def test_get_proposal_requirements(self, client, auth_headers):
        """Test getting requirements for a proposal."""
        # Create proposal and add requirement
        proposal_response = client.post(
            '/api/agents/compliance-matrix/proposals',
            json={'name': 'Test RFP'},
            headers=auth_headers
        )
        proposal_id = proposal_response.get_json()['id']
        
        # Add a requirement directly to database
        with client.application.app_context():
            from app import db
            requirement = Requirement(
                proposal_id=proposal_id,
                requirement_id='R-1',
                requirement_text='Test requirement',
                section_ref='C.1',
                source_document='test.pdf'
            )
            db.session.add(requirement)
            db.session.commit()
        
        response = client.get(
            f'/api/agents/compliance-matrix/proposals/{proposal_id}/requirements',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['proposal_id'] == proposal_id
        assert data['total_requirements'] == 1
        assert data['requirements'][0]['id'] == 'R-1'
    
    def test_update_requirement(self, client, auth_headers):
        """Test updating a requirement."""
        # Create proposal and add requirement
        proposal_response = client.post(
            '/api/agents/compliance-matrix/proposals',
            json={'name': 'Test RFP'},
            headers=auth_headers
        )
        proposal_id = proposal_response.get_json()['id']
        
        with client.application.app_context():
            from app import db
            requirement = Requirement(
                proposal_id=proposal_id,
                requirement_id='R-1',
                requirement_text='Test requirement',
                section_ref='C.1',
                source_document='test.pdf'
            )
            db.session.add(requirement)
            db.session.commit()
        
        response = client.put(
            '/api/agents/compliance-matrix/requirements/R-1',
            json={
                'proposal_id': proposal_id,
                'assigned_owner': 'John Doe',
                'status': 'in_progress',
                'notes': 'Working on this'
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['assigned_owner'] == 'John Doe'
        assert data['status'] == 'in_progress'
        assert data['notes'] == 'Working on this'


@pytest.fixture
def auth_headers():
    """Mock authentication headers for testing."""
    return {'Authorization': 'Bearer test-token'}


@pytest.fixture
def app():
    """Create a test Flask app."""
    import os
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ['SECRET_KEY'] = 'test-secret-key'
    
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def db_session(app):
    """Create a database session for testing."""
    with app.app_context():
        from app import db
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()

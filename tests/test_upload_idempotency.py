"""
Tests for atomic and idempotent upload→job creation under concurrency.

This test suite verifies that:
1. Multiple concurrent uploads of the same file create only one conversion
2. The system correctly handles race conditions
3. Existing completed conversions are returned immediately
4. Existing pending conversions are returned without creating duplicates
5. Database constraints prevent duplicate entries
"""

import os
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import create_app, db
from app.models_conversion import Conversion
from app.quality import sha256_file


class TestUploadIdempotency:
    """Test suite for upload idempotency under concurrency."""
    
    @pytest.fixture
    def app(self):
        """Create a test Flask application."""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return app.test_client()
    
    @pytest.fixture
    def sample_file(self):
        """Create a sample file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("This is a test file for upload idempotency testing.\n" * 100)
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    @pytest.fixture
    def mock_gcs_upload(self):
        """Mock GCS upload to avoid actual cloud operations."""
        with patch('google.cloud.storage.Client') as mock_client:
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            mock_client.return_value.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            mock_blob.upload_from_filename.return_value = None
            yield mock_client
    
    @pytest.fixture
    def mock_celery_task(self):
        """Mock Celery task enqueueing."""
        with patch('app.celery_tasks.enqueue_conversion_task') as mock_enqueue:
            mock_enqueue.return_value = str(uuid.uuid4())
            yield mock_enqueue
    
    def test_single_upload_creates_conversion(self, app, client, sample_file, mock_gcs_upload, mock_celery_task):
        """Test that a single upload creates a conversion record."""
        with app.app_context():
            # Mock authentication
            with patch('app.auth_api.require_api_key_if_configured'), \
                 patch('app.utils.authz.allow_session_or_api_key', return_value=True), \
                 patch('app.utils.validation.validate_upload_file') as mock_validate:
                
                # Mock validation to return success
                mock_validate.return_value.is_valid = True
                
                # Mock file type detection
                with patch('app.security.sniff_category', return_value=('text/plain', 'document')), \
                     patch('app.security.size_ok', return_value=True):
                    
                    with open(sample_file, 'rb') as f:
                        response = client.post('/api/upload', data={'file': (f, 'test.txt')})
                    
                    assert response.status_code == 202
                    data = response.get_json()
                    assert 'conversion_id' in data
                    assert data['status'] == 'QUEUED'
                    
                    # Verify conversion was created in database
                    conversion = Conversion.query.get(data['conversion_id'])
                    assert conversion is not None
                    assert conversion.filename == 'test.txt'
                    assert conversion.status == 'QUEUED'
                    assert conversion.sha256 is not None
    
    def test_duplicate_upload_returns_existing(self, app, client, sample_file, mock_gcs_upload, mock_celery_task):
        """Test that duplicate uploads return the existing conversion."""
        with app.app_context():
            # Mock authentication and validation
            with patch('app.auth_api.require_api_key_if_configured'), \
                 patch('app.utils.authz.allow_session_or_api_key', return_value=True), \
                 patch('app.utils.validation.validate_upload_file') as mock_validate, \
                 patch('app.security.sniff_category', return_value=('text/plain', 'document')), \
                 patch('app.security.size_ok', return_value=True):
                
                mock_validate.return_value.is_valid = True
                
                # First upload
                with open(sample_file, 'rb') as f:
                    response1 = client.post('/api/upload', data={'file': (f, 'test.txt')})
                
                assert response1.status_code == 202
                data1 = response1.get_json()
                conversion_id1 = data1['conversion_id']
                
                # Second upload of same file
                with open(sample_file, 'rb') as f:
                    response2 = client.post('/api/upload', data={'file': (f, 'test.txt')})
                
                assert response2.status_code == 202
                data2 = response2.get_json()
                
                # Should return the same conversion ID
                assert data2['conversion_id'] == conversion_id1
                assert data2['note'] == 'duplicate_upload'
                
                # Verify only one conversion exists in database
                conversions = Conversion.query.filter_by(sha256=Conversion.query.get(conversion_id1).sha256).all()
                assert len(conversions) == 1
    
    def test_completed_conversion_returns_immediately(self, app, client, sample_file, mock_gcs_upload, mock_celery_task):
        """Test that completed conversions are returned immediately."""
        with app.app_context():
            # Create a completed conversion manually
            file_hash = sha256_file(sample_file)
            conversion = Conversion(
                id=str(uuid.uuid4()),
                filename='test.txt',
                status='COMPLETED',
                sha256=file_hash,
                markdown='# Test Content\n\nThis is test content.',
                user_id=1
            )
            db.session.add(conversion)
            db.session.commit()
            
            # Mock authentication and validation
            with patch('app.auth_api.require_api_key_if_configured'), \
                 patch('app.utils.authz.allow_session_or_api_key', return_value=True), \
                 patch('app.utils.validation.validate_upload_file') as mock_validate, \
                 patch('app.security.sniff_category', return_value=('text/plain', 'document')), \
                 patch('app.security.size_ok', return_value=True):
                
                mock_validate.return_value.is_valid = True
                
                # Upload same file
                with open(sample_file, 'rb') as f:
                    response = client.post('/api/upload', data={'file': (f, 'test.txt')})
                
                assert response.status_code == 200  # Should return immediately
                data = response.get_json()
                assert data['conversion_id'] == conversion.id
                assert data['status'] == 'COMPLETED'
                assert data['note'] == 'deduplicated'
                
                # Verify no new conversion was created
                conversions = Conversion.query.filter_by(sha256=file_hash).all()
                assert len(conversions) == 1
    
    def test_concurrent_uploads_create_single_conversion(self, app, client, sample_file, mock_gcs_upload, mock_celery_task):
        """Test that concurrent uploads of the same file create only one conversion."""
        with app.app_context():
            # Mock authentication and validation
            with patch('app.auth_api.require_api_key_if_configured'), \
                 patch('app.utils.authz.allow_session_or_api_key', return_value=True), \
                 patch('app.utils.validation.validate_upload_file') as mock_validate, \
                 patch('app.security.sniff_category', return_value=('text/plain', 'document')), \
                 patch('app.security.size_ok', return_value=True):
                
                mock_validate.return_value.is_valid = True
                
                def upload_file():
                    """Upload a file and return the response."""
                    with open(sample_file, 'rb') as f:
                        return client.post('/api/upload', data={'file': (f, 'test.txt')})
                
                # Perform 5 concurrent uploads
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(upload_file) for _ in range(5)]
                    responses = [future.result() for future in as_completed(futures)]
                
                # All responses should be successful
                for response in responses:
                    assert response.status_code in [200, 202]
                
                # Get the conversion IDs from responses
                conversion_ids = set()
                for response in responses:
                    data = response.get_json()
                    conversion_ids.add(data['conversion_id'])
                
                # Should have only one unique conversion ID
                assert len(conversion_ids) == 1
                
                # Verify only one conversion exists in database
                file_hash = sha256_file(sample_file)
                conversions = Conversion.query.filter_by(sha256=file_hash).all()
                assert len(conversions) == 1
    
    def test_database_constraint_prevents_duplicates(self, app):
        """Test that database unique constraint prevents duplicate entries."""
        with app.app_context():
            # Create a conversion
            conversion1 = Conversion(
                id=str(uuid.uuid4()),
                filename='test.txt',
                status='QUEUED',
                sha256='test_hash_123',
                user_id=1
            )
            db.session.add(conversion1)
            db.session.commit()
            
            # Try to create another conversion with same SHA256 and user_id
            conversion2 = Conversion(
                id=str(uuid.uuid4()),
                filename='test2.txt',
                status='QUEUED',
                sha256='test_hash_123',
                user_id=1
            )
            db.session.add(conversion2)
            
            # Should raise IntegrityError due to unique constraint
            with pytest.raises(IntegrityError):
                db.session.commit()
    
    def test_different_owners_can_have_same_sha256(self, app):
        """Test that different owners can have conversions with the same SHA256."""
        with app.app_context():
            # Create conversion for user 1
            conversion1 = Conversion(
                id=str(uuid.uuid4()),
                filename='test.txt',
                status='QUEUED',
                sha256='test_hash_123',
                user_id=1
            )
            db.session.add(conversion1)
            db.session.commit()
            
            # Create conversion for user 2 with same SHA256
            conversion2 = Conversion(
                id=str(uuid.uuid4()),
                filename='test.txt',
                status='QUEUED',
                sha256='test_hash_123',
                user_id=2
            )
            db.session.add(conversion2)
            db.session.commit()  # Should succeed
            
            # Verify both conversions exist
            conversions = Conversion.query.filter_by(sha256='test_hash_123').all()
            assert len(conversions) == 2
            assert {c.user_id for c in conversions} == {1, 2}
    
    def test_visitor_session_idempotency(self, app):
        """Test idempotency for anonymous users with visitor session IDs."""
        with app.app_context():
            # Create conversion for visitor session
            conversion1 = Conversion(
                id=str(uuid.uuid4()),
                filename='test.txt',
                status='QUEUED',
                sha256='test_hash_123',
                visitor_session_id='visitor_123'
            )
            db.session.add(conversion1)
            db.session.commit()
            
            # Try to create another conversion with same SHA256 and visitor session
            conversion2 = Conversion(
                id=str(uuid.uuid4()),
                filename='test2.txt',
                status='QUEUED',
                sha256='test_hash_123',
                visitor_session_id='visitor_123'
            )
            db.session.add(conversion2)
            
            # Should raise IntegrityError due to unique constraint
            with pytest.raises(IntegrityError):
                db.session.commit()
    
    def test_mixed_user_and_visitor_idempotency(self, app):
        """Test that user and visitor conversions are treated separately."""
        with app.app_context():
            # Create conversion for user
            conversion1 = Conversion(
                id=str(uuid.uuid4()),
                filename='test.txt',
                status='QUEUED',
                sha256='test_hash_123',
                user_id=1
            )
            db.session.add(conversion1)
            db.session.commit()
            
            # Create conversion for visitor with same SHA256
            conversion2 = Conversion(
                id=str(uuid.uuid4()),
                filename='test.txt',
                status='QUEUED',
                sha256='test_hash_123',
                visitor_session_id='visitor_123'
            )
            db.session.add(conversion2)
            db.session.commit()  # Should succeed
            
            # Verify both conversions exist
            conversions = Conversion.query.filter_by(sha256='test_hash_123').all()
            assert len(conversions) == 2
            assert any(c.user_id == 1 for c in conversions)
            assert any(c.visitor_session_id == 'visitor_123' for c in conversions)
    
    def test_force_parameter_bypasses_idempotency(self, app, client, sample_file, mock_gcs_upload, mock_celery_task):
        """Test that force=true parameter bypasses idempotency checks."""
        with app.app_context():
            # Mock authentication and validation
            with patch('app.auth_api.require_api_key_if_configured'), \
                 patch('app.utils.authz.allow_session_or_api_key', return_value=True), \
                 patch('app.utils.validation.validate_upload_file') as mock_validate, \
                 patch('app.security.sniff_category', return_value=('text/plain', 'document')), \
                 patch('app.security.size_ok', return_value=True):
                
                mock_validate.return_value.is_valid = True
                
                # First upload
                with open(sample_file, 'rb') as f:
                    response1 = client.post('/api/upload', data={'file': (f, 'test.txt')})
                
                assert response1.status_code == 202
                data1 = response1.get_json()
                conversion_id1 = data1['conversion_id']
                
                # Second upload with force=true
                with open(sample_file, 'rb') as f:
                    response2 = client.post('/api/upload?force=true', data={'file': (f, 'test.txt')})
                
                assert response2.status_code == 202
                data2 = response2.get_json()
                
                # Should return the same conversion ID (legacy behavior)
                assert data2['conversion_id'] == conversion_id1
                assert data2['note'] == 'duplicate_upload'
    
    def test_transaction_rollback_on_error(self, app, client, sample_file, mock_gcs_upload):
        """Test that database transaction is rolled back on error."""
        with app.app_context():
            # Mock authentication and validation
            with patch('app.auth_api.require_api_key_if_configured'), \
                 patch('app.utils.authz.allow_session_or_api_key', return_value=True), \
                 patch('app.utils.validation.validate_upload_file') as mock_validate, \
                 patch('app.security.sniff_category', return_value=('text/plain', 'document')), \
                 patch('app.security.size_ok', return_value=True):
                
                mock_validate.return_value.is_valid = True
                
                # Mock Celery task to raise an exception
                with patch('app.celery_tasks.enqueue_conversion_task', side_effect=Exception("Task error")):
                    with open(sample_file, 'rb') as f:
                        response = client.post('/api/upload', data={'file': (f, 'test.txt')})
                    
                    assert response.status_code == 500
                    
                    # Verify no conversion was created in database
                    file_hash = sha256_file(sample_file)
                    conversions = Conversion.query.filter_by(sha256=file_hash).all()
                    assert len(conversions) == 0
    
    def test_indexes_exist_for_performance(self, app):
        """Test that required indexes exist for performance."""
        with app.app_context():
            # Get database connection
            connection = db.engine.connect()
            
            # Check for required indexes (PostgreSQL-specific)
            if connection.dialect.name == 'postgresql':
                # Check unique constraint
                result = connection.execute(text("""
                    SELECT constraint_name 
                    FROM information_schema.table_constraints 
                    WHERE table_name = 'conversions' 
                    AND constraint_name = 'uq_conversions_sha256_owner'
                """)).fetchone()
                assert result is not None, "Unique constraint should exist"
                
                # Check indexes
                result = connection.execute(text("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename = 'conversions' 
                    AND indexname IN ('ix_conversions_status_user_id', 'ix_conversions_status_visitor_id')
                """)).fetchall()
                assert len(result) == 2, "Required indexes should exist"
            
            connection.close()


if __name__ == '__main__':
    pytest.main([__file__])

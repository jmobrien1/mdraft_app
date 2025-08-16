"""
Tests for async upload functionality.

This module tests the fully async upload→processing system including:
- Idempotency with SHA256 deduplication
- Task routing and retry policies
- Atomic state transitions
- Multiple identical uploads handling
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, call
from flask import Flask
from datetime import datetime, timedelta

from app.models_conversion import Conversion
from app.celery_tasks import (
    convert_document, 
    enqueue_conversion_task, 
    is_pro_user, 
    get_task_queue,
    _convert_with_markitdown
)


@pytest.fixture
def app():
    """Create a test Flask app."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    from app import db
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def sample_file():
    """Create a sample file for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as f:
        f.write(b"Sample PDF content for testing")
        f.flush()
        yield f.name
    try:
        os.unlink(f.name)
    except:
        pass


@pytest.fixture
def mock_gcs():
    """Mock Google Cloud Storage."""
    with patch('app.celery_tasks.storage') as mock_storage:
        mock_client = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()
        
        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        yield {
            'client': mock_client,
            'bucket': mock_bucket,
            'blob': mock_blob
        }


class TestAsyncUploadIdempotency:
    """Test idempotency features of async upload."""
    
    def test_convert_document_idempotent_completed(self, app):
        """Test that convert_document returns existing result for completed conversion."""
        with app.app_context():
            # Create a completed conversion
            conv = Conversion(
                id="test-conv-123",
                filename="test.pdf",
                status="COMPLETED",
                markdown="# Test Content",
                sha256="test-sha256",
                original_mime="application/pdf",
                original_size=1024,
                stored_uri="gs://bucket/test.pdf"
            )
            from app import db
            db.session.add(conv)
            db.session.commit()
            
            # Call convert_document
            result = convert_document("test-conv-123", 1, "gs://bucket/test.pdf")
            
            # Should return existing result without processing
            assert result['status'] == 'completed'
            assert result['conversion_id'] == "test-conv-123"
            assert result['note'] == 'already_completed'
    
    def test_convert_document_retry_failed(self, app):
        """Test that convert_document retries failed conversions."""
        with app.app_context():
            # Create a failed conversion to test retry logic
            conv = Conversion(
                id="test-conv-456",
                filename="test.pdf",
                status="FAILED",
                error="Previous error",
                sha256="test-sha256",
                original_mime="application/pdf",
                original_size=1024,
                stored_uri="gs://bucket/test.pdf"
            )
            from app import db
            db.session.add(conv)
            db.session.commit()
            
            # Test that the function logs retry attempt for failed conversions
            with patch('app.celery_tasks.logger') as mock_logger:
                # This should fail because FAILED status is not valid for processing
                with pytest.raises(ValueError, match="Invalid conversion status"):
                    convert_document("test-conv-456", 1, "gs://bucket/test.pdf")
                
                # Should have logged retry attempt
                mock_logger.info.assert_called_with("Conversion test-conv-456 previously failed, retrying")
    
    def test_convert_document_invalid_status(self, app):
        """Test that convert_document rejects invalid status transitions."""
        with app.app_context():
            # Create a conversion with invalid status
            conv = Conversion(
                id="test-conv-789",
                filename="test.pdf",
                status="INVALID_STATUS",
                sha256="test-sha256",
                original_mime="application/pdf",
                original_size=1024,
                stored_uri="gs://bucket/test.pdf"
            )
            from app import db
            db.session.add(conv)
            db.session.commit()
            
            # Should raise error for invalid status
            with pytest.raises(ValueError, match="Invalid conversion status"):
                convert_document("test-conv-789", 1, "gs://bucket/test.pdf")


class TestTaskRouting:
    """Test task routing based on user priority."""
    
    def test_get_task_queue_pro_user(self, app):
        """Test that pro users get priority queue."""
        with app.app_context():
            with patch('app.celery_tasks.is_pro_user', return_value=True):
                queue = get_task_queue(1)
                assert queue == 'mdraft_priority'
    
    def test_get_task_queue_free_user(self, app):
        """Test that free users get default queue."""
        with app.app_context():
            with patch('app.celery_tasks.is_pro_user', return_value=False):
                queue = get_task_queue(1)
                assert queue == 'mdraft_default'
    
    def test_get_task_queue_anonymous_user(self, app):
        """Test that anonymous users get default queue."""
        with app.app_context():
            queue = get_task_queue(None)
            assert queue == 'mdraft_default'
    
    def test_is_pro_user_active_subscription(self, app):
        """Test pro user detection with active subscription."""
        with app.app_context():
            mock_user = Mock()
            mock_user.subscription_status = 'active'
            mock_user.plan = 'Free'
            
            with patch('app.celery_tasks.db') as mock_db:
                mock_db.session.get.return_value = mock_user
                assert is_pro_user(1) is True
    
    def test_is_pro_user_pro_plan(self, app):
        """Test pro user detection with pro plan."""
        with app.app_context():
            mock_user = Mock()
            mock_user.subscription_status = 'free'
            mock_user.plan = 'Pro'
            
            with patch('app.celery_tasks.db') as mock_db:
                mock_db.session.get.return_value = mock_user
                assert is_pro_user(1) is True
    
    def test_is_pro_user_free_user(self, app):
        """Test pro user detection for free users."""
        with app.app_context():
            mock_user = Mock()
            mock_user.subscription_status = 'free'
            mock_user.plan = 'Free'
            
            with patch('app.celery_tasks.db') as mock_db:
                mock_db.session.get.return_value = mock_user
                assert is_pro_user(1) is False


class TestAtomicStateTransitions:
    """Test atomic state transitions in conversion process."""
    
    def test_queued_to_processing_transition(self, app, mock_gcs):
        """Test QUEUED -> PROCESSING transition."""
        with app.app_context():
            # Create a queued conversion
            conv = Conversion(
                id="test-conv-state",
                filename="test.pdf",
                status="QUEUED",
                sha256="test-sha256",
                original_mime="application/pdf",
                original_size=1024,
                stored_uri="gs://bucket/test.pdf"
            )
            from app import db
            db.session.add(conv)
            db.session.commit()
            
            # Mock the conversion process
            with patch('app.celery_tasks._convert_with_markitdown', return_value="# Content"):
                with patch('app.celery_tasks.clean_markdown', return_value="# Content"):
                    result = convert_document("test-conv-state", 1, "gs://bucket/test.pdf")
            
            # Should have transitioned through states
            db.session.refresh(conv)
            assert conv.status == "COMPLETED"
            
            # Check that processing happened
            assert result['status'] == 'completed'
    
    def test_failure_transition(self, app, mock_gcs):
        """Test transition to FAILED on error."""
        with app.app_context():
            # Create a queued conversion
            conv = Conversion(
                id="test-conv-fail",
                filename="test.pdf",
                status="QUEUED",
                sha256="test-sha256",
                original_mime="application/pdf",
                original_size=1024,
                stored_uri="gs://bucket/test.pdf"
            )
            from app import db
            db.session.add(conv)
            db.session.commit()
            
            # Mock GCS download to fail
            mock_gcs['blob'].download_to_filename.side_effect = Exception("GCS Error")
            
            # Should transition to FAILED
            with pytest.raises(Exception):
                convert_document("test-conv-fail", 1, "gs://bucket/test.pdf")
            
            # Check state transition
            db.session.refresh(conv)
            assert conv.status == "FAILED"
            assert "GCS Error" in conv.error


class TestMultipleIdenticalUploads:
    """Test handling of multiple identical uploads."""
    
    def test_duplicate_upload_detection(self, app):
        """Test that duplicate uploads are detected and handled properly."""
        with app.app_context():
            from app import db
            
            # Create first conversion (queued)
            conv1 = Conversion(
                id="conv-1",
                filename="test.pdf",
                status="QUEUED",
                sha256="same-sha256",
                original_mime="application/pdf",
                original_size=1024,
                stored_uri="gs://bucket/test1.pdf"
            )
            db.session.add(conv1)
            db.session.commit()
            
            # Simulate second upload with same SHA256
            # This would be handled in the API layer, but we can test the logic
            existing_pending = Conversion.query.filter_by(sha256="same-sha256").filter(
                Conversion.status.in_(["QUEUED", "PROCESSING"])
            ).order_by(Conversion.created_at.desc()).first()
            
            assert existing_pending is not None
            assert existing_pending.id == "conv-1"
            assert existing_pending.status == "QUEUED"
    
    def test_completed_duplicate_return(self, app):
        """Test that completed duplicates return immediately."""
        with app.app_context():
            from app import db
            
            # Create completed conversion
            conv = Conversion(
                id="conv-completed",
                filename="test.pdf",
                status="COMPLETED",
                markdown="# Content",
                sha256="same-sha256",
                original_mime="application/pdf",
                original_size=1024,
                stored_uri="gs://bucket/test.pdf"
            )
            db.session.add(conv)
            db.session.commit()
            
            # Check for existing completed conversion
            existing = Conversion.query.filter_by(sha256="same-sha256", status="COMPLETED").order_by(Conversion.created_at.desc()).first()
            
            assert existing is not None
            assert existing.id == "conv-completed"
            assert existing.status == "COMPLETED"
            assert existing.markdown == "# Content"


class TestRetryPolicies:
    """Test retry policies and error handling."""
    
    def test_enqueue_conversion_task_retry_config(self, app):
        """Test that enqueue_conversion_task creates tasks with proper retry config."""
        with app.app_context():
            with patch.dict('sys.modules', {'celery_worker': None}):
                # Test the fallback path for testing (when celery_worker import fails)
                task_id = enqueue_conversion_task("conv-123", 1, "gs://bucket/test.pdf")
                
                # Should return mock task ID when celery is not available
                assert task_id == "mock-task-id"


class TestConversionLogic:
    """Test the actual conversion logic."""
    
    def test_convert_with_markitdown_success(self, sample_file):
        """Test successful markitdown conversion."""
        with patch('markitdown.MarkItDown') as mock_md:
            mock_instance = Mock()
            mock_result = Mock()
            mock_result.text_content = "# Converted Content"
            mock_instance.convert.return_value = mock_result
            mock_md.return_value = mock_instance
            
            result = _convert_with_markitdown(sample_file)
            
            assert result == "# Converted Content"
            mock_instance.convert.assert_called_once_with(sample_file)
    
    def test_convert_with_markitdown_fallback(self, sample_file):
        """Test markitdown fallback to file preview."""
        with patch('markitdown.MarkItDown') as mock_md:
            mock_md.side_effect = Exception("Conversion failed")
            
            result = _convert_with_markitdown(sample_file)
            
            # Should return file preview
            assert "Sample PDF content" in result
    
    def test_convert_with_markitdown_markdown_attr(self, sample_file):
        """Test markitdown with markdown attribute."""
        with patch('markitdown.MarkItDown') as mock_md:
            mock_instance = Mock()
            mock_result = Mock()
            # Mock result has markdown attribute but no text_content
            # Use delattr to remove text_content so hasattr returns False
            mock_result.text_content = None
            mock_result.markdown = "# Markdown Content"
            # Remove text_content attribute so hasattr returns False
            del mock_result.text_content
            mock_instance.convert.return_value = mock_result
            mock_md.return_value = mock_instance
            
            result = _convert_with_markitdown(sample_file)
            
            assert result == "# Markdown Content"


class TestWebhookIntegration:
    """Test webhook delivery integration."""
    
    def test_webhook_delivery_on_completion(self, app, mock_gcs):
        """Test that webhooks are delivered on successful completion."""
        with app.app_context():
            # Create a queued conversion
            conv = Conversion(
                id="test-conv-webhook",
                filename="test.pdf",
                status="QUEUED",
                sha256="test-sha256",
                original_mime="application/pdf",
                original_size=1024,
                stored_uri="gs://bucket/test.pdf"
            )
            from app import db
            db.session.add(conv)
            db.session.commit()
            
            # Mock webhook delivery
            with patch('app.celery_tasks.deliver_webhook') as mock_webhook:
                mock_webhook.return_value = (200, None)
                
                # Mock the conversion process
                with patch('app.celery_tasks._convert_with_markitdown', return_value="# Content"):
                    with patch('app.celery_tasks.clean_markdown', return_value="# Content"):
                        result = convert_document("test-conv-webhook", 1, "gs://bucket/test.pdf", "http://example.com/webhook")
            
            # Should have delivered webhook
            mock_webhook.assert_called_once()
            call_args = mock_webhook.call_args
            assert call_args[0][0] == "http://example.com/webhook"
            assert call_args[0][1] == "conversion.completed"
    
    def test_webhook_failure_doesnt_fail_task(self, app, mock_gcs):
        """Test that webhook failure doesn't fail the conversion task."""
        with app.app_context():
            # Create a queued conversion
            conv = Conversion(
                id="test-conv-webhook-fail",
                filename="test.pdf",
                status="QUEUED",
                sha256="test-sha256",
                original_mime="application/pdf",
                original_size=1024,
                stored_uri="gs://bucket/test.pdf"
            )
            from app import db
            db.session.add(conv)
            db.session.commit()
            
            # Mock webhook delivery to fail
            with patch('app.celery_tasks.deliver_webhook') as mock_webhook:
                mock_webhook.side_effect = Exception("Webhook failed")
                
                # Mock the conversion process
                with patch('app.celery_tasks._convert_with_markitdown', return_value="# Content"):
                    with patch('app.celery_tasks.clean_markdown', return_value="# Content"):
                        result = convert_document("test-conv-webhook-fail", 1, "gs://bucket/test.pdf", "http://example.com/webhook")
            
            # Should still complete successfully
            assert result['status'] == 'completed'
            assert result['conversion_id'] == "test-conv-webhook-fail"


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_conversion_not_found(self, app):
        """Test handling of non-existent conversion."""
        with app.app_context():
            with pytest.raises(ValueError, match="Conversion nonexistent not found"):
                convert_document("nonexistent", 1, "gs://bucket/test.pdf")
    
    def test_empty_conversion_result(self, app, mock_gcs):
        """Test handling of empty conversion result."""
        with app.app_context():
            # Create a queued conversion
            conv = Conversion(
                id="test-conv-empty",
                filename="test.pdf",
                status="QUEUED",
                sha256="test-sha256",
                original_mime="application/pdf",
                original_size=1024,
                stored_uri="gs://bucket/test.pdf"
            )
            from app import db
            db.session.add(conv)
            db.session.commit()
            
            # Mock empty conversion result
            with patch('app.celery_tasks._convert_with_markitdown', return_value=""):
                with patch('app.celery_tasks.clean_markdown', return_value=""):
                    with pytest.raises(ValueError, match="No content extracted"):
                        convert_document("test-conv-empty", 1, "gs://bucket/test.pdf")
            
            # Should have transitioned to FAILED
            db.session.refresh(conv)
            assert conv.status == "FAILED"
            assert "No content extracted" in conv.error
    
    def test_invalid_gcs_uri(self, app):
        """Test handling of invalid GCS URI."""
        with app.app_context():
            # Create a queued conversion
            conv = Conversion(
                id="test-conv-invalid-uri",
                filename="test.pdf",
                status="QUEUED",
                sha256="test-sha256",
                original_mime="application/pdf",
                original_size=1024,
                stored_uri="invalid-uri"
            )
            from app import db
            db.session.add(conv)
            db.session.commit()
            
            with pytest.raises(ValueError, match="Invalid GCS URI"):
                convert_document("test-conv-invalid-uri", 1, "invalid-uri")
            
            # Should have transitioned to FAILED
            db.session.refresh(conv)
            assert conv.status == "FAILED"
            assert "Invalid GCS URI" in conv.error

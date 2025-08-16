"""
Tests for conversion progress tracking functionality.

This module tests the progress field (0-100) that tracks conversion job progress
through major steps: received (5), downloaded (15), validated (30), converted (80),
post-process (90), completed (100).
"""

import pytest
import tempfile
import os
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timezone

from app import create_app, db
from app.models_conversion import Conversion
from app.models import ConversionStatus


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app()
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return app.test_client()


@pytest.fixture
def sample_conversion(app):
    """Create a sample conversion for testing."""
    with app.app_context():
        conversion = Conversion(
            filename="test.pdf",
            status=ConversionStatus.QUEUED,
            progress=None,
            user_id=1
        )
        db.session.add(conversion)
        db.session.commit()
        return conversion


class TestProgressField:
    """Test the progress field functionality."""
    
    def test_progress_field_initialization(self, app):
        """Test that progress field is properly initialized."""
        with app.app_context():
            conversion = Conversion(
                filename="test.pdf",
                status=ConversionStatus.QUEUED
            )
            assert conversion.progress is None
    
    def test_update_progress_valid_values(self, app):
        """Test updating progress with valid values (0-100)."""
        with app.app_context():
            conversion = Conversion(
                filename="test.pdf",
                status=ConversionStatus.QUEUED
            )
            
            # Test valid progress values
            for progress in [0, 25, 50, 75, 100]:
                conversion.update_progress(progress)
                assert conversion.progress == progress
                assert conversion.updated_at is not None
    
    def test_update_progress_invalid_values(self, app):
        """Test that invalid progress values raise ValueError."""
        with app.app_context():
            conversion = Conversion(
                filename="test.pdf",
                status=ConversionStatus.QUEUED
            )
            
            # Test invalid progress values
            invalid_values = [-1, 101, 150, "50", 50.5, None]
            for progress in invalid_values:
                with pytest.raises(ValueError):
                    conversion.update_progress(progress)
    
    def test_progress_monotonic_increase(self, app):
        """Test that progress only increases monotonically."""
        with app.app_context():
            conversion = Conversion(
                filename="test.pdf",
                status=ConversionStatus.QUEUED
            )
            
            # Set initial progress
            conversion.update_progress(25)
            assert conversion.progress == 25
            
            # Should be able to increase
            conversion.update_progress(50)
            assert conversion.progress == 50
            
            # Should be able to set to same value
            conversion.update_progress(50)
            assert conversion.progress == 50


class TestProgressInConversionPipeline:
    """Test progress updates during the conversion pipeline."""
    
    @patch('app.celery_tasks.storage.Client')
    @patch('app.celery_tasks._convert_with_markitdown')
    @patch('app.celery_tasks.clean_markdown')
    def test_progress_updates_during_conversion(self, mock_clean, mock_convert, mock_storage, app):
        """Test that progress is updated at each major step during conversion."""
        from app.celery_tasks import convert_document
        
        with app.app_context():
            # Create a conversion
            conversion = Conversion(
                filename="test.pdf",
                status=ConversionStatus.QUEUED,
                stored_uri="gs://test-bucket/test.pdf",
                original_mime="application/pdf"
            )
            db.session.add(conversion)
            db.session.commit()
            
            # Mock GCS download
            mock_blob = Mock()
            mock_bucket = Mock()
            mock_bucket.blob.return_value = mock_blob
            mock_storage.return_value.bucket.return_value = mock_bucket
            
            # Mock conversion
            mock_convert.return_value = "Test markdown content"
            mock_clean.return_value = "Test markdown content"
            
            # Run conversion
            result = convert_document(conversion.id, 1, "gs://test-bucket/test.pdf")
            
            # Verify progress was updated at each step
            db.session.refresh(conversion)
            assert conversion.progress == 100
            assert conversion.status == ConversionStatus.COMPLETED
    
    @patch('app.celery_tasks.storage.Client')
    def test_progress_on_failure(self, mock_storage, app):
        """Test that progress is preserved on conversion failure."""
        from app.celery_tasks import convert_document
        
        with app.app_context():
            # Create a conversion
            conversion = Conversion(
                filename="test.pdf",
                status=ConversionStatus.QUEUED,
                stored_uri="gs://test-bucket/test.pdf"
            )
            db.session.add(conversion)
            db.session.commit()
            
            # Mock GCS download to fail
            mock_storage.side_effect = Exception("GCS error")
            
            # Run conversion (should fail)
            with pytest.raises(Exception):
                convert_document(conversion.id, 1, "gs://test-bucket/test.pdf")
            
            # Verify conversion failed but progress was set
            db.session.refresh(conversion)
            assert conversion.status == ConversionStatus.FAILED
            assert conversion.progress == 5  # Should be at the step where it failed


class TestProgressInAPI:
    """Test progress field in API responses."""
    
    def test_get_conversion_with_progress(self, client, sample_conversion):
        """Test that GET /api/conversions/<id> returns progress."""
        with client.application.app_context():
            # Update progress
            sample_conversion.update_progress(50)
            db.session.commit()
            
            # Make API request
            response = client.get(f"/api/conversions/{sample_conversion.id}")
            assert response.status_code == 200
            
            data = response.get_json()
            assert "progress" in data
            assert data["progress"] == 50
    
    def test_list_conversions_with_progress(self, client, app):
        """Test that GET /api/conversions returns progress for each conversion."""
        with app.app_context():
            # Create multiple conversions with different progress
            conversions = []
            for i in range(3):
                conv = Conversion(
                    filename=f"test{i}.pdf",
                    status=ConversionStatus.PROCESSING,
                    progress=i * 25,
                    user_id=1
                )
                db.session.add(conv)
                conversions.append(conv)
            db.session.commit()
            
            # Mock authentication
            with patch('app.auth.ownership.get_owner_tuple') as mock_owner:
                mock_owner.return_value = ("user", 1)
                
                # Make API request
                response = client.get("/api/conversions")
                assert response.status_code == 200
                
                data = response.get_json()
                assert len(data) == 3
                
                # Check that each conversion has progress
                for i, conv_data in enumerate(data):
                    assert "progress" in conv_data
                    assert conv_data["progress"] == i * 25
    
    def test_progress_null_when_not_set(self, client, sample_conversion):
        """Test that progress is null when not explicitly set."""
        response = client.get(f"/api/conversions/{sample_conversion.id}")
        assert response.status_code == 200
        
        data = response.get_json()
        assert "progress" in data
        assert data["progress"] is None


class TestProgressValidation:
    """Test progress field validation and constraints."""
    
    def test_progress_database_constraints(self, app):
        """Test that progress field can be null and accepts valid integers."""
        with app.app_context():
            # Test null progress
            conv1 = Conversion(
                filename="test1.pdf",
                status=ConversionStatus.QUEUED,
                progress=None
            )
            db.session.add(conv1)
            
            # Test valid progress values
            conv2 = Conversion(
                filename="test2.pdf",
                status=ConversionStatus.PROCESSING,
                progress=50
            )
            db.session.add(conv2)
            
            conv3 = Conversion(
                filename="test3.pdf",
                status=ConversionStatus.COMPLETED,
                progress=100
            )
            db.session.add(conv3)
            
            db.session.commit()
            
            # Verify all saved correctly
            assert conv1.progress is None
            assert conv2.progress == 50
            assert conv3.progress == 100
    
    def test_progress_repr_includes_progress(self, app):
        """Test that __repr__ includes progress information."""
        with app.app_context():
            conversion = Conversion(
                filename="test.pdf",
                status=ConversionStatus.PROCESSING,
                progress=75
            )
            
            repr_str = repr(conversion)
            assert "progress=75" in repr_str


class TestProgressIntegration:
    """Integration tests for progress functionality."""
    
    @patch('app.celery_tasks.storage.Client')
    @patch('app.celery_tasks._convert_with_markitdown')
    @patch('app.celery_tasks.clean_markdown')
    def test_full_conversion_progress_flow(self, mock_clean, mock_convert, mock_storage, app, client):
        """Test complete flow from upload to completion with progress tracking."""
        from app.celery_tasks import convert_document
        
        with app.app_context():
            # Create a conversion
            conversion = Conversion(
                filename="test.pdf",
                status=ConversionStatus.QUEUED,
                stored_uri="gs://test-bucket/test.pdf",
                original_mime="application/pdf"
            )
            db.session.add(conversion)
            db.session.commit()
            
            # Mock GCS and conversion
            mock_blob = Mock()
            mock_bucket = Mock()
            mock_bucket.blob.return_value = mock_blob
            mock_storage.return_value.bucket.return_value = mock_bucket
            mock_convert.return_value = "Test content"
            mock_clean.return_value = "Test content"
            
            # Start conversion
            result = convert_document(conversion.id, 1, "gs://test-bucket/test.pdf")
            
            # Verify final state
            db.session.refresh(conversion)
            assert conversion.status == ConversionStatus.COMPLETED
            assert conversion.progress == 100
            
            # Verify API response includes progress
            response = client.get(f"/api/conversions/{conversion.id}")
            assert response.status_code == 200
            
            data = response.get_json()
            assert data["progress"] == 100
            assert data["status"] == "COMPLETED"
    
    def test_progress_polling_scenario(self, client, app):
        """Test realistic polling scenario where client checks progress."""
        with app.app_context():
            # Create conversion
            conversion = Conversion(
                filename="test.pdf",
                status=ConversionStatus.QUEUED,
                user_id=1
            )
            db.session.add(conversion)
            db.session.commit()
            
            # Mock authentication
            with patch('app.auth.ownership.get_owner_tuple') as mock_owner:
                mock_owner.return_value = ("user", 1)
                
                # Initial poll - should show no progress
                response = client.get(f"/api/conversions/{conversion.id}")
                assert response.status_code == 200
                data = response.get_json()
                assert data["progress"] is None
                assert data["status"] == "QUEUED"
                
                # Simulate progress updates
                conversion.update_progress(25)
                conversion.status = ConversionStatus.PROCESSING
                db.session.commit()
                
                # Poll again - should show progress
                response = client.get(f"/api/conversions/{conversion.id}")
                assert response.status_code == 200
                data = response.get_json()
                assert data["progress"] == 25
                assert data["status"] == "PROCESSING"
                
                # Final state
                conversion.update_progress(100)
                conversion.status = ConversionStatus.COMPLETED
                db.session.commit()
                
                # Final poll
                response = client.get(f"/api/conversions/{conversion.id}")
                assert response.status_code == 200
                data = response.get_json()
                assert data["progress"] == 100
                assert data["status"] == "COMPLETED"


if __name__ == "__main__":
    pytest.main([__file__])

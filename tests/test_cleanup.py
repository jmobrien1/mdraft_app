"""
Tests for cleanup functionality.

This module tests the cleanup tasks including file cleanup,
job cleanup, and CLI commands with mocked dependencies.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from flask import Flask

from app.cleanup import (
    get_retention_days, should_delete_gcs, should_use_gcs,
    cleanup_old_files, cleanup_old_jobs, run_cleanup
)


@pytest.fixture
def app():
    """Create a test Flask app."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app


class TestCleanupConfig:
    """Test cleanup configuration functions."""
    
    def test_get_retention_days_default(self):
        """Test get_retention_days returns default value."""
        with patch('app.cleanup.os.getenv', return_value=None):
            result = get_retention_days()
            assert result == 30
    
    def test_get_retention_days_custom(self):
        """Test get_retention_days returns custom value."""
        with patch('app.cleanup.os.getenv', return_value='7'):
            result = get_retention_days()
            assert result == 7
    
    def test_should_delete_gcs_enabled(self):
        """Test should_delete_gcs returns True when enabled."""
        with patch('app.cleanup.os.getenv', return_value='1'):
            result = should_delete_gcs()
            assert result is True
    
    def test_should_delete_gcs_disabled(self):
        """Test should_delete_gcs returns False when disabled."""
        with patch('app.cleanup.os.getenv', return_value='0'):
            result = should_delete_gcs()
            assert result is False
    
    def test_should_use_gcs_enabled(self):
        """Test should_use_gcs returns True when enabled."""
        with patch('app.cleanup.os.getenv', return_value='1'):
            result = should_use_gcs()
            assert result is True
    
    def test_should_use_gcs_disabled(self):
        """Test should_use_gcs returns False when disabled."""
        with patch('app.cleanup.os.getenv', return_value='0'):
            result = should_use_gcs()
            assert result is False


class TestCleanupOldFiles:
    """Test file cleanup functionality."""
    
    def test_cleanup_old_files_skip_gcs_disabled(self, app):
        """Test cleanup skips when GCS is disabled."""
        with app.app_context():
            with patch('app.cleanup.should_use_gcs', return_value=False):
                result = cleanup_old_files()
                assert result['status'] == 'skipped'
                assert result['reason'] == 'USE_GCS=0'
                assert result['files_deleted'] == 0
    
    def test_cleanup_old_files_skip_deletion_disabled(self, app):
        """Test cleanup skips when deletion is disabled."""
        with app.app_context():
            with patch('app.cleanup.should_use_gcs', return_value=True), \
                 patch('app.cleanup.should_delete_gcs', return_value=False):
                result = cleanup_old_files()
                assert result['status'] == 'skipped'
                assert result['reason'] == 'CLEANUP_DELETE_GCS=0'
                assert result['files_deleted'] == 0
    
    def test_cleanup_old_files_success(self, app):
        """Test successful file cleanup."""
        with app.app_context():
            with patch('app.cleanup.should_use_gcs', return_value=True), \
                 patch('app.cleanup.should_delete_gcs', return_value=True), \
                 patch('app.cleanup.get_retention_days', return_value=30), \
                 patch('app.cleanup.Storage') as mock_storage_class, \
                 patch('app.cleanup.db') as mock_db:
                
                # Mock storage
                mock_storage = Mock()
                mock_storage.list_prefix.side_effect = [
                    ['outputs/123/result.md', 'outputs/456/result.md'],  # outputs
                    ['uploads/123/document.pdf', 'uploads/789/document.pdf']  # uploads
                ]
                mock_storage.delete.return_value = True
                mock_storage_class.return_value = mock_storage
                
                # Mock jobs
                mock_job_old = Mock()
                mock_job_old.completed_at = datetime.utcnow() - timedelta(days=35)
                mock_job_old.created_at = datetime.utcnow() - timedelta(days=35)
                
                mock_job_new = Mock()
                mock_job_new.completed_at = datetime.utcnow() - timedelta(days=10)
                mock_job_new.created_at = datetime.utcnow() - timedelta(days=10)
                
                mock_db.session.get.side_effect = [mock_job_old, mock_job_new, mock_job_old, mock_job_new]
                
                result = cleanup_old_files()
                
                assert result['status'] == 'completed'
                assert result['files_deleted'] == 2  # 2 old files deleted
                assert len(result['errors']) == 0
                assert result['retention_days'] == 30
    
    def test_cleanup_old_files_with_errors(self, app):
        """Test file cleanup with some errors."""
        with app.app_context():
            with patch('app.cleanup.should_use_gcs', return_value=True), \
                 patch('app.cleanup.should_delete_gcs', return_value=True), \
                 patch('app.cleanup.get_retention_days', return_value=30), \
                 patch('app.cleanup.Storage') as mock_storage_class, \
                 patch('app.cleanup.db') as mock_db:
                
                # Mock storage with some failures
                mock_storage = Mock()
                mock_storage.list_prefix.side_effect = [
                    ['outputs/123/result.md'],  # outputs
                    ['uploads/123/document.pdf']  # uploads
                ]
                mock_storage.delete.side_effect = [True, False]  # First succeeds, second fails
                mock_storage_class.return_value = mock_storage
                
                # Mock job
                mock_job = Mock()
                mock_job.completed_at = datetime.utcnow() - timedelta(days=35)
                mock_job.created_at = datetime.utcnow() - timedelta(days=35)
                mock_db.session.get.return_value = mock_job
                
                result = cleanup_old_files()
                
                assert result['status'] == 'completed'
                assert result['files_deleted'] == 1
                assert len(result['errors']) == 1
                assert 'Failed to delete upload' in result['errors'][0]
    
    def test_cleanup_old_files_invalid_paths(self, app):
        """Test cleanup handles invalid file paths gracefully."""
        with app.app_context():
            with patch('app.cleanup.should_use_gcs', return_value=True), \
                 patch('app.cleanup.should_delete_gcs', return_value=True), \
                 patch('app.cleanup.get_retention_days', return_value=30), \
                 patch('app.cleanup.Storage') as mock_storage_class, \
                 patch('app.cleanup.db') as mock_db:
                
                # Mock storage with invalid paths
                mock_storage = Mock()
                mock_storage.list_prefix.side_effect = [
                    ['invalid/path', 'outputs/123/result.md'],  # outputs
                    ['invalid/path']  # uploads (no valid paths)
                ]
                mock_storage.delete.return_value = True
                mock_storage_class.return_value = mock_storage
                
                # Mock job for valid path (123)
                mock_job = Mock()
                mock_job.completed_at = datetime.utcnow() - timedelta(days=35)
                mock_job.created_at = datetime.utcnow() - timedelta(days=35)
                mock_db.session.get.return_value = mock_job
                
                result = cleanup_old_files()
                
                assert result['status'] == 'completed'
                assert result['files_deleted'] == 1  # Only valid path processed
                assert len(result['errors']) == 0


class TestCleanupOldJobs:
    """Test job cleanup functionality."""
    
    def test_cleanup_old_jobs_success(self, app):
        """Test successful job cleanup."""
        with app.app_context():
            with patch('app.cleanup.get_retention_days', return_value=30), \
                 patch('app.cleanup.db') as mock_db:
                
                # Mock old jobs
                mock_job1 = Mock()
                mock_job1.status = 'completed'
                mock_job1.created_at = datetime.utcnow() - timedelta(days=35)
                
                mock_job2 = Mock()
                mock_job2.status = 'failed'
                mock_job2.created_at = datetime.utcnow() - timedelta(days=40)
                
                # Mock query
                mock_query = Mock()
                mock_query.filter.return_value = mock_query
                mock_query.all.return_value = [mock_job1, mock_job2]
                mock_db.session.query.return_value = mock_query
                
                result = cleanup_old_jobs()
                
                assert result['status'] == 'completed'
                assert result['jobs_deleted'] == 2
                assert result['retention_days'] == 30
                mock_db.session.commit.assert_called_once()
    
    def test_cleanup_old_jobs_no_jobs(self, app):
        """Test job cleanup when no old jobs exist."""
        with app.app_context():
            with patch('app.cleanup.get_retention_days', return_value=30), \
                 patch('app.cleanup.db') as mock_db:
                
                # Mock empty query
                mock_query = Mock()
                mock_query.filter.return_value = mock_query
                mock_query.all.return_value = []
                mock_db.session.query.return_value = mock_query
                
                result = cleanup_old_jobs()
                
                assert result['status'] == 'completed'
                assert result['jobs_deleted'] == 0
                mock_db.session.commit.assert_called_once()
    
    def test_cleanup_old_jobs_database_error(self, app):
        """Test job cleanup handles database errors."""
        with app.app_context():
            with patch('app.cleanup.get_retention_days', return_value=30), \
                 patch('app.cleanup.db') as mock_db:
                
                # Mock database error
                mock_db.session.query.side_effect = Exception("Database error")
                
                result = cleanup_old_jobs()
                
                assert result['status'] == 'failed'
                assert 'Database error' in result['error']
                mock_db.session.rollback.assert_called_once()


class TestRunCleanup:
    """Test complete cleanup process."""
    
    def test_run_cleanup_success(self, app):
        """Test successful complete cleanup."""
        with app.app_context():
            with patch('app.cleanup.cleanup_old_files') as mock_file_cleanup, \
                 patch('app.cleanup.cleanup_old_jobs') as mock_job_cleanup:
                
                mock_file_cleanup.return_value = {
                    'status': 'completed',
                    'files_deleted': 5,
                    'errors': []
                }
                
                mock_job_cleanup.return_value = {
                    'status': 'completed',
                    'jobs_deleted': 3
                }
                
                result = run_cleanup()
                
                assert 'file_cleanup' in result
                assert 'job_cleanup' in result
                assert 'timestamp' in result
                assert result['file_cleanup']['status'] == 'completed'
                assert result['job_cleanup']['status'] == 'completed'
                assert result['file_cleanup']['files_deleted'] == 5
                assert result['job_cleanup']['jobs_deleted'] == 3
    
    def test_run_cleanup_with_failures(self, app):
        """Test cleanup with some failures."""
        with app.app_context():
            with patch('app.cleanup.cleanup_old_files') as mock_file_cleanup, \
                 patch('app.cleanup.cleanup_old_jobs') as mock_job_cleanup:
                
                mock_file_cleanup.return_value = {
                    'status': 'failed',
                    'error': 'Storage error'
                }
                
                mock_job_cleanup.return_value = {
                    'status': 'completed',
                    'jobs_deleted': 2
                }
                
                result = run_cleanup()
                
                assert result['file_cleanup']['status'] == 'failed'
                assert result['job_cleanup']['status'] == 'completed'
                assert 'Storage error' in result['file_cleanup']['error']


class TestCleanupIntegration:
    """Test cleanup integration scenarios."""
    
    def test_cleanup_skips_when_gcs_disabled(self, app):
        """Test cleanup skips when GCS is disabled."""
        with app.app_context():
            with patch('app.cleanup.should_use_gcs', return_value=False):
                result = cleanup_old_files()
                assert result['status'] == 'skipped'
                assert result['reason'] == 'USE_GCS=0'
    
    def test_cleanup_respects_retention_days(self, app):
        """Test cleanup respects retention days configuration."""
        with app.app_context():
            with patch('app.cleanup.should_use_gcs', return_value=True), \
                 patch('app.cleanup.should_delete_gcs', return_value=True), \
                 patch('app.cleanup.get_retention_days', return_value=7), \
                 patch('app.cleanup.Storage') as mock_storage_class, \
                 patch('app.cleanup.db') as mock_db:
                
                # Mock storage
                mock_storage = Mock()
                mock_storage.list_prefix.return_value = ['outputs/123/result.md']
                mock_storage.delete.return_value = True
                mock_storage_class.return_value = mock_storage
                
                # Mock job that's 10 days old (should be deleted with 7-day retention)
                mock_job = Mock()
                mock_job.completed_at = datetime.utcnow() - timedelta(days=10)
                mock_db.session.get.return_value = mock_job
                
                result = cleanup_old_files()
                
                assert result['status'] == 'completed'
                assert result['files_deleted'] == 1
                assert result['retention_days'] == 7

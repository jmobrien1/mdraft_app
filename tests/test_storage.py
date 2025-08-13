"""
Tests for the Storage adapter.

This module tests the Storage class functionality for both local and GCS modes.
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

from app.services.storage import Storage


class TestStorageLocal:
    """Test Storage adapter in local mode."""
    
    def setup_method(self):
        """Set up test environment."""
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # Mock Flask app config
        self.mock_app = Mock()
        self.mock_app.config = {
            'USE_GCS': False,
            'GCS_BUCKET_NAME': None,
            'GOOGLE_CLOUD_PROJECT': None
        }
        
        # Patch current_app to return our mock
        self.app_patcher = patch('app.services.storage.current_app', self.mock_app)
        self.app_patcher.start()
        
        # Create storage instance
        self.storage = Storage()
        # Override data directory for testing
        self.storage._data_dir = self.data_dir
    
    def teardown_method(self):
        """Clean up test environment."""
        self.app_patcher.stop()
        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init_local_mode(self):
        """Test Storage initialization in local mode."""
        assert not self.storage.use_gcs
        assert self.storage._data_dir == self.data_dir
        assert self.storage._data_dir.exists()
    
    def test_write_bytes_local(self):
        """Test writing bytes to local storage."""
        test_data = b"Hello, World!"
        test_path = "test/file.txt"
        
        self.storage.write_bytes(test_path, test_data)
        
        # Check file was created
        expected_file = self.data_dir / test_path
        assert expected_file.exists()
        assert expected_file.read_bytes() == test_data
    
    def test_read_bytes_local(self):
        """Test reading bytes from local storage."""
        test_data = b"Hello, World!"
        test_path = "test/file.txt"
        
        # Create test file
        expected_file = self.data_dir / test_path
        expected_file.parent.mkdir(parents=True, exist_ok=True)
        expected_file.write_bytes(test_data)
        
        # Read and verify
        result = self.storage.read_bytes(test_path)
        assert result == test_data
    
    def test_read_bytes_local_not_found(self):
        """Test reading bytes from non-existent local file."""
        with pytest.raises(FileNotFoundError):
            self.storage.read_bytes("nonexistent/file.txt")
    
    def test_exists_local_true(self):
        """Test exists() returns True for existing local file."""
        test_path = "test/file.txt"
        expected_file = self.data_dir / test_path
        expected_file.parent.mkdir(parents=True, exist_ok=True)
        expected_file.write_text("test")
        
        assert self.storage.exists(test_path) is True
    
    def test_exists_local_false(self):
        """Test exists() returns False for non-existent local file."""
        assert self.storage.exists("nonexistent/file.txt") is False
    
    def test_list_prefix_local(self):
        """Test listing files with prefix in local storage."""
        # Create test files
        test_files = [
            "uploads/file1.txt",
            "uploads/file2.txt",
            "outputs/file3.txt",
            "uploads/subdir/file4.txt"
        ]
        
        for file_path in test_files:
            full_path = self.data_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text("test")
        
        # Test listing uploads prefix
        result = self.storage.list_prefix("uploads/")
        assert len(result) == 3
        assert "uploads/file1.txt" in result
        assert "uploads/file2.txt" in result
        assert "uploads/subdir/file4.txt" in result
        assert "outputs/file3.txt" not in result
    
    def test_list_prefix_local_empty(self):
        """Test listing files with non-existent prefix."""
        result = self.storage.list_prefix("nonexistent/")
        assert result == []
    
    def test_delete_local_true(self):
        """Test deleting existing local file."""
        test_path = "test/file.txt"
        expected_file = self.data_dir / test_path
        expected_file.parent.mkdir(parents=True, exist_ok=True)
        expected_file.write_text("test")
        
        assert self.storage.delete(test_path) is True
        assert not expected_file.exists()
    
    def test_delete_local_false(self):
        """Test deleting non-existent local file."""
        assert self.storage.delete("nonexistent/file.txt") is False


class TestStorageGCS:
    """Test Storage adapter in GCS mode."""
    
    def setup_method(self):
        """Set up test environment."""
        # Mock Flask app config
        self.mock_app = Mock()
        self.mock_app.config = {
            'USE_GCS': True,
            'GCS_BUCKET_NAME': 'test-bucket',
            'GOOGLE_CLOUD_PROJECT': 'test-project'
        }
        
        # Patch current_app to return our mock
        self.app_patcher = patch('app.services.storage.current_app', self.mock_app)
        self.app_patcher.start()
        
        # Mock GCS client and bucket
        self.mock_client = Mock()
        self.mock_bucket = Mock()
        self.mock_blob = Mock()
        
        # Set up mock bucket
        self.mock_bucket.exists.return_value = True
        self.mock_bucket.blob.return_value = self.mock_blob
        
        # Set up mock client
        self.mock_client.bucket.return_value = self.mock_bucket
        
        # Patch GCS client creation
        self.gcs_patcher = patch('google.cloud.storage.Client', return_value=self.mock_client)
        self.gcs_patcher.start()
        
        # Create storage instance
        self.storage = Storage()
    
    def teardown_method(self):
        """Clean up test environment."""
        self.app_patcher.stop()
        self.gcs_patcher.stop()
    
    def test_init_gcs_mode(self):
        """Test Storage initialization in GCS mode."""
        assert self.storage.use_gcs
        assert self.storage.gcs_bucket_name == 'test-bucket'
        assert self.storage.google_cloud_project == 'test-project'
        assert self.storage._gcs_client == self.mock_client
        assert self.storage._gcs_bucket == self.mock_bucket
    
    def test_write_bytes_gcs(self):
        """Test writing bytes to GCS."""
        test_data = b"Hello, World!"
        test_path = "test/file.txt"
        
        self.storage.write_bytes(test_path, test_data)
        
        # Verify GCS blob was called correctly
        self.mock_bucket.blob.assert_called_once_with(test_path)
        self.mock_blob.upload_from_string.assert_called_once_with(test_data)
    
    def test_read_bytes_gcs(self):
        """Test reading bytes from GCS."""
        test_data = b"Hello, World!"
        test_path = "test/file.txt"
        
        # Set up mock blob
        self.mock_blob.exists.return_value = True
        self.mock_blob.download_as_bytes.return_value = test_data
        
        result = self.storage.read_bytes(test_path)
        
        assert result == test_data
        self.mock_bucket.blob.assert_called_once_with(test_path)
        self.mock_blob.download_as_bytes.assert_called_once()
    
    def test_read_bytes_gcs_not_found(self):
        """Test reading bytes from non-existent GCS file."""
        test_path = "test/file.txt"
        
        # Set up mock blob to not exist
        self.mock_blob.exists.return_value = False
        
        with pytest.raises(FileNotFoundError):
            self.storage.read_bytes(test_path)
    
    def test_exists_gcs_true(self):
        """Test exists() returns True for existing GCS file."""
        test_path = "test/file.txt"
        self.mock_blob.exists.return_value = True
        
        result = self.storage.exists(test_path)
        
        assert result is True
        self.mock_bucket.blob.assert_called_once_with(test_path)
        self.mock_blob.exists.assert_called_once()
    
    def test_exists_gcs_false(self):
        """Test exists() returns False for non-existent GCS file."""
        test_path = "test/file.txt"
        self.mock_blob.exists.return_value = False
        
        result = self.storage.exists(test_path)
        
        assert result is False
    
    def test_list_prefix_gcs(self):
        """Test listing files with prefix in GCS."""
        test_path = "uploads/"
        
        # Create mock blobs
        mock_blob1 = Mock()
        mock_blob1.name = "uploads/file1.txt"
        mock_blob2 = Mock()
        mock_blob2.name = "uploads/file2.txt"
        
        self.mock_bucket.list_blobs.return_value = [mock_blob1, mock_blob2]
        
        result = self.storage.list_prefix(test_path)
        
        assert result == ["uploads/file1.txt", "uploads/file2.txt"]
        self.mock_bucket.list_blobs.assert_called_once_with(prefix=test_path)
    
    def test_delete_gcs_true(self):
        """Test deleting existing GCS file."""
        test_path = "test/file.txt"
        self.mock_blob.exists.return_value = True
        
        result = self.storage.delete(test_path)
        
        assert result is True
        self.mock_bucket.blob.assert_called_once_with(test_path)
        self.mock_blob.delete.assert_called_once()
    
    def test_delete_gcs_false(self):
        """Test deleting non-existent GCS file."""
        test_path = "test/file.txt"
        self.mock_blob.exists.return_value = False
        
        result = self.storage.delete(test_path)
        
        assert result is False
        self.mock_bucket.blob.assert_called_once_with(test_path)
        self.mock_blob.delete.assert_not_called()


class TestStorageErrorHandling:
    """Test Storage adapter error handling."""
    
    def setup_method(self):
        """Set up test environment."""
        # Mock Flask app config for local mode
        self.mock_app = Mock()
        self.mock_app.config = {
            'USE_GCS': False,
            'GCS_BUCKET_NAME': None,
            'GOOGLE_CLOUD_PROJECT': None
        }
        
        # Patch current_app
        self.app_patcher = patch('app.services.storage.current_app', self.mock_app)
        self.app_patcher.start()
        
        # Create storage instance
        self.storage = Storage()
    
    def teardown_method(self):
        """Clean up test environment."""
        self.app_patcher.stop()
    
    def test_write_bytes_error(self):
        """Test write_bytes() error handling."""
        # Mock file system error
        with patch('builtins.open', side_effect=OSError("Permission denied")):
            with pytest.raises(RuntimeError, match="Storage write failed"):
                self.storage.write_bytes("test/file.txt", b"test")
    
    def test_read_bytes_error(self):
        """Test read_bytes() error handling."""
        # Create a file first, then mock file system error on read
        test_file = self.storage._data_dir / "test/file.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"test")
        
        # Mock file system error
        with patch('builtins.open', side_effect=OSError("Permission denied")):
            with pytest.raises(RuntimeError, match="Storage read failed"):
                self.storage.read_bytes("test/file.txt")
    
    def test_exists_error(self):
        """Test exists() error handling."""
        # Mock pathlib error
        with patch('pathlib.Path.exists', side_effect=OSError("Permission denied")):
            result = self.storage.exists("test/file.txt")
            assert result is False
    
    def test_list_prefix_error(self):
        """Test list_prefix() error handling."""
        # Mock pathlib error
        with patch('pathlib.Path.exists', side_effect=OSError("Permission denied")):
            result = self.storage.list_prefix("test/")
            assert result == []
    
    def test_delete_error(self):
        """Test delete() error handling."""
        # Mock pathlib error
        with patch('pathlib.Path.exists', side_effect=OSError("Permission denied")):
            result = self.storage.delete("test/file.txt")
            assert result is False


class TestStorageGCSInitErrors:
    """Test Storage adapter GCS initialization errors."""
    
    def test_init_gcs_missing_bucket(self):
        """Test GCS initialization with missing bucket name."""
        # Mock Flask app config
        mock_app = Mock()
        mock_app.config = {
            'USE_GCS': True,
            'GCS_BUCKET_NAME': None,
            'GOOGLE_CLOUD_PROJECT': 'test-project'
        }
        
        with patch('app.services.storage.current_app', mock_app):
            with pytest.raises(ValueError, match="GCS_BUCKET_NAME must be set"):
                Storage()
    
    def test_init_gcs_import_error(self):
        """Test GCS initialization with missing google-cloud-storage package."""
        # Mock Flask app config
        mock_app = Mock()
        mock_app.config = {
            'USE_GCS': True,
            'GCS_BUCKET_NAME': 'test-bucket',
            'GOOGLE_CLOUD_PROJECT': 'test-project'
        }
        
        with patch('app.services.storage.current_app', mock_app):
            with patch('builtins.__import__', side_effect=ImportError("No module named 'google.cloud.storage'")):
                with pytest.raises(ImportError, match="google-cloud-storage package is required"):
                    Storage()
    
    def test_init_gcs_bucket_not_found(self):
        """Test GCS initialization with non-existent bucket."""
        # Mock Flask app config
        mock_app = Mock()
        mock_app.config = {
            'USE_GCS': True,
            'GCS_BUCKET_NAME': 'test-bucket',
            'GOOGLE_CLOUD_PROJECT': 'test-project'
        }
        
        # Mock GCS client and bucket
        mock_client = Mock()
        mock_bucket = Mock()
        mock_bucket.exists.return_value = False
        
        with patch('app.services.storage.current_app', mock_app):
            with patch('google.cloud.storage.Client', return_value=mock_client):
                mock_client.bucket.return_value = mock_bucket
                
                with pytest.raises(RuntimeError, match="Failed to initialize GCS storage"):
                    Storage()

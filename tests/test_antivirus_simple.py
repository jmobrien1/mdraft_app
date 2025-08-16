"""
Simplified tests for antivirus scanning functionality.

This module tests the core antivirus service functionality with proper mocking.
"""

import os
import tempfile
import unittest
import socket
import requests
from unittest.mock import patch, MagicMock
import zipfile
from io import BytesIO

from app.services.antivirus import (
    AntivirusService, 
    ScanResult, 
    ScanResponse
)


class TestAntivirusServiceSimple(unittest.TestCase):
    """Simplified test cases for the antivirus service."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        
        # Create a simple test file
        with open(self.test_file, "w") as f:
            f.write("This is a test file")
    
    def tearDown(self):
        """Clean up test fixtures."""
        try:
            os.unlink(self.test_file)
            os.rmdir(self.temp_dir)
        except Exception:
            pass
    
    def test_off_mode(self):
        """Test that off mode returns clean without scanning."""
        # Create a mock config object with proper structure
        mock_config_obj = MagicMock()
        mock_antivirus = MagicMock()
        mock_antivirus.MODE = "off"
        mock_config_obj.antivirus = mock_antivirus
        
        with patch('app.config.config', mock_config_obj):
            service = AntivirusService()
            result = service.scan_file(self.test_file, "test-123")
            
            self.assertEqual(result.result, ScanResult.CLEAN)
            self.assertFalse(result.potential_macro)
            self.assertIsNone(result.virus_name)
    
    @patch('socket.socket')
    def test_clamd_clean(self, mock_socket):
        """Test ClamAV daemon with clean file."""
        # Create a mock config object with proper structure
        mock_config_obj = MagicMock()
        mock_antivirus = MagicMock()
        mock_antivirus.MODE = "clamd"
        mock_antivirus.CLAMD_HOST = "localhost"
        mock_antivirus.CLAMD_PORT = 3310
        mock_antivirus.AV_TIMEOUT_MS = 30000
        mock_antivirus.AV_REQUIRED = False
        mock_config_obj.antivirus = mock_antivirus
        
        with patch('app.config.config', mock_config_obj):
            # Mock socket response
            mock_sock = MagicMock()
            mock_sock.recv.return_value = b"/tmp/test.txt: OK\n"
            mock_socket.return_value = mock_sock
            
            service = AntivirusService()
            result = service.scan_file(self.test_file, "test-123")
            
            self.assertEqual(result.result, ScanResult.CLEAN)
            # Check that send was called with the actual file path
            mock_sock.send.assert_called_once()
            call_args = mock_sock.send.call_args[0][0]
            self.assertTrue(call_args.startswith(b"SCAN "))
            self.assertTrue(call_args.endswith(b"\n"))
    
    @patch('socket.socket')
    def test_clamd_infected(self, mock_socket):
        """Test ClamAV daemon with infected file."""
        # Create a mock config object with proper structure
        mock_config_obj = MagicMock()
        mock_antivirus = MagicMock()
        mock_antivirus.MODE = "clamd"
        mock_antivirus.CLAMD_HOST = "localhost"
        mock_antivirus.CLAMD_PORT = 3310
        mock_antivirus.AV_TIMEOUT_MS = 30000
        mock_antivirus.AV_REQUIRED = False
        mock_config_obj.antivirus = mock_antivirus
        
        with patch('app.config.config', mock_config_obj):
            # Mock socket response for infected file
            mock_sock = MagicMock()
            # Use a response that will match the endswith check
            mock_sock.recv.return_value = b"test.txt: EICAR-Test-Signature FOUND\n"
            mock_socket.return_value = mock_sock
            
            service = AntivirusService()
            result = service.scan_file(self.test_file, "test-123")
            
            self.assertEqual(result.result, ScanResult.INFECTED)
            self.assertEqual(result.virus_name, "EICAR-Test-Signature")
    
    @patch('requests.post')
    def test_http_clean(self, mock_post):
        """Test HTTP antivirus service with clean file."""
        # Create a mock config object with proper structure
        mock_config_obj = MagicMock()
        mock_antivirus = MagicMock()
        mock_antivirus.MODE = "http"
        mock_antivirus.AV_HTTP_ENDPOINT = "https://av.example.com/scan"
        mock_antivirus.AV_TIMEOUT_MS = 30000
        mock_antivirus.AV_REQUIRED = False
        mock_config_obj.antivirus = mock_antivirus
        
        with patch('app.config.config', mock_config_obj):
            # Mock HTTP response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"clean": True}
            mock_post.return_value = mock_response
            
            service = AntivirusService()
            result = service.scan_file(self.test_file, "test-123")
            
            self.assertEqual(result.result, ScanResult.CLEAN)
            mock_post.assert_called_once()
    
    def test_office_macro_detection(self):
        """Test Office document macro detection."""
        # Create a mock Office document with VBA project
        zip_data = BytesIO()
        with zipfile.ZipFile(zip_data, 'w') as zip_file:
            zip_file.writestr('word/document.xml', '<xml>test</xml>')
            zip_file.writestr('word/vbaProject.bin', 'fake vba data')
        
        zip_data.seek(0)
        
        # Save to temporary file
        macro_file = os.path.join(self.temp_dir, "test.docx")
        with open(macro_file, 'wb') as f:
            f.write(zip_data.getvalue())
        
        try:
            # Create a mock config object with proper structure
            mock_config_obj = MagicMock()
            mock_antivirus = MagicMock()
            mock_antivirus.MODE = "clamd"
            mock_antivirus.CLAMD_HOST = "localhost"
            mock_antivirus.CLAMD_PORT = 3310
            mock_antivirus.AV_TIMEOUT_MS = 30000
            mock_antivirus.AV_REQUIRED = False
            mock_config_obj.antivirus = mock_antivirus
            
            with patch('app.config.config', mock_config_obj):
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    mock_sock.recv.return_value = b"/tmp/test.docx: OK\n"
                    mock_socket.return_value = mock_sock
                    
                    service = AntivirusService()
                    result = service.scan_file(macro_file, "test-123")
                    
                    self.assertEqual(result.result, ScanResult.CLEAN)
                    self.assertTrue(result.potential_macro)
        finally:
            try:
                os.unlink(macro_file)
            except Exception:
                pass
    
    def test_office_no_macro_detection(self):
        """Test Office document without macro detection."""
        # Create a mock Office document without VBA project
        zip_data = BytesIO()
        with zipfile.ZipFile(zip_data, 'w') as zip_file:
            zip_file.writestr('word/document.xml', '<xml>test</xml>')
            zip_file.writestr('word/settings.xml', '<xml>settings</xml>')
        
        zip_data.seek(0)
        
        # Save to temporary file
        clean_file = os.path.join(self.temp_dir, "clean.docx")
        with open(clean_file, 'wb') as f:
            f.write(zip_data.getvalue())
        
        try:
            # Create a mock config object with proper structure
            mock_config_obj = MagicMock()
            mock_antivirus = MagicMock()
            mock_antivirus.MODE = "clamd"
            mock_antivirus.CLAMD_HOST = "localhost"
            mock_antivirus.CLAMD_PORT = 3310
            mock_antivirus.AV_TIMEOUT_MS = 30000
            mock_antivirus.AV_REQUIRED = False
            mock_config_obj.antivirus = mock_antivirus
            
            with patch('app.config.config', mock_config_obj):
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    mock_sock.recv.return_value = b"/tmp/clean.docx: OK\n"
                    mock_socket.return_value = mock_sock
                    
                    service = AntivirusService()
                    result = service.scan_file(clean_file, "test-123")
                    
                    self.assertEqual(result.result, ScanResult.CLEAN)
                    self.assertFalse(result.potential_macro)
        finally:
            try:
                os.unlink(clean_file)
            except Exception:
                pass
    
    def test_av_required_fail_closed(self):
        """Test that AV_REQUIRED causes failures to fail closed."""
        # Create a mock config object with proper structure
        mock_config_obj = MagicMock()
        mock_antivirus = MagicMock()
        mock_antivirus.MODE = "clamd"
        mock_antivirus.CLAMD_HOST = "localhost"
        mock_antivirus.CLAMD_PORT = 3310
        mock_antivirus.AV_TIMEOUT_MS = 30000
        mock_antivirus.AV_REQUIRED = True
        mock_config_obj.antivirus = mock_antivirus
        
        with patch('app.config.config', mock_config_obj):
            with patch('socket.socket') as mock_socket:
                # Mock socket connection failure
                mock_socket.side_effect = Exception("Connection failed")
                
                service = AntivirusService()
                result = service.scan_file(self.test_file, "test-123")
                
                self.assertEqual(result.result, ScanResult.ERROR)
                self.assertIn("ClamAV scan error", result.error_message)
    
    def test_av_not_required_fail_open(self):
        """Test that AV_REQUIRED=False allows failures to continue."""
        # Create a mock config object with proper structure
        mock_config_obj = MagicMock()
        mock_antivirus = MagicMock()
        mock_antivirus.MODE = "clamd"
        mock_antivirus.CLAMD_HOST = "localhost"
        mock_antivirus.CLAMD_PORT = 3310
        mock_antivirus.AV_TIMEOUT_MS = 30000
        mock_antivirus.AV_REQUIRED = False
        mock_config_obj.antivirus = mock_antivirus
        
        with patch('app.config.config', mock_config_obj):
            with patch('socket.socket') as mock_socket:
                # Mock socket connection failure
                mock_socket.side_effect = Exception("Connection failed")
                
                service = AntivirusService()
                result = service.scan_file(self.test_file, "test-123")
                
                self.assertEqual(result.result, ScanResult.CLEAN)
    
    def test_invalid_mode(self):
        """Test that invalid mode raises ValueError."""
        # Create a mock config object with proper structure
        mock_config_obj = MagicMock()
        mock_antivirus = MagicMock()
        mock_antivirus.MODE = "invalid"
        mock_config_obj.antivirus = mock_antivirus
        
        with patch('app.config.config', mock_config_obj):
            service = AntivirusService()
            with self.assertRaises(ValueError):
                service.scan_file(self.test_file, "test-123")
    
    def test_clamd_missing_config(self):
        """Test that ClamAV mode requires proper configuration."""
        # Create a mock config object with proper structure
        mock_config_obj = MagicMock()
        mock_antivirus = MagicMock()
        mock_antivirus.MODE = "clamd"
        mock_antivirus.CLAMD_SOCKET = None
        mock_antivirus.CLAMD_HOST = None
        mock_config_obj.antivirus = mock_antivirus
        
        with patch('app.config.config', mock_config_obj):
            service = AntivirusService()
            with self.assertRaises(ValueError):
                service.scan_file(self.test_file, "test-123")
    
    def test_http_missing_endpoint(self):
        """Test that HTTP mode requires endpoint configuration."""
        # Create a mock config object with proper structure
        mock_config_obj = MagicMock()
        mock_antivirus = MagicMock()
        mock_antivirus.MODE = "http"
        mock_antivirus.AV_HTTP_ENDPOINT = None
        mock_config_obj.antivirus = mock_antivirus
        
        with patch('app.config.config', mock_config_obj):
            service = AntivirusService()
            with self.assertRaises(ValueError):
                service.scan_file(self.test_file, "test-123")


if __name__ == '__main__':
    unittest.main()

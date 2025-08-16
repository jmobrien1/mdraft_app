"""
Tests for antivirus scanning functionality.

This module tests the antivirus service with various configurations
and scenarios including ClamAV, HTTP scanning, and macro detection.
"""

import os
import tempfile
import unittest
import socket
import requests
from unittest.mock import patch, MagicMock, mock_open
import zipfile
from io import BytesIO

from app.services.antivirus import (
    AntivirusService, 
    ScanResult, 
    ScanResponse, 
    get_antivirus_service,
    scan_file
)
from app.config import get_config


class TestAntivirusService(unittest.TestCase):
    """Test cases for the antivirus service."""
    
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
        # Create a mock config object
        mock_config_obj = MagicMock()
        mock_config_obj.antivirus.MODE = "off"
        
        with patch('app.config.get_config', return_value=mock_config_obj):
            service = AntivirusService()
            result = service.scan_file(self.test_file, "test-123")
            
            self.assertEqual(result.result, ScanResult.CLEAN)
            self.assertFalse(result.potential_macro)
            self.assertIsNone(result.virus_name)
    
    @patch('socket.socket')
    def test_clamd_clean(self, mock_socket):
        """Test ClamAV daemon with clean file."""
        # Create a mock config object
        mock_config_obj = MagicMock()
        mock_config_obj.antivirus.MODE = "clamd"
        mock_config_obj.antivirus.CLAMD_HOST = "localhost"
        mock_config_obj.antivirus.CLAMD_PORT = 3310
        mock_config_obj.antivirus.AV_TIMEOUT_MS = 30000
        mock_config_obj.antivirus.AV_REQUIRED = False
        
        with patch('app.config.get_config', return_value=mock_config_obj):
            # Mock socket response
            mock_sock = MagicMock()
            mock_sock.recv.return_value = b"/tmp/test.txt: OK\n"
            mock_socket.return_value = mock_sock
            
            service = AntivirusService()
            result = service.scan_file(self.test_file, "test-123")
            
            self.assertEqual(result.result, ScanResult.CLEAN)
            mock_sock.send.assert_called_once_with(b"SCAN /tmp/test.txt\n")
    
    @patch('socket.socket')
    def test_clamd_infected(self, mock_socket):
        """Test ClamAV daemon with infected file."""
        with patch('app.config.get_config') as mock_config:
            mock_config.return_value.antivirus.MODE = "clamd"
            mock_config.return_value.antivirus.CLAMD_HOST = "localhost"
            mock_config.return_value.antivirus.CLAMD_PORT = 3310
            mock_config.return_value.antivirus.AV_TIMEOUT_MS = 30000
            mock_config.return_value.antivirus.AV_REQUIRED = False
            
            # Mock socket response for infected file
            mock_sock = MagicMock()
            mock_sock.recv.return_value = b"/tmp/test.txt: EICAR-Test-Signature FOUND\n"
            mock_socket.return_value = mock_sock
            
            service = AntivirusService()
            result = service.scan_file(self.test_file, "test-123")
            
            self.assertEqual(result.result, ScanResult.INFECTED)
            self.assertEqual(result.virus_name, "EICAR-Test-Signature")
    
    @patch('socket.socket')
    def test_clamd_timeout(self, mock_socket):
        """Test ClamAV daemon timeout handling."""
        with patch('app.config.get_config') as mock_config:
            mock_config.return_value.antivirus.MODE = "clamd"
            mock_config.return_value.antivirus.CLAMD_HOST = "localhost"
            mock_config.return_value.antivirus.CLAMD_PORT = 3310
            mock_config.return_value.antivirus.AV_TIMEOUT_MS = 1000
            mock_config.return_value.antivirus.AV_REQUIRED = False
            
            # Mock socket timeout
            mock_sock = MagicMock()
            mock_sock.recv.side_effect = socket.timeout()
            mock_socket.return_value = mock_sock
            
            service = AntivirusService()
            result = service.scan_file(self.test_file, "test-123")
            
            self.assertEqual(result.result, ScanResult.TIMEOUT)
            self.assertIn("timeout", result.error_message.lower())
    
    @patch('requests.post')
    def test_http_clean(self, mock_post):
        """Test HTTP antivirus service with clean file."""
        with patch('app.config.get_config') as mock_config:
            mock_config.return_value.antivirus.MODE = "http"
            mock_config.return_value.antivirus.AV_HTTP_ENDPOINT = "https://av.example.com/scan"
            mock_config.return_value.antivirus.AV_TIMEOUT_MS = 30000
            mock_config.return_value.antivirus.AV_REQUIRED = False
            
            # Mock HTTP response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"clean": True}
            mock_post.return_value = mock_response
            
            service = AntivirusService()
            result = service.scan_file(self.test_file, "test-123")
            
            self.assertEqual(result.result, ScanResult.CLEAN)
            mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_http_infected(self, mock_post):
        """Test HTTP antivirus service with infected file."""
        with patch('app.config.get_config') as mock_config:
            mock_config.return_value.antivirus.MODE = "http"
            mock_config.return_value.antivirus.AV_HTTP_ENDPOINT = "https://av.example.com/scan"
            mock_config.return_value.antivirus.AV_TIMEOUT_MS = 30000
            mock_config.return_value.antivirus.AV_REQUIRED = False
            
            # Mock HTTP response for infected file
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"infected": True, "virus_name": "Test.Virus"}
            mock_post.return_value = mock_response
            
            service = AntivirusService()
            result = service.scan_file(self.test_file, "test-123")
            
            self.assertEqual(result.result, ScanResult.INFECTED)
            self.assertEqual(result.virus_name, "Test.Virus")
    
    @patch('requests.post')
    def test_http_timeout(self, mock_post):
        """Test HTTP antivirus service timeout handling."""
        with patch('app.config.get_config') as mock_config:
            mock_config.return_value.antivirus.MODE = "http"
            mock_config.return_value.antivirus.AV_HTTP_ENDPOINT = "https://av.example.com/scan"
            mock_config.return_value.antivirus.AV_TIMEOUT_MS = 1000
            mock_config.return_value.antivirus.AV_REQUIRED = False
            
            # Mock HTTP timeout
            mock_post.side_effect = requests.exceptions.Timeout()
            
            service = AntivirusService()
            result = service.scan_file(self.test_file, "test-123")
            
            self.assertEqual(result.result, ScanResult.TIMEOUT)
            self.assertIn("timeout", result.error_message.lower())
    
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
            with patch('app.config.get_config') as mock_config:
                mock_config.return_value.antivirus.MODE = "clamd"
                mock_config.return_value.antivirus.CLAMD_HOST = "localhost"
                mock_config.return_value.antivirus.CLAMD_PORT = 3310
                mock_config.return_value.antivirus.AV_TIMEOUT_MS = 30000
                mock_config.return_value.antivirus.AV_REQUIRED = False
                
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
            with patch('app.config.get_config') as mock_config:
                mock_config.return_value.antivirus.MODE = "clamd"
                mock_config.return_value.antivirus.CLAMD_HOST = "localhost"
                mock_config.return_value.antivirus.CLAMD_PORT = 3310
                mock_config.return_value.antivirus.AV_TIMEOUT_MS = 30000
                mock_config.return_value.antivirus.AV_REQUIRED = False
                
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
        with patch('app.config.get_config') as mock_config:
            mock_config.return_value.antivirus.MODE = "clamd"
            mock_config.return_value.antivirus.CLAMD_HOST = "localhost"
            mock_config.return_value.antivirus.CLAMD_PORT = 3310
            mock_config.return_value.antivirus.AV_TIMEOUT_MS = 30000
            mock_config.return_value.antivirus.AV_REQUIRED = True
            
            with patch('socket.socket') as mock_socket:
                # Mock socket connection failure
                mock_socket.side_effect = Exception("Connection failed")
                
                service = AntivirusService()
                result = service.scan_file(self.test_file, "test-123")
                
                self.assertEqual(result.result, ScanResult.ERROR)
                self.assertIn("Antivirus scan failed", result.error_message)
    
    def test_av_not_required_fail_open(self):
        """Test that AV_REQUIRED=False allows failures to continue."""
        with patch('app.config.get_config') as mock_config:
            mock_config.return_value.antivirus.MODE = "clamd"
            mock_config.return_value.antivirus.CLAMD_HOST = "localhost"
            mock_config.return_value.antivirus.CLAMD_PORT = 3310
            mock_config.return_value.antivirus.AV_TIMEOUT_MS = 30000
            mock_config.return_value.antivirus.AV_REQUIRED = False
            
            with patch('socket.socket') as mock_socket:
                # Mock socket connection failure
                mock_socket.side_effect = Exception("Connection failed")
                
                service = AntivirusService()
                result = service.scan_file(self.test_file, "test-123")
                
                self.assertEqual(result.result, ScanResult.CLEAN)
    
    def test_invalid_mode(self):
        """Test that invalid mode raises ValueError."""
        with patch('app.config.get_config') as mock_config:
            mock_config.return_value.antivirus.MODE = "invalid"
            
            with self.assertRaises(ValueError):
                AntivirusService()
    
    def test_clamd_missing_config(self):
        """Test that ClamAV mode requires proper configuration."""
        with patch('app.config.get_config') as mock_config:
            mock_config.return_value.antivirus.MODE = "clamd"
            mock_config.return_value.antivirus.CLAMD_SOCKET = None
            mock_config.return_value.antivirus.CLAMD_HOST = None
            
            with self.assertRaises(ValueError):
                AntivirusService()
    
    def test_http_missing_endpoint(self):
        """Test that HTTP mode requires endpoint configuration."""
        with patch('app.config.get_config') as mock_config:
            mock_config.return_value.antivirus.MODE = "http"
            mock_config.return_value.antivirus.AV_HTTP_ENDPOINT = None
            
            with self.assertRaises(ValueError):
                AntivirusService()
    
    def test_scan_time_tracking(self):
        """Test that scan time is properly tracked."""
        with patch('app.config.get_config') as mock_config:
            mock_config.return_value.antivirus.MODE = "clamd"
            mock_config.return_value.antivirus.CLAMD_HOST = "localhost"
            mock_config.return_value.antivirus.CLAMD_PORT = 3310
            mock_config.return_value.antivirus.AV_TIMEOUT_MS = 30000
            mock_config.return_value.antivirus.AV_REQUIRED = False
            
            with patch('socket.socket') as mock_socket:
                mock_sock = MagicMock()
                mock_sock.recv.return_value = b"/tmp/test.txt: OK\n"
                mock_socket.return_value = mock_sock
                
                service = AntivirusService()
                result = service.scan_file(self.test_file, "test-123")
                
                self.assertIsNotNone(result.scan_time_ms)
                self.assertGreaterEqual(result.scan_time_ms, 0)


class TestAntivirusIntegration(unittest.TestCase):
    """Integration tests for antivirus functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass
    
    def test_eicar_sample_detection(self):
        """Test EICAR sample detection."""
        # Create EICAR test file
        eicar_content = b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
        eicar_file = os.path.join(self.temp_dir, "eicar.txt")
        
        with open(eicar_file, 'wb') as f:
            f.write(eicar_content)
        
        try:
            with patch('app.config.get_config') as mock_config:
                mock_config.return_value.antivirus.MODE = "clamd"
                mock_config.return_value.antivirus.CLAMD_HOST = "localhost"
                mock_config.return_value.antivirus.CLAMD_PORT = 3310
                mock_config.return_value.antivirus.AV_TIMEOUT_MS = 30000
                mock_config.return_value.antivirus.AV_REQUIRED = False
                
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    mock_sock.recv.return_value = b"/tmp/eicar.txt: EICAR-Test-Signature FOUND\n"
                    mock_socket.return_value = mock_sock
                    
                    service = AntivirusService()
                    result = service.scan_file(eicar_file, "eicar-test")
                    
                    self.assertEqual(result.result, ScanResult.INFECTED)
                    self.assertEqual(result.virus_name, "EICAR-Test-Signature")
        finally:
            try:
                os.unlink(eicar_file)
            except Exception:
                pass
    
    def test_global_service_instance(self):
        """Test global service instance management."""
        # Reset global instance
        import app.services.antivirus
        app.services.antivirus._antivirus_service = None
        
        with patch('app.config.get_config') as mock_config:
            mock_config.return_value.antivirus.MODE = "off"
            
            # Get service instance
            service1 = get_antivirus_service()
            service2 = get_antivirus_service()
            
            # Should be the same instance
            self.assertIs(service1, service2)
    
    def test_scan_file_convenience(self):
        """Test scan_file convenience function."""
        with patch('app.config.get_config') as mock_config:
            mock_config.return_value.antivirus.MODE = "off"
            
            # Create a test file
            test_file = os.path.join(self.temp_dir, "test.txt")
            with open(test_file, 'w') as f:
                f.write("test content")
            
            try:
                result = scan_file(test_file, "convenience-test")
                self.assertEqual(result.result, ScanResult.CLEAN)
            finally:
                try:
                    os.unlink(test_file)
                except Exception:
                    pass


if __name__ == '__main__':
    unittest.main()

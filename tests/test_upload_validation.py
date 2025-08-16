"""
Comprehensive tests for file upload validation system.

Tests cover content-sniffing, size limits, security checks, and error handling.
"""

import os
import tempfile
import zipfile
from io import BytesIO
import pytest
from unittest.mock import patch, MagicMock

from app.utils.validation import (
    FileValidator, 
    ValidationError, 
    ValidationResult,
    validate_upload_file
)


class TestFileValidator:
    """Test the FileValidator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = FileValidator()
        
        # Create test files
        self.pdf_content = b"%PDF-1.4\n%Test PDF content"
        self.txt_content = b"This is a test text file"
        self.json_content = b'{"test": "data"}'
        self.zip_content = b'PK\x03\x04\x14\x00\x00\x00\x08\x00'  # Minimal ZIP header
        
    def test_valid_pdf_file(self):
        """Test validation of a valid PDF file."""
        stream = BytesIO(self.pdf_content)
        result = self.validator.validate_file(stream, "test.pdf")
        
        assert result.is_valid is True
        assert result.mime_type == "application/pdf"
        assert result.category == "pdf"
        assert result.file_size == len(self.pdf_content)
        assert result.error is None
    
    def test_valid_text_file(self):
        """Test validation of a valid text file."""
        stream = BytesIO(self.txt_content)
        result = self.validator.validate_file(stream, "test.txt")
        
        assert result.is_valid is True
        assert result.mime_type == "text/plain"
        assert result.category == "text"
        assert result.file_size == len(self.txt_content)
        assert result.error is None
    
    def test_valid_json_file(self):
        """Test validation of a valid JSON file."""
        stream = BytesIO(self.json_content)
        result = self.validator.validate_file(stream, "test.json")
        
        assert result.is_valid is True
        assert result.mime_type == "application/json"
        assert result.category == "text"
        assert result.file_size == len(self.json_content)
        assert result.error is None
    
    def test_empty_file(self):
        """Test rejection of empty files."""
        stream = BytesIO(b"")
        result = self.validator.validate_file(stream, "empty.txt")
        
        assert result.is_valid is False
        assert result.error == ValidationError.EMPTY_FILE
        assert result.file_size == 0
    
    def test_file_too_large_pdf(self):
        """Test rejection of oversized PDF files."""
        # Create a PDF file larger than 25MB
        large_pdf = self.pdf_content + b"x" * (26 * 1024 * 1024)
        stream = BytesIO(large_pdf)
        result = self.validator.validate_file(stream, "large.pdf")
        
        assert result.is_valid is False
        assert result.error == ValidationError.FILE_TOO_LARGE
        assert result.mime_type == "application/pdf"
        assert result.category == "pdf"
        assert "25" in result.details  # Should mention 25MB limit
    
    def test_file_too_large_text(self):
        """Test rejection of oversized text files."""
        # Create a text file larger than 5MB
        large_text = self.txt_content + b"x" * (6 * 1024 * 1024)
        stream = BytesIO(large_text)
        result = self.validator.validate_file(stream, "large.txt")
        
        assert result.is_valid is False
        assert result.error == ValidationError.FILE_TOO_LARGE
        assert result.category == "text"
        assert "5" in result.details  # Should mention 5MB limit
    
    def test_denied_extension(self):
        """Test rejection of files with denied extensions."""
        stream = BytesIO(self.txt_content)
        result = self.validator.validate_file(stream, "test.exe")
        
        assert result.is_valid is False
        assert result.error == ValidationError.FILE_TYPE_NOT_ALLOWED
        assert "Denied extension" in result.details
    
    def test_double_extension_with_denied(self):
        """Test rejection of double extensions containing denied extensions."""
        stream = BytesIO(self.txt_content)
        result = self.validator.validate_file(stream, "test.txt.exe")
        
        assert result.is_valid is False
        assert result.error == ValidationError.DOUBLE_EXTENSION
        assert "Double extension" in result.details
    
    def test_double_extension_safe(self):
        """Test acceptance of double extensions that are safe."""
        stream = BytesIO(self.txt_content)
        result = self.validator.validate_file(stream, "test.txt.bak")
        
        assert result.is_valid is True
        assert result.mime_type == "text/plain"
        assert result.category == "text"
    
    def test_content_mismatch(self):
        """Test rejection when content doesn't match extension."""
        # Create a file with .docx extension but text content (not a ZIP file)
        stream = BytesIO(self.txt_content)
        result = self.validator.validate_file(stream, "test.docx")
        
        assert result.is_valid is False
        assert result.error == ValidationError.MALFORMED_FILE
        assert "Invalid ZIP archive" in result.details
    
    def test_unsupported_file_type(self):
        """Test rejection of unsupported file types."""
        stream = BytesIO(b"Some random binary data")
        result = self.validator.validate_file(stream, "test.bin")
        
        assert result.is_valid is False
        assert result.error == ValidationError.FILE_TYPE_NOT_ALLOWED
        assert "Unsupported file type" in result.details
    
    def test_no_filename(self):
        """Test validation without filename."""
        stream = BytesIO(self.txt_content)
        result = self.validator.validate_file(stream, "")
        
        assert result.is_valid is True
        assert result.mime_type == "text/plain"
        assert result.category == "text"
    
    def test_correlation_id_logging(self):
        """Test that correlation ID is included in logging."""
        with patch('app.utils.validation.logging.getLogger') as mock_logger:
            mock_log = MagicMock()
            mock_logger.return_value = mock_log
            
            validator = FileValidator(mock_log)
            stream = BytesIO(self.txt_content)
            result = validator.validate_file(stream, "test.txt", "test-correlation-id")
            
            assert result.is_valid is True
            # Verify that logging was called with correlation ID
            mock_log.info.assert_called()
            log_calls = [call[0][0] for call in mock_log.info.call_args_list]
            assert any("test-correlation-id" in call for call in log_calls)


class TestOfficeDocumentValidation:
    """Test Office document validation (DOCX, PPTX, XLSX)."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = FileValidator()
    
    def create_docx_zip(self):
        """Create a minimal DOCX ZIP file."""
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr('word/document.xml', '<document>test</document>')
        return zip_buffer.getvalue()
    
    def create_pptx_zip(self):
        """Create a minimal PPTX ZIP file."""
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr('ppt/presentation.xml', '<presentation>test</presentation>')
        return zip_buffer.getvalue()
    
    def create_xlsx_zip(self):
        """Create a minimal XLSX ZIP file."""
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr('xl/workbook.xml', '<workbook>test</workbook>')
        return zip_buffer.getvalue()
    
    def test_valid_docx_file(self):
        """Test validation of a valid DOCX file."""
        docx_content = self.create_docx_zip()
        stream = BytesIO(docx_content)
        result = self.validator.validate_file(stream, "test.docx")
        
        assert result.is_valid is True
        assert result.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert result.category == "office"
    
    def test_valid_pptx_file(self):
        """Test validation of a valid PPTX file."""
        pptx_content = self.create_pptx_zip()
        stream = BytesIO(pptx_content)
        result = self.validator.validate_file(stream, "test.pptx")
        
        assert result.is_valid is True
        assert result.mime_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        assert result.category == "office"
    
    def test_valid_xlsx_file(self):
        """Test validation of a valid XLSX file."""
        xlsx_content = self.create_xlsx_zip()
        stream = BytesIO(xlsx_content)
        result = self.validator.validate_file(stream, "test.xlsx")
        
        assert result.is_valid is True
        assert result.mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert result.category == "office"
    
    def test_invalid_zip_not_office(self):
        """Test rejection of ZIP files that aren't Office documents."""
        # Create a ZIP file without Office structure
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr('random.txt', 'test content')
        zip_content = zip_buffer.getvalue()
        
        stream = BytesIO(zip_content)
        result = self.validator.validate_file(stream, "test.zip")
        
        assert result.is_valid is False
        assert result.error == ValidationError.CONTENT_MISMATCH
        assert "Office document structure" in result.details
    
    def test_corrupted_zip_file(self):
        """Test rejection of corrupted ZIP files."""
        corrupted_zip = b'PK\x03\x04\x14\x00\x00\x00\x08\x00corrupted'
        stream = BytesIO(corrupted_zip)
        result = self.validator.validate_file(stream, "test.docx")
        
        assert result.is_valid is False
        assert result.error == ValidationError.MALFORMED_FILE
        assert "Invalid ZIP archive" in result.details


class TestValidationErrorHandling:
    """Test error handling and edge cases."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = FileValidator()
    
    def test_stream_seek_error(self):
        """Test handling of stream seek errors."""
        mock_stream = MagicMock()
        mock_stream.seek.side_effect = IOError("Seek failed")
        
        result = self.validator.validate_file(mock_stream, "test.txt")
        
        assert result.is_valid is False
        assert result.error == ValidationError.MALFORMED_FILE
        assert "Seek failed" in result.details
    
    def test_filetype_library_error(self):
        """Test handling of filetype library errors."""
        with patch('filetype.guess') as mock_guess:
            mock_guess.side_effect = Exception("filetype error")
            
            stream = BytesIO(b"test content")
            result = self.validator.validate_file(stream, "test.txt")
            
            assert result.is_valid is False
            assert result.error == ValidationError.MALFORMED_FILE
            assert "filetype error" in result.details


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_validate_upload_file(self):
        """Test the validate_upload_file convenience function."""
        content = b"This is a test file"
        stream = BytesIO(content)
        
        result = validate_upload_file(stream, "test.txt", "test-correlation-id")
        
        assert result.is_valid is True
        assert result.mime_type == "text/plain"
        assert result.category == "text"
    
    def test_get_validator_singleton(self):
        """Test that get_validator returns a singleton."""
        from app.utils.validation import get_validator
        
        validator1 = get_validator()
        validator2 = get_validator()
        
        assert validator1 is validator2


class TestSizeLimits:
    """Test file size limit enforcement."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = FileValidator()
    
    def test_pdf_size_limit(self):
        """Test PDF size limit (25MB)."""
        # Create a PDF file exactly at the limit
        pdf_header = b"%PDF-1.4\n"
        pdf_content = pdf_header + b"x" * (25 * 1024 * 1024 - len(pdf_header))
        stream = BytesIO(pdf_content)
        result = self.validator.validate_file(stream, "test.pdf")
        
        assert result.is_valid is True
        
        # Create a PDF file over the limit
        pdf_content = pdf_header + b"x" * (26 * 1024 * 1024)
        stream = BytesIO(pdf_content)
        result = self.validator.validate_file(stream, "test.pdf")
        
        assert result.is_valid is False
        assert result.error == ValidationError.FILE_TOO_LARGE
    
    def test_office_size_limit(self):
        """Test Office document size limit (20MB)."""
        # Create a DOCX file over the limit
        docx_content = b'PK\x03\x04' + b"x" * (21 * 1024 * 1024)
        stream = BytesIO(docx_content)
        result = self.validator.validate_file(stream, "test.docx")
        
        assert result.is_valid is False
        assert result.error == ValidationError.FILE_TOO_LARGE
    
    def test_text_size_limit(self):
        """Test text file size limit (5MB)."""
        # Create a text file over the limit
        text_content = b"x" * (6 * 1024 * 1024)
        stream = BytesIO(text_content)
        result = self.validator.validate_file(stream, "test.txt")
        
        assert result.is_valid is False
        assert result.error == ValidationError.FILE_TOO_LARGE


class TestSecurityChecks:
    """Test security-related validation checks."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = FileValidator()
    
    def test_denied_extensions(self):
        """Test various denied extensions."""
        denied_extensions = [
            ".exe", ".bat", ".cmd", ".com", ".scr", ".pif", ".vbs", ".js",
            ".jar", ".war", ".ear", ".apk", ".dmg", ".deb", ".rpm", ".msi",
            ".sh", ".py", ".php", ".asp", ".aspx", ".jsp", ".pl", ".rb",
            ".dll", ".so", ".dylib", ".sys", ".drv", ".ocx", ".cpl",
            ".lnk", ".url", ".reg", ".inf", ".ini", ".cfg", ".conf"
        ]
        
        content = b"test content"
        stream = BytesIO(content)
        
        for ext in denied_extensions:
            result = self.validator.validate_file(stream, f"test{ext}")
            assert result.is_valid is False, f"Extension {ext} should be denied"
            assert result.error == ValidationError.FILE_TYPE_NOT_ALLOWED
    
    def test_double_extension_attack(self):
        """Test double extension attack scenarios."""
        content = b"test content"
        stream = BytesIO(content)
        
        # Test various double extension patterns
        attack_patterns = [
            "document.txt.exe",
            "report.pdf.bat",
            "data.csv.cmd",
            "presentation.pptx.vbs",
            "spreadsheet.xlsx.js"
        ]
        
        for filename in attack_patterns:
            result = self.validator.validate_file(stream, filename)
            assert result.is_valid is False, f"Double extension attack {filename} should be rejected"
            assert result.error == ValidationError.DOUBLE_EXTENSION
    
    def test_safe_double_extensions(self):
        """Test that safe double extensions are allowed."""
        # Create a minimal PPTX file for testing
        pptx_buffer = BytesIO()
        with zipfile.ZipFile(pptx_buffer, 'w') as zip_file:
            zip_file.writestr('ppt/presentation.xml', '<presentation>test</presentation>')
        pptx_content = pptx_buffer.getvalue()
        
        safe_patterns = [
            ("document.txt.bak", b"test content"),
            ("report.pdf.old", b"%PDF-1.4\ntest content"),
            ("data.csv.backup", b"test,data,content"),
            ("presentation.pptx.tmp", pptx_content)
        ]
        
        for filename, content in safe_patterns:
            stream = BytesIO(content)
            result = self.validator.validate_file(stream, filename)
            assert result.is_valid is True, f"Safe double extension {filename} should be allowed"


if __name__ == "__main__":
    pytest.main([__file__])

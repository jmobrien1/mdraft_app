"""
Antivirus scanning service with support for ClamAV and HTTP-based scanning.

This module provides a unified interface for virus scanning with support for:
- ClamAV daemon (local socket/TCP)
- HTTP-based scanning services
- Office document macro detection
- Configurable timeout and error handling
"""

import os
import socket
import logging
import requests
import zipfile
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
import time

from ..config import get_config
from .reliability import resilient_call, ReliabilityError


class ScanResult(Enum):
    """Antivirus scan result enumeration."""
    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class ScanResponse:
    """Response from antivirus scan."""
    result: ScanResult
    virus_name: Optional[str] = None
    error_message: Optional[str] = None
    scan_time_ms: Optional[int] = None
    potential_macro: bool = False


class AntivirusService:
    """Antivirus scanning service with multiple backend support."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the antivirus service."""
        self.logger = logger or logging.getLogger(__name__)
        # Don't get config here - get it lazily in scan_file method
        
    def _get_config(self):
        """Get the antivirus configuration."""
        return get_config().antivirus
        
    def _validate_config(self, config):
        """Validate antivirus configuration."""
        if config.MODE not in ["off", "clamd", "http"]:
            raise ValueError(f"Invalid antivirus mode: {config.MODE}")
        
        if config.MODE == "clamd":
            # Check if either socket or host is configured
            has_socket = hasattr(config, 'CLAMD_SOCKET') and config.CLAMD_SOCKET
            has_host = hasattr(config, 'CLAMD_HOST') and config.CLAMD_HOST
            if not has_socket and not has_host:
                raise ValueError("ClamAV mode requires either CLAMD_SOCKET or CLAMD_HOST")
        
        if config.MODE == "http":
            has_endpoint = hasattr(config, 'AV_HTTP_ENDPOINT') and config.AV_HTTP_ENDPOINT
            if not has_endpoint:
                raise ValueError("HTTP mode requires AV_HTTP_ENDPOINT")
    
    def scan_file(self, file_path: str, request_id: Optional[str] = None) -> ScanResponse:
        """
        Scan a file for viruses.
        
        Args:
            file_path: Path to the file to scan
            request_id: Optional request ID for logging
            
        Returns:
            ScanResponse with scan results
        """
        log_prefix = f"[{request_id}] " if request_id else ""
        
        # Get config lazily
        config = self._get_config()
        self._validate_config(config)
        
        if config.MODE == "off":
            self.logger.debug(f"{log_prefix}Antivirus scanning disabled")
            return ScanResponse(result=ScanResult.CLEAN)
        
        start_time = time.time()
        
        try:
            # Check for potential macros in Office documents
            potential_macro = self._check_for_macros(file_path)
            
            if config.MODE == "clamd":
                result = self._scan_with_clamd(file_path, config)
            elif config.MODE == "http":
                result = self._scan_with_http(file_path, config)
            else:
                result = ScanResponse(result=ScanResult.CLEAN)
            
            scan_time_ms = int((time.time() - start_time) * 1000)
            result.scan_time_ms = scan_time_ms
            result.potential_macro = potential_macro
            
            self.logger.info(
                f"{log_prefix}Antivirus scan completed: {result.result.value} "
                f"({scan_time_ms}ms, macro: {potential_macro})"
            )
            
            return result
            
        except (ValueError, TimeoutError) as e:
            scan_time_ms = int((time.time() - start_time) * 1000)
            self.logger.warning(f"{log_prefix}Antivirus scan error: {e}")
            
            if config.AV_REQUIRED:
                return ScanResponse(
                    result=ScanResult.ERROR,
                    error_message=f"Antivirus scan failed: {str(e)}",
                    scan_time_ms=scan_time_ms
                )
            else:
                # Fail open - log warning but continue
                self.logger.warning(f"{log_prefix}Antivirus scan failed, continuing: {e}")
                return ScanResponse(
                    result=ScanResult.CLEAN,
                    scan_time_ms=scan_time_ms
                )
        except Exception as e:
            scan_time_ms = int((time.time() - start_time) * 1000)
            self.logger.exception(f"{log_prefix}Antivirus scan error: {e}")
            
            if config.AV_REQUIRED:
                return ScanResponse(
                    result=ScanResult.ERROR,
                    error_message=f"Antivirus scan failed: {str(e)}",
                    scan_time_ms=scan_time_ms
                )
            else:
                # Fail open - log warning but continue
                self.logger.warning(f"{log_prefix}Antivirus scan failed, continuing: {e}")
                return ScanResponse(
                    result=ScanResult.CLEAN,
                    scan_time_ms=scan_time_ms
                )
    
    def _scan_with_clamd(self, file_path: str, config) -> ScanResponse:
        """Scan file using ClamAV daemon with reliability features."""
        def _clamd_scan():
            # Connect to ClamAV daemon
            if hasattr(config, 'CLAMD_SOCKET') and config.CLAMD_SOCKET:
                # Unix socket connection
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(config.AV_TIMEOUT_MS / 1000.0)
                sock.connect(config.CLAMD_SOCKET)
            else:
                # TCP connection
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(config.AV_TIMEOUT_MS / 1000.0)
                sock.connect((config.CLAMD_HOST, config.CLAMD_PORT))
            
            # Send SCAN command
            scan_command = f"SCAN {file_path}\n".encode('utf-8')
            sock.send(scan_command)
            
            # Read response
            response = sock.recv(4096).decode('utf-8').strip()
            sock.close()
            
            # Parse response
            if response.endswith(": OK"):
                return ScanResponse(result=ScanResult.CLEAN)
            elif " FOUND" in response:
                # Extract virus name
                parts = response.split(": ")
                if len(parts) >= 2:
                    # The last part should be "VIRUS_NAME FOUND", so split by space and take the first part
                    virus_part = parts[-1]
                    virus_name = virus_part.split()[0] if virus_part else "unknown"
                else:
                    virus_name = "unknown"
                return ScanResponse(
                    result=ScanResult.INFECTED,
                    virus_name=virus_name
                )
            else:
                raise ValueError(f"Unexpected ClamAV response: {response}")
        
        # Use resilient_call for automatic retries and circuit breaker
        return resilient_call(
            service_name="clamav",
            endpoint="scan",
            func=_clamd_scan,
            timeout_sec=config.AV_TIMEOUT_MS / 1000.0
        )
    
    def _scan_with_http(self, file_path: str, config) -> ScanResponse:
        """Scan file using HTTP-based antivirus service with reliability features."""
        def _http_scan():
            with open(file_path, 'rb') as f:
                files = {'file': f}
                
                response = requests.post(
                    config.AV_HTTP_ENDPOINT,
                    files=files,
                    timeout=config.AV_TIMEOUT_MS / 1000.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Common response formats
                    if data.get('clean') is True:
                        return ScanResponse(result=ScanResult.CLEAN)
                    elif data.get('infected') is True:
                        virus_name = data.get('virus_name', 'unknown')
                        return ScanResponse(
                            result=ScanResult.INFECTED,
                            virus_name=virus_name
                        )
                    elif data.get('status') == 'clean':
                        return ScanResponse(result=ScanResult.CLEAN)
                    elif data.get('status') == 'infected':
                        virus_name = data.get('threat', 'unknown')
                        return ScanResponse(
                            result=ScanResult.INFECTED,
                            virus_name=virus_name
                        )
                    else:
                        return ScanResponse(
                            result=ScanResult.ERROR,
                            error_message=f"Unexpected HTTP response format: {data}"
                        )
                else:
                    return ScanResponse(
                        result=ScanResult.ERROR,
                        error_message=f"HTTP scan failed with status {response.status_code}"
                    )
        
        # Use resilient_call for automatic retries and circuit breaker
        return resilient_call(
            service_name="antivirus_http",
            endpoint="scan",
            func=_http_scan,
            timeout_sec=config.AV_TIMEOUT_MS / 1000.0
        )
    
    def _check_for_macros(self, file_path: str) -> bool:
        """
        Check for potential macros in Office documents.
        
        This is a lightweight check that looks for macro indicators
        in Office document ZIP structures.
        """
        try:
            # Check if file is a ZIP (Office document)
            with open(file_path, 'rb') as f:
                magic = f.read(4)
                if magic != b'PK\x03\x04':
                    return False
            
            # Check for macro indicators in Office documents
            with zipfile.ZipFile(file_path) as zip_file:
                file_list = zip_file.namelist()
                
                # Check for VBA project files
                vba_indicators = [
                    'word/vbaProject.bin',
                    'ppt/vbaProject.bin',
                    'xl/vbaProject.bin',
                    'word/_rels/vbaProject.bin.rels',
                    'ppt/_rels/vbaProject.bin.rels',
                    'xl/_rels/vbaProject.bin.rels'
                ]
                
                for indicator in vba_indicators:
                    if indicator in file_list:
                        return True
                
                # Check for macro-enabled file extensions in content
                macro_extensions = ['.docm', '.xlsm', '.pptm']
                for name in file_list:
                    if any(ext in name.lower() for ext in macro_extensions):
                        return True
                
                return False
                
        except Exception:
            # If we can't check, assume no macros
            return False


# Global antivirus service instance
_antivirus_service = None


def get_antivirus_service() -> AntivirusService:
    """Get the global antivirus service instance."""
    global _antivirus_service
    if _antivirus_service is None:
        _antivirus_service = AntivirusService()
    return _antivirus_service


def scan_file(file_path: str, request_id: Optional[str] = None) -> ScanResponse:
    """
    Convenience function for file scanning.
    
    Args:
        file_path: Path to the file to scan
        request_id: Optional request ID for logging
        
    Returns:
        ScanResponse with scan results
    """
    service = get_antivirus_service()
    return service.scan_file(file_path, request_id)

"""
Tests for Content Security Policy (CSP) and security headers.

This module tests that:
1. CSP configuration has secure defaults
2. CSP policy is properly constructed from configuration
3. Environment variable overrides work correctly
4. Policy follows security best practices
"""

import pytest
import os
from app.config import get_config, CSPConfig


class TestCSPConfiguration:
    """Test Content Security Policy configuration and policy construction."""
    
    def test_csp_config_defaults(self):
        """Test that CSP configuration has secure defaults."""
        config = get_config()
        
        # Verify default CSP values are secure
        assert config.csp.DEFAULT_SRC == "'self'"
        assert config.csp.SCRIPT_SRC == "'self'"
        assert config.csp.STYLE_SRC == "'self' 'unsafe-inline'"
        assert config.csp.IMG_SRC == "'self' data:"
        assert config.csp.CONNECT_SRC == "'self' https:"
        assert config.csp.FRAME_ANCESTORS == "'none'"
        assert config.csp.OBJECT_SRC == "'none'"
        assert config.csp.BASE_URI == "'self'"
        assert config.csp.UPGRADE_INSECURE_REQUESTS is True
    
    def test_csp_policy_construction(self):
        """Test that CSP policy is properly constructed."""
        config = get_config()
        policy = config.csp.build_policy()
        
        # Verify all required directives are present
        assert "default-src 'self'" in policy
        assert "object-src 'none'" in policy
        assert "base-uri 'self'" in policy
        assert "frame-ancestors 'none'" in policy
        assert "img-src 'self' data:" in policy
        assert "style-src 'self' 'unsafe-inline'" in policy
        assert "script-src 'self'" in policy
        assert "connect-src 'self' https:" in policy
        assert "upgrade-insecure-requests" in policy
        
        # Verify policy format (semicolon-separated)
        directives = policy.split("; ")
        assert len(directives) >= 9  # At least 9 directives
        
        # Verify no duplicate directives
        directive_names = [d.split()[0] for d in directives]
        assert len(directive_names) == len(set(directive_names))
    
    def test_csp_policy_with_report_uri(self):
        """Test CSP policy construction with report URI."""
        # Create a test CSP config with report URI
        csp_config = CSPConfig(
            DEFAULT_SRC="'self'",
            SCRIPT_SRC="'self'",
            STYLE_SRC="'self' 'unsafe-inline'",
            IMG_SRC="'self' data:",
            CONNECT_SRC="'self' https:",
            FRAME_ANCESTORS="'none'",
            REPORT_URI="https://example.com/csp-report",
            OBJECT_SRC="'none'",
            BASE_URI="'self'",
            UPGRADE_INSECURE_REQUESTS=True
        )
        
        policy = csp_config.build_policy()
        assert "report-uri https://example.com/csp-report" in policy
    
    def test_csp_policy_without_report_uri(self):
        """Test CSP policy construction without report URI."""
        # Create a test CSP config without report URI
        csp_config = CSPConfig(
            DEFAULT_SRC="'self'",
            SCRIPT_SRC="'self'",
            STYLE_SRC="'self' 'unsafe-inline'",
            IMG_SRC="'self' data:",
            CONNECT_SRC="'self' https:",
            FRAME_ANCESTORS="'none'",
            REPORT_URI=None,
            OBJECT_SRC="'none'",
            BASE_URI="'self'",
            UPGRADE_INSECURE_REQUESTS=True
        )
        
        policy = csp_config.build_policy()
        assert "report-uri" not in policy
    
    def test_csp_policy_without_upgrade_insecure_requests(self):
        """Test CSP policy construction without upgrade-insecure-requests."""
        # Create a test CSP config without upgrade-insecure-requests
        csp_config = CSPConfig(
            DEFAULT_SRC="'self'",
            SCRIPT_SRC="'self'",
            STYLE_SRC="'self' 'unsafe-inline'",
            IMG_SRC="'self' data:",
            CONNECT_SRC="'self' https:",
            FRAME_ANCESTORS="'none'",
            REPORT_URI=None,
            OBJECT_SRC="'none'",
            BASE_URI="'self'",
            UPGRADE_INSECURE_REQUESTS=False
        )
        
        policy = csp_config.build_policy()
        assert "upgrade-insecure-requests" not in policy
    
    def test_csp_policy_security_analysis(self):
        """Test that CSP policy follows security best practices."""
        config = get_config()
        policy = config.csp.build_policy()
        
        # Verify secure defaults
        assert "object-src 'none'" in policy  # No plugins
        assert "frame-ancestors 'none'" in policy  # No embedding
        assert "base-uri 'self'" in policy  # Restrict base tag
        assert "upgrade-insecure-requests" in policy  # Force HTTPS
        
        # Verify script-src doesn't include unsafe-inline by default
        # (only style-src should have it for CSS)
        assert "script-src 'self'" in policy
        assert "script-src 'unsafe-inline'" not in policy
        
        # Verify connect-src allows HTTPS but not HTTP
        assert "connect-src 'self' https:" in policy
        assert "connect-src 'self' http:" not in policy
    
    def test_csp_environment_override_simulation(self):
        """Test that CSP can be overridden via environment variables."""
        # Test by directly creating CSPConfig with custom values
        # This simulates what would happen with environment variable overrides
        
        # Create a test CSP config with overridden values
        csp_config = CSPConfig(
            DEFAULT_SRC="'self'",
            SCRIPT_SRC="'self' 'unsafe-eval' https://cdn.example.com",
            STYLE_SRC="'self' 'unsafe-inline'",
            IMG_SRC="'self' data:",
            CONNECT_SRC="'self' https://api.example.com",
            FRAME_ANCESTORS="'none'",
            REPORT_URI="https://sentry.io/csp-report",
            OBJECT_SRC="'none'",
            BASE_URI="'self'",
            UPGRADE_INSECURE_REQUESTS=True
        )
        
        # Verify overridden values
        assert "'unsafe-eval'" in csp_config.SCRIPT_SRC
        assert "https://cdn.example.com" in csp_config.SCRIPT_SRC
        assert "https://api.example.com" in csp_config.CONNECT_SRC
        assert csp_config.REPORT_URI == 'https://sentry.io/csp-report'
        
        # Verify policy includes overridden values
        policy = csp_config.build_policy()
        assert "'unsafe-eval'" in policy
        assert "https://cdn.example.com" in policy
        assert "https://api.example.com" in policy
        assert "report-uri https://sentry.io/csp-report" in policy
    
    def test_csp_directive_ordering(self):
        """Test that CSP directives are consistently ordered."""
        config = get_config()
        policy = config.csp.build_policy()
        
        # Split policy into directives
        directives = [d.strip() for d in policy.split(";")]
        
        # Verify expected order (alphabetical within logical groups)
        directive_names = [d.split()[0] for d in directives if d]
        
        # Check that base-uri comes before connect-src
        base_uri_index = directive_names.index("base-uri")
        connect_src_index = directive_names.index("connect-src")
        assert base_uri_index < connect_src_index
        
        # Check that default-src comes before other src directives
        default_src_index = directive_names.index("default-src")
        script_src_index = directive_names.index("script-src")
        assert default_src_index < script_src_index
    
    def test_csp_policy_length_limits(self):
        """Test that CSP policy doesn't exceed reasonable length limits."""
        config = get_config()
        policy = config.csp.build_policy()
        
        # CSP policies should be reasonable length (not too long)
        assert len(policy) < 2000  # Reasonable upper limit
        
        # Each directive should be reasonable length
        directives = policy.split("; ")
        for directive in directives:
            assert len(directive) < 500  # Individual directive limit
    
    def test_csp_unsafe_directives_analysis(self):
        """Test that CSP policy minimizes unsafe directives."""
        config = get_config()
        policy = config.csp.build_policy()
        
        # Check for unsafe directives that should be avoided
        unsafe_patterns = [
            "script-src 'unsafe-eval'",
            "script-src 'unsafe-inline'",
            "style-src 'unsafe-eval'",
            "object-src 'self'",
            "object-src 'unsafe-inline'",
            "base-uri 'unsafe-inline'",
            "base-uri *"
        ]
        
        # By default, only style-src should have unsafe-inline (for CSS)
        for pattern in unsafe_patterns:
            if pattern == "style-src 'unsafe-inline'":
                # This is expected and acceptable for CSS
                assert pattern in policy
            else:
                # These should not be present in default policy
                assert pattern not in policy, f"Unsafe directive found: {pattern}"
    
    def test_csp_https_enforcement(self):
        """Test that CSP enforces HTTPS connections."""
        config = get_config()
        policy = config.csp.build_policy()
        
        # Verify HTTPS enforcement
        assert "upgrade-insecure-requests" in policy
        
        # Verify connect-src includes https: but not http:
        assert "connect-src 'self' https:" in policy
        assert "connect-src 'self' http:" not in policy
        
        # Verify no mixed content sources
        assert "http:" not in policy  # No HTTP sources in any directive


class TestCSPIntegration:
    """Test CSP integration with Flask application (minimal setup)."""
    
    def test_csp_config_integration(self):
        """Test that CSP configuration is properly integrated into main config."""
        config = get_config()
        
        # Verify CSP config is accessible
        assert hasattr(config, 'csp')
        assert isinstance(config.csp, CSPConfig)
        
        # Verify CSP config is included in to_dict output
        config_dict = config.to_dict()
        assert 'CSP_DEFAULT_SRC' in config_dict
        assert 'CSP_SCRIPT_SRC' in config_dict
        assert 'CSP_STYLE_SRC' in config_dict
        assert 'CSP_IMG_SRC' in config_dict
        assert 'CSP_CONNECT_SRC' in config_dict
        assert 'CSP_FRAME_ANCESTORS' in config_dict
        assert 'CSP_REPORT_URI' in config_dict
        assert 'CSP_OBJECT_SRC' in config_dict
        assert 'CSP_BASE_URI' in config_dict
        assert 'CSP_UPGRADE_INSECURE_REQUESTS' in config_dict
        
        # Verify values match
        assert config_dict['CSP_DEFAULT_SRC'] == config.csp.DEFAULT_SRC
        assert config_dict['CSP_SCRIPT_SRC'] == config.csp.SCRIPT_SRC
        assert config_dict['CSP_STYLE_SRC'] == config.csp.STYLE_SRC

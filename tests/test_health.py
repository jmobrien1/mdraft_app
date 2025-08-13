"""
Tests for health endpoints.

This module tests the health check endpoints including /healthz and /readyz.
"""
import pytest
from unittest.mock import Mock, patch
from flask import Flask

from app.health import bp as health_bp


@pytest.fixture
def app():
    """Create a test Flask app."""
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_healthz_endpoint(self, client):
        """Test /healthz endpoint returns healthy status."""
        response = client.get('/healthz')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'healthy'
        assert data['service'] == 'mdraft'
        assert data['version'] == '1.0.0'
    
    def test_readyz_endpoint_all_healthy(self, client):
        """Test /readyz endpoint when all checks pass."""
        with patch('app.health.db') as mock_db, \
             patch('app.health.Storage') as mock_storage_class:
            
            # Mock database check
            mock_db.session.execute.return_value = None
            
            # Mock storage check
            mock_storage = Mock()
            mock_storage.list_prefix.return_value = []
            mock_storage_class.return_value = mock_storage
            
            response = client.get('/readyz')
            assert response.status_code == 200
            data = response.get_json()
            assert data['status'] == 'ready'
            assert data['checks']['database'] is True
            assert data['checks']['redis'] is True
            assert data['checks']['storage'] is True
    
    def test_readyz_endpoint_database_failure(self, client):
        """Test /readyz endpoint when database check fails."""
        with patch('app.health.db') as mock_db, \
             patch('app.health.Storage') as mock_storage_class:
            
            # Mock database failure
            mock_db.session.execute.side_effect = Exception("Database connection failed")
            
            # Mock storage check
            mock_storage = Mock()
            mock_storage.list_prefix.return_value = []
            mock_storage_class.return_value = mock_storage
            
            response = client.get('/readyz')
            assert response.status_code == 503
            data = response.get_json()
            assert data['status'] == 'not_ready'
            assert data['checks']['database'] is False
            assert data['checks']['redis'] is True
            assert data['checks']['storage'] is True
    
    def test_readyz_endpoint_storage_failure(self, client):
        """Test /readyz endpoint when storage check fails."""
        with patch('app.health.db') as mock_db, \
             patch('app.health.Storage') as mock_storage_class:
            
            # Mock database check
            mock_db.session.execute.return_value = None
            
            # Mock storage failure
            mock_storage = Mock()
            mock_storage.list_prefix.side_effect = Exception("Storage connection failed")
            mock_storage_class.return_value = mock_storage
            
            response = client.get('/readyz')
            assert response.status_code == 503
            data = response.get_json()
            assert data['status'] == 'not_ready'
            assert data['checks']['database'] is True
            assert data['checks']['redis'] is True
            assert data['checks']['storage'] is False
    
    def test_legacy_health_endpoint_success(self, client):
        """Test legacy /health endpoint when database is healthy."""
        with patch('app.health.db') as mock_db:
            mock_db.session.execute.return_value = None
            
            response = client.get('/health')
            assert response.status_code == 200
            data = response.get_json()
            assert data['status'] == 'ok'
    
    def test_legacy_health_endpoint_failure(self, client):
        """Test legacy /health endpoint when database fails."""
        with patch('app.health.db') as mock_db:
            mock_db.session.execute.side_effect = Exception("Database connection failed")
            
            response = client.get('/health')
            assert response.status_code == 503
            data = response.get_json()
            assert data['status'] == 'database_error'

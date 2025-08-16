"""
Tests for health endpoints.

This module tests the health check endpoints including /healthz and /readyz
with comprehensive dependency checks.
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
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
        """Test /healthz endpoint returns healthy status quickly."""
        start_time = time.time()
        response = client.get('/healthz')
        duration = time.time() - start_time
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'healthy'
        assert data['service'] == 'mdraft'
        assert data['version'] == '1.0.0'
        assert 'timestamp' in data
        assert duration < 0.1  # Should be very fast
    
    def test_readyz_endpoint_all_healthy(self, client):
        """Test /readyz endpoint when all checks pass."""
        with patch('app.health._check_database') as mock_db_check, \
             patch('app.health._check_redis') as mock_redis_check, \
             patch('app.health._check_celery') as mock_celery_check, \
             patch('app.health._check_storage') as mock_storage_check:
            
            # Mock all checks to return healthy
            mock_db_check.return_value = {
                "status": "healthy",
                "duration_ms": 15.5,
                "error": None
            }
            mock_redis_check.return_value = {
                "status": "healthy",
                "duration_ms": 8.2,
                "error": None
            }
            mock_celery_check.return_value = {
                "status": "healthy",
                "duration_ms": 45.1,
                "error": None,
                "active_workers": 2
            }
            mock_storage_check.return_value = {
                "status": "healthy",
                "duration_ms": 12.3,
                "error": None,
                "storage_type": "gcs"
            }
            
            response = client.get('/readyz')
            assert response.status_code == 200
            data = response.get_json()
            
            assert data['status'] == 'ready'
            assert data['service'] == 'mdraft'
            assert data['version'] == '1.0.0'
            assert 'timestamp' in data
            assert 'duration_ms' in data
            assert data['duration_ms'] > 0
            
            # Check individual component statuses
            assert data['checks']['database']['status'] == 'healthy'
            assert data['checks']['redis']['status'] == 'healthy'
            assert data['checks']['celery']['status'] == 'healthy'
            assert data['checks']['storage']['status'] == 'healthy'
            
            # Check additional metadata
            assert data['checks']['celery']['active_workers'] == 2
            assert data['checks']['storage']['storage_type'] == 'gcs'
    
    def test_readyz_endpoint_database_failure(self, client):
        """Test /readyz endpoint when database check fails."""
        with patch('app.health._check_database') as mock_db_check, \
             patch('app.health._check_redis') as mock_redis_check, \
             patch('app.health._check_celery') as mock_celery_check, \
             patch('app.health._check_storage') as mock_storage_check:
            
            # Mock database failure
            mock_db_check.return_value = {
                "status": "unhealthy",
                "duration_ms": 2000.0,
                "error": "Database connection failed"
            }
            
            # Mock other checks as healthy
            mock_redis_check.return_value = {
                "status": "healthy",
                "duration_ms": 8.2,
                "error": None
            }
            mock_celery_check.return_value = {
                "status": "healthy",
                "duration_ms": 45.1,
                "error": None,
                "active_workers": 1
            }
            mock_storage_check.return_value = {
                "status": "healthy",
                "duration_ms": 12.3,
                "error": None,
                "storage_type": "local"
            }
            
            response = client.get('/readyz')
            assert response.status_code == 503
            data = response.get_json()
            
            assert data['status'] == 'not_ready'
            assert data['checks']['database']['status'] == 'unhealthy'
            assert data['checks']['database']['error'] == 'Database connection failed'
            assert data['checks']['redis']['status'] == 'healthy'
            assert data['checks']['celery']['status'] == 'healthy'
            assert data['checks']['storage']['status'] == 'healthy'
            
            # Check failure details
            assert 'message' in data
            assert 'database' in data['message']
            assert 'failed_checks' in data
            assert 'database' in data['failed_checks']
    
    def test_readyz_endpoint_celery_failure(self, client):
        """Test /readyz endpoint when Celery check fails."""
        with patch('app.health._check_database') as mock_db_check, \
             patch('app.health._check_redis') as mock_redis_check, \
             patch('app.health._check_celery') as mock_celery_check, \
             patch('app.health._check_storage') as mock_storage_check:
            
            # Mock database and redis as healthy
            mock_db_check.return_value = {
                "status": "healthy",
                "duration_ms": 15.5,
                "error": None
            }
            mock_redis_check.return_value = {
                "status": "healthy",
                "duration_ms": 8.2,
                "error": None
            }
            
            # Mock Celery failure
            mock_celery_check.return_value = {
                "status": "unhealthy",
                "duration_ms": 3000.0,
                "error": "No active Celery workers found"
            }
            
            mock_storage_check.return_value = {
                "status": "healthy",
                "duration_ms": 12.3,
                "error": None,
                "storage_type": "gcs"
            }
            
            response = client.get('/readyz')
            assert response.status_code == 503
            data = response.get_json()
            
            assert data['status'] == 'not_ready'
            assert data['checks']['celery']['status'] == 'unhealthy'
            assert data['checks']['celery']['error'] == 'No active Celery workers found'
            assert 'celery' in data['failed_checks']
    
    def test_readyz_endpoint_multiple_failures(self, client):
        """Test /readyz endpoint when multiple checks fail."""
        with patch('app.health._check_database') as mock_db_check, \
             patch('app.health._check_redis') as mock_redis_check, \
             patch('app.health._check_celery') as mock_celery_check, \
             patch('app.health._check_storage') as mock_storage_check:
            
            # Mock multiple failures
            mock_db_check.return_value = {
                "status": "unhealthy",
                "duration_ms": 2000.0,
                "error": "Database connection failed"
            }
            mock_redis_check.return_value = {
                "status": "unhealthy",
                "duration_ms": 1000.0,
                "error": "Redis ping timed out"
            }
            mock_celery_check.return_value = {
                "status": "healthy",
                "duration_ms": 45.1,
                "error": None,
                "active_workers": 1
            }
            mock_storage_check.return_value = {
                "status": "unhealthy",
                "duration_ms": 2000.0,
                "error": "GCS bucket access denied"
            }
            
            response = client.get('/readyz')
            assert response.status_code == 503
            data = response.get_json()
            
            assert data['status'] == 'not_ready'
            assert len(data['failed_checks']) == 3
            assert 'database' in data['failed_checks']
            assert 'redis' in data['failed_checks']
            assert 'storage' in data['failed_checks']
            assert 'celery' not in data['failed_checks']
    
    def test_readyz_endpoint_redis_not_configured(self, client):
        """Test /readyz endpoint when Redis is not configured."""
        with patch('app.health._check_database') as mock_db_check, \
             patch('app.health._check_redis') as mock_redis_check, \
             patch('app.health._check_celery') as mock_celery_check, \
             patch('app.health._check_storage') as mock_storage_check:
            
            # Mock all checks as healthy
            mock_db_check.return_value = {
                "status": "healthy",
                "duration_ms": 15.5,
                "error": None
            }
            mock_redis_check.return_value = {
                "status": "healthy",
                "duration_ms": 0,
                "error": None,
                "note": "Redis not configured"
            }
            mock_celery_check.return_value = {
                "status": "healthy",
                "duration_ms": 45.1,
                "error": None,
                "active_workers": 1
            }
            mock_storage_check.return_value = {
                "status": "healthy",
                "duration_ms": 12.3,
                "error": None,
                "storage_type": "local"
            }
            
            response = client.get('/readyz')
            assert response.status_code == 200
            data = response.get_json()
            
            assert data['status'] == 'ready'
            assert data['checks']['redis']['note'] == 'Redis not configured'
    
    def test_readyz_endpoint_timeout_handling(self, client):
        """Test /readyz endpoint handles timeouts gracefully."""
        with patch('app.health._check_database') as mock_db_check, \
             patch('app.health._check_redis') as mock_redis_check, \
             patch('app.health._check_celery') as mock_celery_check, \
             patch('app.health._check_storage') as mock_storage_check:
            
            # Mock timeout scenarios
            mock_db_check.return_value = {
                "status": "unhealthy",
                "duration_ms": 2000.0,
                "error": "Database query timed out"
            }
            mock_redis_check.return_value = {
                "status": "healthy",
                "duration_ms": 8.2,
                "error": None
            }
            mock_celery_check.return_value = {
                "status": "unhealthy",
                "duration_ms": 3000.0,
                "error": "Celery inspect ping timed out"
            }
            mock_storage_check.return_value = {
                "status": "healthy",
                "duration_ms": 12.3,
                "error": None,
                "storage_type": "gcs"
            }
            
            response = client.get('/readyz')
            assert response.status_code == 503
            data = response.get_json()
            
            assert data['status'] == 'not_ready'
            assert 'timed out' in data['checks']['database']['error']
            assert 'timed out' in data['checks']['celery']['error']
    
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
            assert 'error' in data


class TestHealthCheckFunctions:
    """Test individual health check functions."""
    
    def test_check_database_success(self, app):
        """Test database check function with success."""
        with app.app_context():
            with patch('app.health.db') as mock_db:
                mock_db.session.execute.return_value = None
                
                from app.health import _check_database
                result = _check_database(timeout=1.0)
                
                assert result['status'] == 'healthy'
                assert result['error'] is None
                assert 'duration_ms' in result
                assert result['duration_ms'] >= 0
    
    def test_check_database_timeout(self, app):
        """Test database check function with timeout."""
        with app.app_context():
            with patch('app.health.db') as mock_db:
                # Simulate slow database response
                def slow_query(*args, **kwargs):
                    time.sleep(0.1)  # Simulate slow query
                    return None
                
                mock_db.session.execute.side_effect = slow_query
                
                from app.health import _check_database
                result = _check_database(timeout=0.05)  # Very short timeout
                
                assert result['status'] == 'unhealthy'
                assert 'timed out' in result['error']
                assert result['duration_ms'] >= 50  # Should be at least timeout duration
    
    def test_check_redis_not_configured(self, app):
        """Test Redis check when Redis is not configured."""
        with app.app_context():
            # Mock the extensions.get method directly
            with patch.object(app, 'extensions') as mock_extensions:
                mock_extensions.get.return_value = None
                
                from app.health import _check_redis
                result = _check_redis()
                
                assert result['status'] == 'healthy'
                assert result['error'] is None
                assert result['note'] == 'Redis not configured'
                assert result['duration_ms'] == 0
    
    def test_check_storage_gcs(self, app):
        """Test storage check function with GCS."""
        with app.app_context():
            with patch.object(app, 'config') as mock_config, \
                 patch('app.health.Storage') as mock_storage_class:
                
                mock_config.get.return_value = True  # USE_GCS=True
                mock_storage = Mock()
                mock_storage.list_prefix.return_value = []
                mock_storage_class.return_value = mock_storage
                
                from app.health import _check_storage
                result = _check_storage(timeout=1.0)
                
                assert result['status'] == 'healthy'
                assert result['error'] is None
                assert result['storage_type'] == 'gcs'
    
    def test_check_storage_local(self, app):
        """Test storage check function with local storage."""
        with app.app_context():
            with patch.object(app, 'config') as mock_config, \
                 patch('app.health.Storage') as mock_storage_class:
                
                mock_config.get.return_value = False  # USE_GCS=False
                mock_storage = Mock()
                mock_storage_class.return_value = mock_storage
                
                from app.health import _check_storage
                result = _check_storage(timeout=1.0)
                
                assert result['status'] == 'healthy'
                assert result['error'] is None
                assert result['storage_type'] == 'local'

"""
Tests for Celery tasks.

This module tests the Celery task functionality including queue routing
and user priority handling.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

from app.celery_tasks import is_pro_user, get_task_queue, enqueue_conversion_task


@pytest.fixture
def app():
    """Create a test Flask app."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app


class TestCeleryTasks:
    """Test Celery task functionality."""
    
    def test_is_pro_user_active_subscription(self, app):
        """Test is_pro_user returns True for active subscription."""
        with app.app_context():
            with patch('app.celery_tasks.db') as mock_db:
                mock_user = Mock()
                mock_user.subscription_status = 'active'
                mock_user.plan = 'Free'
                mock_db.session.get.return_value = mock_user
                
                result = is_pro_user(1)
                assert result is True
    
    def test_is_pro_user_pro_plan(self, app):
        """Test is_pro_user returns True for pro plan."""
        with app.app_context():
            with patch('app.celery_tasks.db') as mock_db:
                mock_user = Mock()
                mock_user.subscription_status = 'free'
                mock_user.plan = 'Pro'
                mock_db.session.get.return_value = mock_user
                
                result = is_pro_user(1)
                assert result is True
    
    def test_is_pro_user_free_user(self, app):
        """Test is_pro_user returns False for free user."""
        with app.app_context():
            with patch('app.celery_tasks.db') as mock_db:
                mock_user = Mock()
                mock_user.subscription_status = 'free'
                mock_user.plan = 'Free'
                mock_db.session.get.return_value = mock_user
                
                result = is_pro_user(1)
                assert result is False
    
    def test_is_pro_user_not_found(self, app):
        """Test is_pro_user returns False for non-existent user."""
        with app.app_context():
            with patch('app.celery_tasks.db') as mock_db:
                mock_db.session.get.return_value = None
                
                result = is_pro_user(999)
                assert result is False
    
    def test_get_task_queue_pro_user(self, app):
        """Test get_task_queue returns priority queue for pro user."""
        with app.app_context():
            with patch('app.celery_tasks.is_pro_user', return_value=True):
                result = get_task_queue(1)
                assert result == 'mdraft_priority'
    
    def test_get_task_queue_free_user(self, app):
        """Test get_task_queue returns default queue for free user."""
        with app.app_context():
            with patch('app.celery_tasks.is_pro_user', return_value=False):
                result = get_task_queue(1)
                assert result == 'mdraft_default'
    
    def test_enqueue_conversion_task_celery_mode(self, app):
        """Test enqueue_conversion_task in celery mode."""
        with app.app_context():
            with patch('app.celery_tasks.os.getenv', return_value='celery'), \
                 patch('app.celery_tasks.convert_document') as mock_convert:
                
                # Skip Celery test for now - requires complex mocking
                # This test would require a full Celery setup
                pytest.skip("Celery mode test requires full Celery setup")
    
    def test_enqueue_conversion_task_sync_mode(self, app):
        """Test enqueue_conversion_task in sync mode."""
        with app.app_context():
            with patch('app.celery_tasks.os.getenv', return_value='sync'), \
                 patch('app.celery_tasks.convert_document') as mock_convert:
                
                mock_convert.return_value = {'status': 'completed'}
                
                result = enqueue_conversion_task(1, 1, 'test/path')
                assert result == 'sync_1'
                mock_convert.assert_called_once_with(1, 1, 'test/path')

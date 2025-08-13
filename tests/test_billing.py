"""
Tests for billing functionality.

This module tests the billing blueprint including checkout, portal,
webhook handling, and configuration validation.
"""
import pytest
from unittest.mock import Mock, patch
from flask import Flask

from app.billing import is_billing_enabled, get_stripe_config


@pytest.fixture
def app():
    """Create a test Flask app."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    # Register the billing blueprint
    from app.billing import bp as billing_bp
    app.register_blueprint(billing_bp)
    
    return app


class TestBillingConfig:
    """Test billing configuration functions."""
    
    def test_is_billing_enabled_true(self):
        """Test is_billing_enabled returns True when enabled."""
        with patch('app.billing.os.getenv', return_value='1'):
            result = is_billing_enabled()
            assert result is True
    
    def test_is_billing_enabled_false(self):
        """Test is_billing_enabled returns False when disabled."""
        with patch('app.billing.os.getenv', return_value='0'):
            result = is_billing_enabled()
            assert result is False
    
    def test_is_billing_enabled_default(self):
        """Test is_billing_enabled returns False by default."""
        with patch('app.billing.os.getenv', return_value=None):
            result = is_billing_enabled()
            assert result is False
    
    def test_get_stripe_config_complete(self):
        """Test get_stripe_config returns config when all keys present."""
        with patch('app.billing.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key: {
                'STRIPE_SECRET_KEY': 'sk_test_123',
                'STRIPE_PRICE_PRO': 'price_123',
                'STRIPE_WEBHOOK_SECRET': 'whsec_123'
            }.get(key)
            
            result = get_stripe_config()
            
            assert result is not None
            assert result['secret_key'] == 'sk_test_123'
            assert result['price_pro'] == 'price_123'
            assert result['webhook_secret'] == 'whsec_123'
    
    def test_get_stripe_config_missing_keys(self):
        """Test get_stripe_config returns None when keys missing."""
        with patch('app.billing.os.getenv', return_value=None):
            result = get_stripe_config()
            assert result is None
    
    def test_get_stripe_config_partial_keys(self):
        """Test get_stripe_config returns None when some keys missing."""
        with patch('app.billing.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda key: {
                'STRIPE_SECRET_KEY': 'sk_test_123',
                'STRIPE_PRICE_PRO': None,  # Missing
                'STRIPE_WEBHOOK_SECRET': 'whsec_123'
            }.get(key)
            
            result = get_stripe_config()
            assert result is None


class TestBillingRoutes:
    """Test billing route endpoints."""
    
    def test_checkout_billing_disabled(self, app):
        """Test checkout returns 503 when billing disabled."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=False):
                response = client.post('/billing/checkout', json={'user_id': 1})
                
                assert response.status_code == 503
                data = response.get_json()
                assert data['error'] == 'billing_disabled'
                assert 'not enabled' in data['message']
    
    def test_checkout_stripe_not_configured(self, app):
        """Test checkout returns 503 when Stripe not configured."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=True), \
                 patch('app.billing.get_stripe_config', return_value=None):
                response = client.post('/billing/checkout', json={'user_id': 1})
                
                assert response.status_code == 503
                data = response.get_json()
                assert data['error'] == 'stripe_not_configured'
                assert 'incomplete' in data['message']
    
    def test_checkout_missing_user_id(self, app):
        """Test checkout returns 400 when user_id missing."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=True), \
                 patch('app.billing.get_stripe_config', return_value={'secret_key': 'test'}):
                response = client.post('/billing/checkout', json={})
                
                assert response.status_code == 400
                data = response.get_json()
                assert data['error'] == 'user_required'
    
    def test_checkout_success_placeholder(self, app):
        """Test checkout returns placeholder response when implemented."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=True), \
                 patch('app.billing.get_stripe_config', return_value={'secret_key': 'test'}):
                response = client.post('/billing/checkout', json={'user_id': 1})
                
                assert response.status_code == 501
                data = response.get_json()
                assert data['error'] == 'not_implemented'
                assert 'not yet implemented' in data['message']
    
    def test_portal_billing_disabled(self, app):
        """Test portal returns 503 when billing disabled."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=False):
                response = client.get('/billing/portal?user_id=1')
                
                assert response.status_code == 503
                data = response.get_json()
                assert data['error'] == 'billing_disabled'
    
    def test_portal_missing_user_id(self, app):
        """Test portal returns 400 when user_id missing."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=True), \
                 patch('app.billing.get_stripe_config', return_value={'secret_key': 'test'}):
                response = client.get('/billing/portal')
                
                assert response.status_code == 400
                data = response.get_json()
                assert data['error'] == 'user_required'
    
    def test_webhook_billing_disabled(self, app):
        """Test webhook returns 503 when billing disabled."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=False):
                response = client.post('/billing/webhook', json={})
                
                assert response.status_code == 503
                data = response.get_json()
                assert data['error'] == 'billing_disabled'
    
    def test_webhook_success_placeholder(self, app):
        """Test webhook returns success response."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=True), \
                 patch('app.billing.get_stripe_config', return_value={'secret_key': 'test'}):
                response = client.post('/billing/webhook', json={})
                
                assert response.status_code == 200
                data = response.get_json()
                assert data['status'] == 'received'
    
    def test_status_billing_disabled(self, app):
        """Test status endpoint when billing disabled."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=False), \
                 patch('app.billing.get_stripe_config', return_value=None):
                response = client.get('/billing/status')
                
                assert response.status_code == 200
                data = response.get_json()
                assert data['billing_enabled'] is False
                assert data['stripe_configured'] is False
                assert len(data['missing_keys']) == 3
    
    def test_status_billing_enabled_configured(self, app):
        """Test status endpoint when billing enabled and configured."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=True), \
                 patch('app.billing.get_stripe_config', return_value={'secret_key': 'test'}):
                response = client.get('/billing/status')
                
                assert response.status_code == 200
                data = response.get_json()
                assert data['billing_enabled'] is True
                assert data['stripe_configured'] is True
                assert len(data['missing_keys']) == 0
    
    def test_status_billing_enabled_not_configured(self, app):
        """Test status endpoint when billing enabled but not configured."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=True), \
                 patch('app.billing.get_stripe_config', return_value=None):
                response = client.get('/billing/status')
                
                assert response.status_code == 200
                data = response.get_json()
                assert data['billing_enabled'] is True
                assert data['stripe_configured'] is False
                assert len(data['missing_keys']) == 3


class TestBillingIntegration:
    """Test billing integration scenarios."""
    
    def test_checkout_flow_disabled(self, app):
        """Test complete checkout flow when billing disabled."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=False):
                response = client.post('/billing/checkout', json={'user_id': 1})
                
                assert response.status_code == 503
                data = response.get_json()
                assert data['error'] == 'billing_disabled'
    
    def test_portal_flow_disabled(self, app):
        """Test complete portal flow when billing disabled."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=False):
                response = client.get('/billing/portal?user_id=1')
                
                assert response.status_code == 503
                data = response.get_json()
                assert data['error'] == 'billing_disabled'
    
    def test_webhook_flow_disabled(self, app):
        """Test complete webhook flow when billing disabled."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=False):
                response = client.post('/billing/webhook', json={'type': 'test'})
                
                assert response.status_code == 503
                data = response.get_json()
                assert data['error'] == 'billing_disabled'
    
    def test_status_flow_complete(self, app):
        """Test status endpoint provides complete configuration info."""
        with app.test_client() as client:
            with patch('app.billing.is_billing_enabled', return_value=True), \
                 patch('app.billing.get_stripe_config', return_value=None):
                response = client.get('/billing/status')
                
                assert response.status_code == 200
                data = response.get_json()
                assert 'billing_enabled' in data
                assert 'stripe_configured' in data
                assert 'missing_keys' in data
                assert isinstance(data['missing_keys'], list)

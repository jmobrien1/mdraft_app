import pytest
import os
from flask import Flask

@pytest.fixture
def app():
    """Create a test Flask app with all blueprints."""
    # Set up test environment
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ['SECRET_KEY'] = 'test-secret-key'
    
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()

def test_health_simple(client):
    r = client.get("/health/simple")
    assert r.status_code == 200

def test_health_full(client):
    r = client.get("/health/full")
    assert r.status_code in (200, 503)

def test_root_does_not_500(client):
    r = client.get("/")
    assert r.status_code in (200, 302, 401, 403)

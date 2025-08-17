"""
Test homepage route determinism.

This module tests that:
1. Only one route handles "/"
2. The homepage returns expected content
3. Any redirects work correctly
"""
import pytest
from flask import Flask
from unittest.mock import patch, MagicMock

# Import the blueprints directly
from app.ui import bp as ui_bp
from app.routes import bp as main_bp


@pytest.fixture
def app():
    """Create a minimal test Flask app with just the UI and main blueprints."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    # Register blueprints in the same order as the main app
    app.register_blueprint(ui_bp)
    app.register_blueprint(main_bp)
    
    return app


def test_only_one_root_route(app):
    """Test that only one route handles the root path "/"."""
    # Count routes that handle "/"
    root_routes = [r for r in app.url_map.iter_rules() if r.rule == "/"]
    
    assert len(root_routes) == 1, f"Expected exactly 1 route for '/', found {len(root_routes)}: {root_routes}"


@patch('app.ui.render_template')
def test_homepage_returns_200(mock_render, app):
    """Test that GET / returns 200 and expected content."""
    mock_render.return_value = "<html><head></head><body>Test Homepage</body></html>"
    
    with app.test_client() as client:
        response = client.get("/")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # The UI route should render the index.html template
        # Check that it's an HTML response
        assert "text/html" in response.headers.get("Content-Type", ""), "Expected HTML response"
        
        # Check that the response contains expected content
        html_content = response.get_data(as_text=True)
        assert "html" in html_content.lower(), "Expected HTML content"


@patch('app.ui.render_template')
def test_homepage_content_structure(mock_render, app):
    """Test that the homepage has the expected structure."""
    mock_render.return_value = "<!DOCTYPE html><html><head></head><body>Test Homepage</body></html>"
    
    with app.test_client() as client:
        response = client.get("/")
        
        assert response.status_code == 200
        html_content = response.get_data(as_text=True)
        
        # Basic HTML structure checks
        assert "<!DOCTYPE html>" in html_content or "<html" in html_content
        assert "<head>" in html_content
        assert "<body>" in html_content


def test_no_conflicting_blueprint_routes(app):
    """Test that blueprints don't have conflicting url_prefix + "/" combinations."""
    # Get all blueprints
    blueprints = list(app.blueprints.values())
    
    # Check for any blueprints with url_prefix="/" that also have a "/" route
    conflicting_blueprints = []
    
    for bp in blueprints:
        if bp.url_prefix == "/":
            # This blueprint has url_prefix="/", so it shouldn't have a "/" route
            for rule in bp.deferred_functions:
                if hasattr(rule, 'rule') and rule.rule == "/":
                    conflicting_blueprints.append(bp.name)
    
    assert len(conflicting_blueprints) == 0, f"Found blueprints with conflicting url_prefix='/': {conflicting_blueprints}"


def test_home_endpoint_accessible(app):
    """Test that the /home endpoint is accessible and returns JSON."""
    with app.test_client() as client:
        response = client.get("/home")
        
        # /home should return 200 with JSON response
        assert response.status_code == 200
        assert "application/json" in response.headers.get("Content-Type", "")
        
        # Should contain the JSON response from main route
        json_content = response.get_json()
        assert json_content["status"] == "ok"
        assert json_content["message"] == "Welcome to mdraft!"


def test_homepage_route_registration_order(app):
    """Test that the UI route takes precedence over the main route."""
    # Get the route that handles "/"
    root_routes = [r for r in app.url_map.iter_rules() if r.rule == "/"]
    assert len(root_routes) == 1
    
    root_route = root_routes[0]
    
    # The route should be from the UI blueprint, not the main blueprint
    # Flask route endpoints are typically in format "blueprint_name.function_name"
    assert root_route.endpoint.startswith("ui."), f"Expected UI route, got {root_route.endpoint}"


@patch('app.ui.render_template')
def test_main_route_not_accessible(mock_render):
    """Test that the main route's "/" is not accessible when UI route is registered first."""
    mock_render.return_value = "<html><head></head><body>Test Homepage</body></html>"
    
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    # Register blueprints in the same order as the main app
    app.register_blueprint(ui_bp)
    app.register_blueprint(main_bp)
    
    with app.test_client() as client:
        response = client.get("/")
        
        # Should get the UI route (HTML), not the main route (JSON)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", "")
        
        # Should not contain the JSON response from main route
        html_content = response.get_data(as_text=True)
        assert '"status": "ok"' not in html_content
        assert '"message": "Welcome to mdraft!"' not in html_content


def test_homepage_route_deterministic():
    """Test that the homepage route is deterministic - only one route handles "/"."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    # Register blueprints in the same order as the main app
    app.register_blueprint(ui_bp)
    app.register_blueprint(main_bp)
    
    # Count routes that handle "/"
    root_routes = [r for r in app.url_map.iter_rules() if r.rule == "/"]
    
    assert len(root_routes) == 1, f"Expected exactly 1 route for '/', found {len(root_routes)}: {root_routes}"
    
    # Verify it's the UI route
    root_route = root_routes[0]
    assert root_route.endpoint == "ui.index", f"Expected ui.index, got {root_route.endpoint}"

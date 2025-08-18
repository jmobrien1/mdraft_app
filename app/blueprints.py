"""
Centralized blueprint registration for mdraft.

This module provides a canonical way to register all Flask blueprints
in the application. It imports all blueprints and registers them with
the Flask app in a consistent order.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from flask import Flask

logger = logging.getLogger(__name__)


def register_blueprints(app: Flask) -> List[str]:
    """Register all blueprints with the Flask application.
    
    Args:
        app: The Flask application instance
        
    Returns:
        List of blueprint registration errors (empty if all successful)
    """
    blueprint_errors = []
    
    # Define all blueprints with their import paths and registration info
    blueprints = [
        # Core blueprints (always register first)
        ("app.auth.routes", "bp", "auth_bp"),
        ("app.ui", "bp", "ui_bp"),
        ("app.health", "bp", "health_bp"),
        
        # API blueprints (register in order of specificity)
        ("app.api_estimate", "bp", "estimate_api_bp"),
        ("app.api_convert", "bp", "api_convert_bp"),
        ("app.api_usage", "bp", "usage_api_bp"),
        ("app.api_queue", "bp", "api_queue_bp"),
        ("app.api.agents", "bp", "agents_bp"),
        ("app.api.ops", "bp", "ops_bp"),
        ("app.api.errors", "errors", "errors_bp"),
        
        # Feature blueprints
        ("app.beta", "bp", "beta_bp"),
        ("app.billing", "bp", "billing_bp"),
        ("app.admin", "bp", "admin_bp"),
        ("app.view", "bp", "view_bp"),
        
        # Main routes blueprint (register last to avoid conflicts)
        ("app.routes", "bp", "main_bp"),
    ]
    
    # Register each blueprint with error handling
    for module_path, blueprint_var, blueprint_name in blueprints:
        try:
            # Import the module and get the blueprint
            module = __import__(module_path, fromlist=[blueprint_var])
            blueprint = getattr(module, blueprint_var)
            
            # Register the blueprint
            app.register_blueprint(blueprint)
            
            # Exempt API blueprints from CSRF protection
            if module_path.startswith("app.api") or "api" in module_path:
                try:
                    from app.extensions import csrf
                    csrf.exempt(blueprint)
                    logger.info(f"{blueprint_name} blueprint exempted from CSRF protection")
                except Exception as e:
                    logger.warning(f"Failed to exempt {blueprint_name} from CSRF: {e}")
            
            logger.info(f"{blueprint_name} blueprint registered from {module_path}")
            
        except Exception as e:
            error_msg = f"{blueprint_name} blueprint ({module_path}): {e}"
            blueprint_errors.append(error_msg)
            logger.warning(f"Failed to register {error_msg}")
    
    # Log summary
    if blueprint_errors:
        logger.warning(f"Blueprint registration errors: {blueprint_errors}")
    else:
        logger.info("All blueprints registered successfully")
    
    return blueprint_errors


def get_blueprint_info() -> List[Tuple[str, str, str]]:
    """Get information about all available blueprints.
    
    Returns:
        List of tuples: (blueprint_name, module_path, url_prefix)
    """
    return [
        # Core blueprints
        ("auth", "app.auth.routes", "/auth"),
        ("ui", "app.ui", ""),
        ("health", "app.health", ""),
        
        # API blueprints
        ("estimate_api", "app.api_estimate", "/api"),
        ("api_convert", "app.api_convert", "/api"),
        ("usage_api", "app.api_usage", "/api"),
        ("api_queue", "app.api_queue", "/api/queue"),
        ("agents", "app.api.agents", "/api/agents"),
        ("ops", "app.api.ops", "/api/ops"),
        ("errors", "app.api.errors", ""),
        
        # Feature blueprints
        ("beta", "app.beta", ""),
        ("billing", "app.billing", "/billing"),
        ("admin", "app.admin", "/admin"),
        ("view", "app.view", "/v"),
        
        # Main routes
        ("main", "app.routes", ""),
    ]

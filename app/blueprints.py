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

    def _try(label: str, import_path: str, attr: str, url_prefix: str = None) -> bool:
        """Try to register a blueprint, log errors but don't fail the app.
        
        Args:
            label: Human-readable label for logging
            import_path: Module path to import
            attr: Attribute name containing the blueprint
            url_prefix: Optional URL prefix override
            
        Returns:
            True if registration succeeded, False otherwise
        """
        try:
            mod = __import__(import_path, fromlist=[attr])
            bp = getattr(mod, attr)
            
            # Allow overriding prefix when needed
            if url_prefix and not getattr(bp, 'url_prefix', None):
                from flask import Blueprint
                bp = Blueprint(bp.name, bp.import_name, url_prefix=url_prefix)
            
            app.register_blueprint(bp)
            
            # Exempt API blueprints from CSRF protection
            if import_path.startswith("app.api") or "api" in import_path:
                try:
                    from app.extensions import csrf
                    csrf.exempt(bp)
                    logger.info(f"{label} blueprint exempted from CSRF protection")
                except Exception as e:
                    logger.warning(f"Failed to exempt {label} from CSRF: {e}")
            
            logger.info(f"Registered blueprint: {label} ({import_path}.{attr})")
            return True
            
        except Exception as e:
            msg = f"Failed to register {label} ({import_path}): {e}"
            logger.warning(msg)
            blueprint_errors.append(msg)
            return False

    # Core blueprints (always register first - these should never fail)
    logger.info("Registering core blueprints...")
    _try("auth_bp", "app.auth.routes", "bp")
    _try("ui_bp", "app.ui", "bp")
    _try("health_bp", "app.health", "bp")
    
    # API blueprints (optional - don't fail if missing)
    logger.info("Registering API blueprints...")
    _try("estimate_api_bp", "app.api_estimate", "bp")      # exposes /api/estimate
    _try("api_convert_bp", "app.api_convert", "bp")        # exposes /api/convert
    _try("usage_api_bp", "app.api_usage", "bp")            # exposes /api/me/usage
    _try("api_queue_bp", "app.api_queue", "bp")            # exposes /api/queue/*
    _try("agents_bp", "app.api.agents", "bp")              # OpenAI-based features
    _try("ops_bp", "app.api.ops", "bp")                    # operations endpoints
    _try("errors_bp", "app.api.errors", "errors")          # error handlers
    
    # Feature blueprints (optional - don't fail if missing)
    logger.info("Registering feature blueprints...")
    _try("beta_bp", "app.beta", "bp")                      # beta features
    _try("billing_bp", "app.billing", "bp")                # billing endpoints
    _try("admin_bp", "app.admin", "bp")                    # admin interface
    _try("view_bp", "app.view", "bp")                      # document viewing
    
    # Main routes blueprint (register last to avoid conflicts)
    logger.info("Registering main routes...")
    _try("main_bp", "app.routes", "bp")                    # main application routes

    # Log summary
    if blueprint_errors:
        logger.warning(f"Blueprint registration errors: {blueprint_errors}")
        logger.info(f"App will continue with {len(blueprint_errors)} blueprint(s) disabled")
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

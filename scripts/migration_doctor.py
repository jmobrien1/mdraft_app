#!/usr/bin/env python3
"""
Migration Doctor for mdraft application.

This script diagnoses and fixes common database migration issues:
- Missing migrations
- Inconsistent migration state
- Database connectivity issues
- Schema validation problems
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_database_connectivity() -> bool:
    """Check if we can connect to the database."""
    try:
        from sqlalchemy import create_engine, text
        
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            logger.error("DATABASE_URL not set")
            return False
        
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        logger.info("Database connectivity: OK")
        return True
        
    except Exception as e:
        logger.error(f"Database connectivity failed: {e}")
        return False


def check_migration_state() -> Dict[str, Any]:
    """Check the current migration state."""
    try:
        from flask import Flask
        from flask_migrate import Migrate
        from flask_sqlalchemy import SQLAlchemy
        
        # Create a minimal app for migration checking
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        db = SQLAlchemy(app)
        migrate = Migrate(app, db)
        
        with app.app_context():
            from alembic import command
            from alembic.config import Config
            
            # Get Alembic config
            alembic_cfg = Config("alembic.ini")
            
            # Check current revision
            try:
                from alembic.script import ScriptDirectory
                script_dir = ScriptDirectory.from_config(alembic_cfg)
                current = command.current(alembic_cfg)
                logger.info(f"Current migration: {current}")
                
                # Get all available revisions
                revisions = list(script_dir.walk_revisions())
                latest_revision = revisions[-1].revision if revisions else None
                
                return {
                    'current': current,
                    'latest': latest_revision,
                    'total_migrations': len(revisions),
                    'status': 'ok'
                }
                
            except Exception as e:
                logger.error(f"Failed to check migration state: {e}")
                return {
                    'current': None,
                    'latest': None,
                    'total_migrations': 0,
                    'status': 'error',
                    'error': str(e)
                }
                
    except Exception as e:
        logger.error(f"Migration state check failed: {e}")
        return {
            'current': None,
            'latest': None,
            'total_migrations': 0,
            'status': 'error',
            'error': str(e)
        }


def check_schema_consistency() -> Dict[str, Any]:
    """Check if the database schema matches expectations."""
    try:
        from sqlalchemy import create_engine, text, inspect
        
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            return {'status': 'error', 'error': 'DATABASE_URL not set'}
        
        engine = create_engine(db_url)
        inspector = inspect(engine)
        
        # Check for required tables
        required_tables = ['proposals', 'conversions', 'users', 'api_keys']
        existing_tables = inspector.get_table_names()
        
        missing_tables = [table for table in required_tables if table not in existing_tables]
        
        # Check for required columns in proposals table
        schema_issues = []
        if 'proposals' in existing_tables:
            columns = [col['name'] for col in inspector.get_columns('proposals')]
            required_columns = ['id', 'title', 'created_at', 'visitor_session_id']
            missing_columns = [col for col in required_columns if col not in columns]
            
            if missing_columns:
                schema_issues.append(f"Missing columns in proposals table: {missing_columns}")
        
        return {
            'status': 'ok' if not missing_tables and not schema_issues else 'issues',
            'missing_tables': missing_tables,
            'schema_issues': schema_issues,
            'existing_tables': existing_tables
        }
        
    except Exception as e:
        logger.error(f"Schema consistency check failed: {e}")
        return {'status': 'error', 'error': str(e)}


def run_migrations() -> bool:
    """Run pending migrations."""
    try:
        from flask import Flask
        from flask_migrate import Migrate
        from flask_sqlalchemy import SQLAlchemy
        
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        db = SQLAlchemy(app)
        migrate = Migrate(app, db)
        
        with app.app_context():
            from alembic import command
            from alembic.config import Config
            
            alembic_cfg = Config("alembic.ini")
            
            # Check if there are pending migrations
            try:
                command.upgrade(alembic_cfg, "head")
                logger.info("Migrations applied successfully")
                return True
            except Exception as e:
                logger.error(f"Migration failed: {e}")
                return False
                
    except Exception as e:
        logger.error(f"Failed to run migrations: {e}")
        return False


def create_missing_tables() -> bool:
    """Create missing tables if migrations are not available."""
    try:
        from app import create_app, db
        
        app = create_app()
        
        with app.app_context():
            # Create all tables
            db.create_all()
            logger.info("Missing tables created successfully")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        return False


def main():
    """Main migration doctor function."""
    parser = argparse.ArgumentParser(description='Migration Doctor for mdraft')
    parser.add_argument('--fix', action='store_true', help='Attempt to fix issues')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("=== MIGRATION DOCTOR STARTED ===")
    logger.info(f"Timestamp: {datetime.now()}")
    
    # Check database connectivity
    logger.info("1. Checking database connectivity...")
    if not check_database_connectivity():
        logger.error("❌ Database connectivity failed")
        if args.fix:
            logger.info("Cannot fix connectivity issues automatically")
        return 1
    
    logger.info("✅ Database connectivity: OK")
    
    # Check migration state
    logger.info("2. Checking migration state...")
    migration_state = check_migration_state()
    
    if migration_state['status'] == 'error':
        logger.error(f"❌ Migration state check failed: {migration_state.get('error')}")
        if args.fix:
            logger.info("Attempting to create missing tables...")
            if create_missing_tables():
                logger.info("✅ Tables created successfully")
            else:
                logger.error("❌ Failed to create tables")
                return 1
    else:
        current = migration_state.get('current', 'unknown')
        latest = migration_state.get('latest', 'unknown')
        
        if current == latest:
            logger.info(f"✅ Migration state: OK (current: {current})")
        else:
            logger.warning(f"⚠️  Migration state: Outdated (current: {current}, latest: {latest})")
            if args.fix:
                logger.info("Running pending migrations...")
                if run_migrations():
                    logger.info("✅ Migrations applied successfully")
                else:
                    logger.error("❌ Failed to apply migrations")
                    return 1
    
    # Check schema consistency
    logger.info("3. Checking schema consistency...")
    schema_check = check_schema_consistency()
    
    if schema_check['status'] == 'error':
        logger.error(f"❌ Schema check failed: {schema_check.get('error')}")
    elif schema_check['status'] == 'issues':
        missing_tables = schema_check.get('missing_tables', [])
        schema_issues = schema_check.get('schema_issues', [])
        
        if missing_tables:
            logger.warning(f"⚠️  Missing tables: {missing_tables}")
        if schema_issues:
            logger.warning(f"⚠️  Schema issues: {schema_issues}")
        
        if args.fix and (missing_tables or schema_issues):
            logger.info("Attempting to fix schema issues...")
            if create_missing_tables():
                logger.info("✅ Schema issues resolved")
            else:
                logger.error("❌ Failed to resolve schema issues")
                return 1
    else:
        logger.info("✅ Schema consistency: OK")
    
    # Final validation
    logger.info("4. Final validation...")
    if check_database_connectivity():
        logger.info("✅ Final connectivity check: OK")
    else:
        logger.error("❌ Final connectivity check failed")
        return 1
    
    logger.info("=== MIGRATION DOCTOR COMPLETED SUCCESSFULLY ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

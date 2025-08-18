#!/usr/bin/env python3
"""
Standalone script to run database migration safely after deployment.
This script can be run manually to add the missing email_verified column.
"""

import os
import sys
import logging
from sqlalchemy import text, inspect
from sqlalchemy.exc import ProgrammingError

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def check_column_exists(engine, table_name, column_name):
    """Check if a column exists in a table."""
    try:
        inspector = inspect(engine)
        columns = inspector.get_columns(table_name)
        column_names = [col['name'] for col in columns]
        return column_name in column_names
    except Exception as e:
        logger.error(f"Error checking columns: {e}")
        return False

def add_email_verified_column(engine):
    """Add email_verified column to users table if it doesn't exist."""
    try:
        # Check if column already exists
        if check_column_exists(engine, 'users', 'email_verified'):
            logger.info("Column 'email_verified' already exists in users table")
            return True
        
        logger.info("Column 'email_verified' does not exist. Adding it...")
        
        # Add the column
        with engine.connect() as conn:
            # For PostgreSQL
            if engine.dialect.name == 'postgresql':
                sql = """
                ALTER TABLE users 
                ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT false;
                """
            # For SQLite
            elif engine.dialect.name == 'sqlite':
                sql = """
                ALTER TABLE users 
                ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 0;
                """
            else:
                logger.error(f"Unsupported database dialect: {engine.dialect.name}")
                return False
            
            conn.execute(text(sql))
            conn.commit()
            
        logger.info("Successfully added 'email_verified' column to users table")
        return True
        
    except Exception as e:
        logger.error(f"Error adding email_verified column: {e}")
        return False

def main():
    """Main function to run the migration."""
    logger.info("=== Starting Post-Deploy Migration ===")
    
    try:
        # Import after setting up the path
        from app import create_app
        from app.extensions import db
        
        # Create app context
        app = create_app()
        
        with app.app_context():
            logger.info("Connected to database successfully")
            
            # Get the engine
            engine = db.engine
            logger.info(f"Database dialect: {engine.dialect.name}")
            
            # Run the migration
            success = add_email_verified_column(engine)
            
            if success:
                logger.info("=== Migration completed successfully ===")
                return 0
            else:
                logger.error("=== Migration failed ===")
                return 1
                
    except Exception as e:
        logger.error(f"Fatal error during migration: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

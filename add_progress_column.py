#!/usr/bin/env python3
"""
Safely add progress column to conversions table.

This script can be run in production to fix the schema drift
without requiring complex migration resolution.
"""
import os
import sys

# Set minimal environment variables
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('SECRET_KEY', 'debug-secret-key')

def add_progress_column():
    """Add progress column to conversions table if it doesn't exist."""
    try:
        from app import create_app, db
        from sqlalchemy import text
        
        app = create_app()
        
        with app.app_context():
            # Check if progress column exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'conversions' 
                AND column_name = 'progress'
            """))
            
            column_exists = result.fetchone() is not None
            
            if column_exists:
                print("✅ Progress column already exists in conversions table")
                return True
            else:
                # Add the column
                db.session.execute(text("""
                    ALTER TABLE conversions 
                    ADD COLUMN progress INTEGER
                """))
                db.session.commit()
                print("✅ Successfully added progress column to conversions table")
                return True
                
    except Exception as e:
        print(f"❌ Error adding progress column: {e}")
        return False

if __name__ == "__main__":
    success = add_progress_column()
    sys.exit(0 if success else 1)

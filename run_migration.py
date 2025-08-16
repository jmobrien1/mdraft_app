#!/usr/bin/env python3
"""
Script to run the progress field migration manually.
"""

import os
import sys

# Set up environment
os.environ['DATABASE_URL'] = 'sqlite:///mdraft_local.db'
os.environ['FLASK_APP'] = 'run.py'

# Import Flask app
from app import create_app, db

def run_migration():
    """Run the migration to add the progress field."""
    app = create_app()
    
    with app.app_context():
        # Create the progress column manually
        try:
            db.engine.execute("ALTER TABLE conversions ADD COLUMN progress INTEGER")
            print("✅ Successfully added progress column to conversions table")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️  Progress column already exists")
            else:
                print(f"❌ Error adding progress column: {e}")
                return False
        
        return True

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)

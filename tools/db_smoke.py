#!/usr/bin/env python3
"""
Database smoke test - connects to database and runs a simple query.
Reads DATABASE_URL from environment or SQLALCHEMY_DATABASE_URI from Flask config.
"""

import os, sys
try:
    from app.utils.db_url import normalize_db_url  # absolute when repo root is on PYTHONPATH
except ModuleNotFoundError:
    # Add project root to sys.path when invoked directly
    root = os.path.dirname(os.path.dirname(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    from app.utils.db_url import normalize_db_url

from datetime import datetime

def main():
    # Get database URL from environment or Flask config
    database_url = os.environ.get("DATABASE_URL")
    
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    try:
        # Import SQLAlchemy components and normalize URL
        from sqlalchemy import create_engine, text
        from app.utils.db_url import normalize_db_url
        
        # Normalize URL and create engine
        normalized_url = normalize_db_url(database_url)
        engine = create_engine(normalized_url)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT now()"))
            timestamp = result.scalar()
            print(f"SUCCESS: Database connection working, current time: {timestamp}")
            
    except Exception as e:
        print(f"ERROR: Database connection failed: {e}")
        sys.exit(1)
    
    sys.exit(0)

if __name__ == "__main__":
    main()

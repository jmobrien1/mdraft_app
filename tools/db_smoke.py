#!/usr/bin/env python3
"""
Database smoke test - connects to database and runs a simple query.
Reads DATABASE_URL from environment or SQLALCHEMY_DATABASE_URI from Flask config.
"""

import os
import sys
from datetime import datetime

def main():
    # Get database URL from environment or Flask config
    database_url = os.environ.get("DATABASE_URL")
    
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    try:
        # Import SQLAlchemy components
        from sqlalchemy import create_engine, text
        
        # Create engine and test connection
        engine = create_engine(database_url)
        
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

#!/usr/bin/env python3
"""
Database smoke test.

Reads SQLALCHEMY_DATABASE_URI or DATABASE_URL, creates an engine,
runs SELECT now(), prints the timestamp or a clear error, and exits 0.
"""
import os
import sys
from sqlalchemy import create_engine, text


def main():
    """Run database smoke test."""
    # Get database URI from environment
    db_uri = os.getenv("SQLALCHEMY_DATABASE_URI") or os.getenv("DATABASE_URL")
    
    if not db_uri:
        print("ERROR: No database URI found in SQLALCHEMY_DATABASE_URI or DATABASE_URL")
        sys.exit(0)
    
    try:
        # Create engine
        engine = create_engine(db_uri)
        
        # Test connection with SELECT now()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT now()"))
            timestamp = result.scalar()
            print(f"SUCCESS: Database connection working, current time: {timestamp}")
            
    except Exception as e:
        print(f"ERROR: Database connection failed: {e}")
    
    sys.exit(0)


if __name__ == "__main__":
    main()

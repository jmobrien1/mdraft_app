#!/usr/bin/env python3
"""
Database Connection Test Script

This script tests database connectivity to identify the specific issue
causing the "unhealthy" database status in the health check.
"""

import os
import sys
import psycopg2
from urllib.parse import urlparse

def test_database_connection():
    """Test database connection and identify issues."""
    print("=== Database Connection Test ===")
    
    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        return False
    
    print(f"Database URL: {database_url[:20]}...")
    
    try:
        # Parse the URL
        parsed = urlparse(database_url)
        print(f"Host: {parsed.hostname}")
        print(f"Port: {parsed.port}")
        print(f"Database: {parsed.path[1:]}")
        print(f"User: {parsed.username}")
        
        # Test direct connection
        print("\nTesting direct psycopg2 connection...")
        conn = psycopg2.connect(database_url)
        
        # Test simple query
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        print(f"✅ Direct connection successful: {result}")
        
        # Test database version
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"✅ Database version: {version.split()[1]}")
        
        # Test if tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        print(f"✅ Found {len(tables)} tables:")
        for table in tables[:5]:  # Show first 5 tables
            print(f"   - {table[0]}")
        if len(tables) > 5:
            print(f"   ... and {len(tables) - 5} more")
        
        cursor.close()
        conn.close()
        print("✅ Database connection test PASSED")
        return True
        
    except psycopg2.OperationalError as e:
        print(f"❌ Database connection failed: {e}")
        print("\nPossible causes:")
        print("1. Database server is down")
        print("2. Network connectivity issues")
        print("3. Incorrect DATABASE_URL")
        print("4. Firewall blocking connection")
        print("5. Database credentials are incorrect")
        return False
        
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_sqlalchemy_connection():
    """Test SQLAlchemy connection (what the app uses)."""
    print("\n=== SQLAlchemy Connection Test ===")
    
    try:
        from app import create_app
        from app.extensions import db
        
        app = create_app()
        with app.app_context():
            # Test SQLAlchemy connection
            result = db.session.execute("SELECT 1").fetchone()
            print(f"✅ SQLAlchemy connection successful: {result}")
            
            # Test if we can access models
            from app.models import User
            print("✅ Models accessible")
            
            return True
            
    except Exception as e:
        print(f"❌ SQLAlchemy connection failed: {e}")
        return False

def main():
    """Main test function."""
    print("Database Connection Diagnostic")
    print("=" * 40)
    
    # Test direct connection
    direct_success = test_database_connection()
    
    # Test SQLAlchemy connection
    sqlalchemy_success = test_sqlalchemy_connection()
    
    # Summary
    print("\n=== Summary ===")
    if direct_success and sqlalchemy_success:
        print("✅ All database tests PASSED")
        print("The database connection should be working.")
        print("Check if there are other issues in the application.")
        return True
    elif direct_success and not sqlalchemy_success:
        print("⚠️  Direct connection works but SQLAlchemy fails")
        print("This suggests a configuration issue in the Flask app.")
        return False
    else:
        print("❌ Database connection FAILED")
        print("This is the root cause of the 'internal server error'.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

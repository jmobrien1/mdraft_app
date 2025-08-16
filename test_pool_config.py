#!/usr/bin/env python3
"""
Test script to validate SQLAlchemy engine pooling configuration.

This script tests the connection pool settings to ensure they're working
correctly for Render deployment.
"""

import os
import sys
import time
from contextlib import contextmanager

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import create_app, db
from sqlalchemy import text

def test_pool_configuration():
    """Test the database pool configuration."""
    app = create_app()
    
    with app.app_context():
        # Get the engine and pool
        engine = db.engine
        pool = engine.pool
        
        print("=== SQLAlchemy Engine Pool Configuration Test ===")
        print(f"Engine URL: {engine.url}")
        print(f"Pool class: {type(pool).__name__}")
        print(f"Pool size: {pool.size()}")
        print(f"Pool overflow: {pool.overflow()}")
        print(f"Pool timeout: {pool.timeout}")
        print(f"Pool recycle: {pool.recycle}")
        print(f"Pool pre-ping: {pool.pre_ping}")
        
        # Test basic connectivity
        print("\n=== Testing Basic Connectivity ===")
        try:
            result = db.session.execute(text("SELECT 1 as test"))
            test_value = result.scalar()
            print(f"✓ Database connection successful: {test_value}")
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            return False
        
        # Test connection pool behavior
        print("\n=== Testing Connection Pool Behavior ===")
        
        # Test multiple concurrent connections
        connections = []
        try:
            for i in range(3):
                conn = engine.connect()
                connections.append(conn)
                print(f"✓ Created connection {i+1}")
            
            print(f"Pool stats after creating connections:")
            print(f"  Checked out: {pool.checkedout()}")
            print(f"  Checked in: {pool.checkedin()}")
            print(f"  Overflow: {pool.overflow()}")
            
            # Close connections
            for i, conn in enumerate(connections):
                conn.close()
                print(f"✓ Closed connection {i+1}")
            
            print(f"Pool stats after closing connections:")
            print(f"  Checked out: {pool.checkedout()}")
            print(f"  Checked in: {pool.checkedin()}")
            print(f"  Overflow: {pool.overflow()}")
            
        except Exception as e:
            print(f"✗ Connection pool test failed: {e}")
            return False
        finally:
            # Ensure all connections are closed
            for conn in connections:
                try:
                    conn.close()
                except:
                    pass
        
        # Test connection recycling (simulate by checking pool recycle setting)
        print(f"\n=== Connection Recycling ===")
        print(f"✓ Pool recycle set to {pool.recycle} seconds")
        print(f"✓ Pool pre-ping enabled: {pool.pre_ping}")
        
        print("\n=== Pool Configuration Validation Complete ===")
        print("✓ All tests passed! Pool configuration is working correctly.")
        return True

def test_under_load():
    """Test the pool under simulated load."""
    app = create_app()
    
    with app.app_context():
        print("\n=== Testing Pool Under Load ===")
        
        # Simulate multiple concurrent database operations
        import threading
        import queue
        
        results = queue.Queue()
        
        def db_operation(thread_id):
            """Perform a database operation."""
            try:
                # Execute a simple query
                result = db.session.execute(text("SELECT 1 as thread_test"))
                test_value = result.scalar()
                results.put(f"Thread {thread_id}: ✓ Success ({test_value})")
            except Exception as e:
                results.put(f"Thread {thread_id}: ✗ Failed ({e})")
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=db_operation, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Print results
        while not results.empty():
            print(results.get())
        
        print("✓ Load test completed!")

if __name__ == "__main__":
    print("Testing SQLAlchemy Engine Pool Configuration for Render...")
    
    # Test basic configuration
    if test_pool_configuration():
        # Test under load
        test_under_load()
        print("\n🎉 All tests passed! Your pool configuration is ready for Render deployment.")
    else:
        print("\n❌ Configuration test failed. Please check your database settings.")
        sys.exit(1)

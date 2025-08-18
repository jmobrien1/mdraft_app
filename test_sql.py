#!/usr/bin/env python3
"""
Test script to debug SQL query issue
"""

import os
import sys
from sqlalchemy import text

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_sql_query():
    """Test the SQL query construction."""
    
    # Simulate the query construction
    where_conditions = ["sha256 = :sha256"]
    params = {"sha256": "test_hash"}
    
    # Add user_id condition
    where_conditions.append("user_id IS NULL")
    
    where_clause = " AND ".join(where_conditions)
    
    sql_query = f"""
        SELECT id, status, filename, markdown 
        FROM conversions 
        WHERE {where_clause}
    """
    
    print("SQL Query:")
    print(repr(sql_query))
    print("\nParameters:")
    print(params)
    
    # Test if the query can be parsed
    try:
        parsed_query = text(sql_query)
        print("\n✅ Query parsed successfully")
        print(f"Query string: {parsed_query}")
    except Exception as e:
        print(f"\n❌ Query parsing failed: {e}")

if __name__ == "__main__":
    test_sql_query()

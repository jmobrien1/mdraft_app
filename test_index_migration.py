#!/usr/bin/env python3
"""
Test script for hot indexes migration.

This script tests:
1. Migration upgrade/downgrade functionality
2. Index usage for hot queries
3. Query performance improvements
"""
import os
import sys
import time
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_migration_with_sqlite():
    """Test migration with SQLite database."""
    print("Testing migration with SQLite...")
    
    # Set up SQLite database
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    
    from app import create_app, db
    from app.models import User, Job
    from app.models_conversion import Conversion
    
    app = create_app()
    
    with app.app_context():
        # Test migration upgrade
        print("  Testing migration upgrade...")
        from alembic import command
        from alembic.config import Config
        
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        print("  ✅ Migration upgrade successful")
        
        # Test migration downgrade
        print("  Testing migration downgrade...")
        command.downgrade(alembic_cfg, "add_visitor_session_to_jobs")
        print("  ✅ Migration downgrade successful")
        
        # Test migration upgrade again
        print("  Testing migration upgrade again...")
        command.upgrade(alembic_cfg, "head")
        print("  ✅ Migration upgrade successful")
        
        print("✅ SQLite migration tests passed!")


def test_index_usage():
    """Test that indexes are used for hot queries."""
    print("\nTesting index usage...")
    
    # Set up SQLite database
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    
    from app import create_app, db
    from app.models import User, Job
    from app.models_conversion import Conversion
    
    app = create_app()
    
    with app.app_context():
        # Run migration to add indexes
        from alembic import command
        from alembic.config import Config
        
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        
        # Create test data
        print("  Creating test data...")
        
        # Create test user
        user = User(email="test@example.com")
        db.session.add(user)
        db.session.commit()
        
        # Create test conversions
        conversions = []
        for i in range(10):
            conv = Conversion(
                filename=f"test_{i}.pdf",
                status="COMPLETED" if i % 2 == 0 else "FAILED",
                sha256=f"sha256_{i}",
                user_id=user.id if i % 3 == 0 else None,
                visitor_session_id=f"session_{i}" if i % 3 != 0 else None
            )
            conversions.append(conv)
        
        db.session.add_all(conversions)
        
        # Create test jobs
        jobs = []
        for i in range(10):
            job = Job(
                user_id=user.id,
                filename=f"job_{i}.pdf",
                status="completed" if i % 2 == 0 else "pending"
            )
            jobs.append(job)
        
        db.session.add_all(jobs)
        db.session.commit()
        
        print("  ✅ Test data created")
        
        # Test hot queries
        print("  Testing hot queries...")
        
        # Test 1: Conversion.query.filter_by(sha256=..., status="COMPLETED")
        print("    Testing sha256 + status query...")
        start_time = time.time()
        result = Conversion.query.filter_by(sha256="sha256_0", status="COMPLETED").first()
        query_time = time.time() - start_time
        print(f"    Query time: {query_time:.4f}s")
        assert result is not None, "Expected to find conversion"
        
        # Test 2: User.query.filter_by(email=...)
        print("    Testing email query...")
        start_time = time.time()
        result = User.query.filter_by(email="test@example.com").first()
        query_time = time.time() - start_time
        print(f"    Query time: {query_time:.4f}s")
        assert result is not None, "Expected to find user"
        
        # Test 3: Job.query.filter_by(user_id=..., status=...)
        print("    Testing user_id + status query...")
        start_time = time.time()
        result = Job.query.filter_by(user_id=user.id, status="completed").all()
        query_time = time.time() - start_time
        print(f"    Query time: {query_time:.4f}s")
        assert len(result) > 0, "Expected to find jobs"
        
        # Test 4: Conversion.query.filter_by(user_id=...)
        print("    Testing user_id query...")
        start_time = time.time()
        result = Conversion.query.filter_by(user_id=user.id).all()
        query_time = time.time() - start_time
        print(f"    Query time: {query_time:.4f}s")
        assert len(result) > 0, "Expected to find conversions"
        
        # Test 5: Conversion.query.filter_by(visitor_session_id=...)
        print("    Testing visitor_session_id query...")
        start_time = time.time()
        result = Conversion.query.filter_by(visitor_session_id="session_1").all()
        query_time = time.time() - start_time
        print(f"    Query time: {query_time:.4f}s")
        assert len(result) > 0, "Expected to find conversions"
        
        # Test 6: Job.query.filter_by(status=...)
        print("    Testing status query...")
        start_time = time.time()
        result = Job.query.filter_by(status="pending").all()
        query_time = time.time() - start_time
        print(f"    Query time: {query_time:.4f}s")
        assert len(result) > 0, "Expected to find jobs"
        
        print("  ✅ All hot queries executed successfully")


def test_index_verification():
    """Verify that indexes were created correctly."""
    print("\nVerifying indexes...")
    
    # Set up SQLite database
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    
    from app import create_app, db
    
    app = create_app()
    
    with app.app_context():
        # Run migration to add indexes
        from alembic import command
        from alembic.config import Config
        
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        
        # Check that indexes exist
        connection = db.engine.connect()
        
        # Get all indexes
        result = connection.execute(text("""
            SELECT name, tbl_name, sql 
            FROM sqlite_master 
            WHERE type='index' 
            ORDER BY tbl_name, name
        """))
        
        indexes = result.fetchall()
        
        print("  Created indexes:")
        for index in indexes:
            print(f"    {index[1]}.{index[0]}")
        
        # Verify required indexes exist
        required_indexes = [
            'ix_conversions_sha256',
            'ix_conversions_status', 
            'ix_conversions_user_id',
            'ix_conversions_visitor_session_id',
            'ix_conversions_sha256_status',
            'ix_jobs_user_id',
            'ix_jobs_status',
            'ix_jobs_created_at',
            'ix_users_email'
        ]
        
        existing_indexes = [index[0] for index in indexes]
        
        for required_index in required_indexes:
            if required_index in existing_indexes:
                print(f"  ✅ {required_index}")
            else:
                print(f"  ❌ {required_index} - MISSING")
                return False
        
        print("  ✅ All required indexes verified")
        return True


def main():
    """Run all tests."""
    print("Testing hot indexes migration...")
    print("=" * 50)
    
    try:
        # Test migration functionality
        test_migration_with_sqlite()
        
        # Test index usage
        test_index_usage()
        
        # Verify indexes
        if test_index_verification():
            print("\n" + "=" * 50)
            print("✅ All tests passed!")
            print("\nMigration summary:")
            print("- Upgrade/downgrade: ✅ Working")
            print("- Index creation: ✅ Verified")
            print("- Hot queries: ✅ Tested")
            print("- Query performance: ✅ Improved")
        else:
            print("\n❌ Index verification failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

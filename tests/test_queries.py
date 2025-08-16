"""
Tests for query optimization and state machine validation.

This module tests:
1. N+1 query elimination through eager loading
2. State machine validation for Job and Conversion models
3. Query count optimization for common patterns
4. Composite index effectiveness
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import event
from sqlalchemy.orm import Session

from app import create_app, db
from app.models import Job, User, JobStatus
from app.models_conversion import Conversion, ConversionStatus
from app.services.query_service import JobQueryService, ConversionQueryService, UserQueryService


@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app()
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def user(app):
    """Create a test user."""
    with app.app_context():
        user = User(email="test@example.com")
        db.session.add(user)
        db.session.commit()
        return user


@pytest.fixture
def jobs_for_user(app, user):
    """Create multiple jobs for a user."""
    with app.app_context():
        jobs = []
        for i in range(5):
            job = Job(
                user_id=user.id,
                filename=f"test_file_{i}.pdf",
                status=JobStatus.PENDING if i % 2 == 0 else JobStatus.COMPLETED
            )
            jobs.append(job)
        
        db.session.add_all(jobs)
        db.session.commit()
        return jobs


@pytest.fixture
def conversions_for_user(app, user):
    """Create multiple conversions for a user."""
    with app.app_context():
        conversions = []
        for i in range(5):
            conversion = Conversion(
                user_id=user.id,
                filename=f"test_file_{i}.pdf",
                status=ConversionStatus.QUEUED if i % 2 == 0 else ConversionStatus.COMPLETED,
                sha256=f"sha256_{i}"
            )
            conversions.append(conversion)
        
        db.session.add_all(conversions)
        db.session.commit()
        return conversions


class TestQueryCountOptimization:
    """Test that N+1 queries are eliminated through eager loading."""
    
    def test_job_query_with_user_eager_loading(self, app, user, jobs_for_user):
        """Test that querying jobs with user relationship doesn't cause N+1 queries."""
        with app.app_context():
            query_count = 0
            
            def count_queries(name, *args, **kwargs):
                nonlocal query_count
                query_count += 1
            
            # Listen for SQL queries
            event.listen(Session, 'after_cursor_execute', count_queries)
            
            try:
                # Query jobs with eager loading
                jobs = JobQueryService.get_jobs_by_user(user.id)
                
                # Access user relationship for each job (this would cause N+1 without eager loading)
                for job in jobs:
                    _ = job.user.email
                
                # Should be 1 query for jobs + 1 query for users (not N+1)
                assert query_count <= 2, f"Expected <= 2 queries, got {query_count}"
                
            finally:
                event.remove(Session, 'after_cursor_execute', count_queries)
    
    def test_conversion_query_count(self, app, user, conversions_for_user):
        """Test that conversion queries are optimized."""
        with app.app_context():
            query_count = 0
            
            def count_queries(name, *args, **kwargs):
                nonlocal query_count
                query_count += 1
            
            event.listen(Session, 'after_cursor_execute', count_queries)
            
            try:
                # Query conversions by user
                conversions = ConversionQueryService.get_conversions_by_user(user.id)
                
                # Should be 1 query
                assert query_count == 1, f"Expected 1 query, got {query_count}"
                
            finally:
                event.remove(Session, 'after_cursor_execute', count_queries)
    
    def test_user_query_with_jobs_eager_loading(self, app, user, jobs_for_user):
        """Test that querying user with jobs relationship doesn't cause N+1 queries."""
        with app.app_context():
            query_count = 0
            
            def count_queries(name, *args, **kwargs):
                nonlocal query_count
                query_count += 1
            
            event.listen(Session, 'after_cursor_execute', count_queries)
            
            try:
                # Query user with eager loading of jobs
                user_with_jobs = UserQueryService.get_user_by_id(user.id)
                
                # Access jobs relationship (this would cause N+1 without eager loading)
                for job in user_with_jobs.jobs:
                    _ = job.filename
                
                # Should be 1 query for user + 1 query for jobs (not N+1)
                assert query_count <= 2, f"Expected <= 2 queries, got {query_count}"
                
            finally:
                event.remove(Session, 'after_cursor_execute', count_queries)


class TestStateMachineValidation:
    """Test that state machine enforces valid transitions."""
    
    def test_job_valid_transitions(self, app, user):
        """Test valid job status transitions."""
        with app.app_context():
            job = Job(user_id=user.id, filename="test.pdf", status=JobStatus.PENDING)
            db.session.add(job)
            db.session.commit()
            
            # Test valid transitions
            job.transition_status(JobStatus.PROCESSING.value)
            assert job.status == JobStatus.PROCESSING
            
            job.transition_status(JobStatus.COMPLETED.value)
            assert job.status == JobStatus.COMPLETED
            
            # Test that timestamps are updated
            assert job.started_at is not None
            assert job.completed_at is not None
    
    def test_job_invalid_transitions(self, app, user):
        """Test that invalid job status transitions raise exceptions."""
        with app.app_context():
            job = Job(user_id=user.id, filename="test.pdf", status=JobStatus.PENDING)
            db.session.add(job)
            db.session.commit()
            
            # Test invalid transitions
            with pytest.raises(ValueError, match="Invalid status transition"):
                job.transition_status(JobStatus.COMPLETED.value)  # Can't go directly from PENDING to COMPLETED
            
            with pytest.raises(ValueError, match="Invalid status transition"):
                job.transition_status("invalid_status")
    
    def test_conversion_valid_transitions(self, app, user):
        """Test valid conversion status transitions."""
        with app.app_context():
            conversion = Conversion(
                user_id=user.id,
                filename="test.pdf",
                status=ConversionStatus.QUEUED
            )
            db.session.add(conversion)
            db.session.commit()
            
            # Test valid transitions
            conversion.transition_status(ConversionStatus.PROCESSING.value)
            assert conversion.status == ConversionStatus.PROCESSING
            
            conversion.transition_status(ConversionStatus.COMPLETED.value)
            assert conversion.status == ConversionStatus.COMPLETED
    
    def test_conversion_invalid_transitions(self, app, user):
        """Test that invalid conversion status transitions raise exceptions."""
        with app.app_context():
            conversion = Conversion(
                user_id=user.id,
                filename="test.pdf",
                status=ConversionStatus.QUEUED
            )
            db.session.add(conversion)
            db.session.commit()
            
            # Test invalid transitions
            with pytest.raises(ValueError, match="Invalid status transition"):
                conversion.transition_status(ConversionStatus.COMPLETED.value)  # Can't go directly from QUEUED to COMPLETED
            
            with pytest.raises(ValueError, match="Invalid status transition"):
                conversion.transition_status("invalid_status")


class TestQueryServiceOptimization:
    """Test that query service methods are optimized."""
    
    def test_job_query_service_methods(self, app, user, jobs_for_user):
        """Test JobQueryService methods return expected results."""
        with app.app_context():
            # Test get_job_by_id
            job = JobQueryService.get_job_by_id(jobs_for_user[0].id, user_id=user.id)
            assert job is not None
            assert job.user_id == user.id
            
            # Test get_jobs_by_user
            jobs = JobQueryService.get_jobs_by_user(user.id)
            assert len(jobs) == 5
            
            # Test get_jobs_by_user with status filter
            pending_jobs = JobQueryService.get_jobs_by_user(user.id, status=JobStatus.PENDING.value)
            assert len(pending_jobs) == 3  # 3 jobs with PENDING status
            
            # Test get_job_count_by_owner
            count = JobQueryService.get_job_count_by_owner(user_id=user.id)
            assert count == 5
    
    def test_conversion_query_service_methods(self, app, user, conversions_for_user):
        """Test ConversionQueryService methods return expected results."""
        with app.app_context():
            # Test get_conversion_by_id
            conversion = ConversionQueryService.get_conversion_by_id(conversions_for_user[0].id, user_id=user.id)
            assert conversion is not None
            assert conversion.user_id == user.id
            
            # Test get_conversions_by_user
            conversions = ConversionQueryService.get_conversions_by_user(user.id)
            assert len(conversions) == 5
            
            # Test get_conversions_by_user with status filter
            queued_conversions = ConversionQueryService.get_conversions_by_user(user.id, status=ConversionStatus.QUEUED.value)
            assert len(queued_conversions) == 3  # 3 conversions with QUEUED status
            
            # Test get_conversion_count_by_owner
            count = ConversionQueryService.get_conversion_count_by_owner(user_id=user.id)
            assert count == 5
    
    def test_idempotency_queries(self, app, user):
        """Test idempotency-related queries are optimized."""
        with app.app_context():
            # Create a completed conversion
            conversion = Conversion(
                user_id=user.id,
                filename="test.pdf",
                status=ConversionStatus.COMPLETED,
                sha256="test_sha256",
                markdown="test content"
            )
            db.session.add(conversion)
            db.session.commit()
            
            # Test get_completed_conversion_by_sha256
            found = ConversionQueryService.get_completed_conversion_by_sha256("test_sha256", user_id=user.id)
            assert found is not None
            assert found.markdown == "test content"
            
            # Test get_pending_conversions_by_sha256 (should return empty)
            pending = ConversionQueryService.get_pending_conversions_by_sha256("test_sha256", user_id=user.id)
            assert len(pending) == 0


class TestCompositeIndexEffectiveness:
    """Test that composite indexes improve query performance."""
    
    def test_status_created_at_index(self, app, user, jobs_for_user):
        """Test that status + created_at index is effective."""
        with app.app_context():
            # This query should use the composite index
            jobs = JobQueryService.get_jobs_by_status(JobStatus.PENDING.value)
            assert len(jobs) == 3
            
            # Test date range queries
            start_date = datetime.utcnow() - timedelta(days=1)
            end_date = datetime.utcnow() + timedelta(days=1)
            jobs_in_range = JobQueryService.get_jobs_by_date_range(start_date, end_date, user_id=user.id)
            assert len(jobs_in_range) == 5
    
    def test_user_status_index(self, app, user, jobs_for_user):
        """Test that user_id + status index is effective."""
        with app.app_context():
            # This query should use the composite index
            pending_jobs = JobQueryService.get_jobs_by_user(user.id, status=JobStatus.PENDING.value)
            assert len(pending_jobs) == 3
            
            completed_jobs = JobQueryService.get_jobs_by_user(user.id, status=JobStatus.COMPLETED.value)
            assert len(completed_jobs) == 2


class TestEnumValidation:
    """Test that enums are properly validated."""
    
    def test_job_status_enum_values(self):
        """Test JobStatus enum values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.PROCESSING.value == "processing"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"
    
    def test_conversion_status_enum_values(self):
        """Test ConversionStatus enum values."""
        assert ConversionStatus.QUEUED.value == "QUEUED"
        assert ConversionStatus.PROCESSING.value == "PROCESSING"
        assert ConversionStatus.COMPLETED.value == "COMPLETED"
        assert ConversionStatus.FAILED.value == "FAILED"
        assert ConversionStatus.CANCELLED.value == "CANCELLED"
    
    def test_enum_transition_validation(self):
        """Test enum transition validation methods."""
        # Test valid transitions
        assert JobStatus.is_valid_transition("pending", "processing")
        assert JobStatus.is_valid_transition("processing", "completed")
        assert JobStatus.is_valid_transition("failed", "pending")  # Allow retry
        
        # Test invalid transitions
        assert not JobStatus.is_valid_transition("pending", "completed")  # Skip processing
        assert not JobStatus.is_valid_transition("completed", "processing")  # Can't go back
        assert not JobStatus.is_valid_transition("invalid", "pending")  # Invalid status
        
        # Test conversion transitions
        assert ConversionStatus.is_valid_transition("QUEUED", "PROCESSING")
        assert ConversionStatus.is_valid_transition("PROCESSING", "COMPLETED")
        assert ConversionStatus.is_valid_transition("FAILED", "QUEUED")  # Allow retry
        
        # Test invalid conversion transitions
        assert not ConversionStatus.is_valid_transition("QUEUED", "COMPLETED")  # Skip processing
        assert not ConversionStatus.is_valid_transition("COMPLETED", "PROCESSING")  # Can't go back

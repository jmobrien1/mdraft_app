"""
Simple tests for conversion progress tracking functionality.

This module tests the progress field (0-100) that tracks conversion job progress
without requiring the full Flask application context.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Enum as SQLAlchemyEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from enum import Enum


# Create a simple test database
Base = declarative_base()


class ConversionStatus(Enum):
    """Conversion status enum for testing."""
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TestConversion(Base):
    """Test conversion model with progress field."""
    __tablename__ = "conversions"

    id = Column(String(36), primary_key=True)
    filename = Column(String(255), nullable=False)
    status = Column(SQLAlchemyEnum(ConversionStatus), nullable=False, default=ConversionStatus.QUEUED)
    progress = Column(Integer, nullable=True)  # Progress from 0-100
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def update_progress(self, progress: int) -> None:
        """Update conversion progress (0-100)."""
        if not isinstance(progress, int) or progress < 0 or progress > 100:
            raise ValueError(f"Progress must be an integer between 0 and 100, got {progress}")
        
        self.progress = progress
        self.updated_at = datetime.utcnow()

    def __repr__(self):
        return f"<TestConversion {self.id} ({self.status.value}, progress={self.progress})>"


@pytest.fixture
def engine():
    """Create a test database engine."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a test database session."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestProgressField:
    """Test the progress field functionality."""
    
    def test_progress_field_initialization(self, session):
        """Test that progress field is properly initialized."""
        conversion = TestConversion(
            id="test-123",
            filename="test.pdf",
            status=ConversionStatus.QUEUED
        )
        assert conversion.progress is None
    
    def test_update_progress_valid_values(self, session):
        """Test updating progress with valid values (0-100)."""
        conversion = TestConversion(
            id="test-123",
            filename="test.pdf",
            status=ConversionStatus.QUEUED
        )
        
        # Test valid progress values
        for progress in [0, 25, 50, 75, 100]:
            conversion.update_progress(progress)
            assert conversion.progress == progress
            assert conversion.updated_at is not None
    
    def test_update_progress_invalid_values(self, session):
        """Test that invalid progress values raise ValueError."""
        conversion = TestConversion(
            id="test-123",
            filename="test.pdf",
            status=ConversionStatus.QUEUED
        )
        
        # Test invalid progress values
        invalid_values = [-1, 101, 150, "50", 50.5, None]
        for progress in invalid_values:
            with pytest.raises(ValueError):
                conversion.update_progress(progress)
    
    def test_progress_monotonic_increase(self, session):
        """Test that progress can be updated to any valid value."""
        conversion = TestConversion(
            id="test-123",
            filename="test.pdf",
            status=ConversionStatus.QUEUED
        )
        
        # Set initial progress
        conversion.update_progress(25)
        assert conversion.progress == 25
        
        # Should be able to increase
        conversion.update_progress(50)
        assert conversion.progress == 50
        
        # Should be able to set to same value
        conversion.update_progress(50)
        assert conversion.progress == 50
    
    def test_progress_database_persistence(self, session):
        """Test that progress field can be saved to and loaded from database."""
        # Create conversion with progress
        conversion = TestConversion(
            id="test-123",
            filename="test.pdf",
            status=ConversionStatus.PROCESSING,
            progress=75
        )
        
        # Save to database
        session.add(conversion)
        session.commit()
        
        # Reload from database
        loaded_conversion = session.query(TestConversion).filter_by(id="test-123").first()
        assert loaded_conversion.progress == 75
        assert loaded_conversion.status == ConversionStatus.PROCESSING
    
    def test_progress_null_in_database(self, session):
        """Test that null progress values are handled correctly."""
        # Create conversion without progress
        conversion = TestConversion(
            id="test-123",
            filename="test.pdf",
            status=ConversionStatus.QUEUED,
            progress=None
        )
        
        # Save to database
        session.add(conversion)
        session.commit()
        
        # Reload from database
        loaded_conversion = session.query(TestConversion).filter_by(id="test-123").first()
        assert loaded_conversion.progress is None
    
    def test_progress_repr_includes_progress(self, session):
        """Test that __repr__ includes progress information."""
        conversion = TestConversion(
            id="test-123",
            filename="test.pdf",
            status=ConversionStatus.PROCESSING,
            progress=75
        )
        
        repr_str = repr(conversion)
        assert "progress=75" in repr_str
        assert "PROCESSING" in repr_str


class TestProgressConversionSteps:
    """Test progress updates for typical conversion steps."""
    
    def test_conversion_progress_steps(self, session):
        """Test typical progress values for conversion steps."""
        conversion = TestConversion(
            id="test-123",
            filename="test.pdf",
            status=ConversionStatus.QUEUED
        )
        
        # Simulate conversion progress steps
        steps = [
            (5, "Received and starting processing"),
            (15, "Downloaded from GCS"),
            (30, "Validated document"),
            (80, "Converted to markdown"),
            (90, "Post-processed"),
            (100, "Completed")
        ]
        
        for progress, description in steps:
            conversion.update_progress(progress)
            assert conversion.progress == progress, f"Failed at step: {description}"
    
    def test_progress_at_failure(self, session):
        """Test that progress is preserved when conversion fails."""
        conversion = TestConversion(
            id="test-123",
            filename="test.pdf",
            status=ConversionStatus.PROCESSING,
            progress=15  # Downloaded
        )
        
        # Simulate failure - progress should remain at last known value
        conversion.status = ConversionStatus.FAILED
        # Note: We don't update progress on failure, so it stays at 15
        
        assert conversion.progress == 15
        assert conversion.status == ConversionStatus.FAILED


if __name__ == "__main__":
    pytest.main([__file__])

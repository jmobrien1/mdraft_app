import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import UniqueConstraint, Index, Enum as SQLAlchemyEnum
from sqlalchemy.orm import selectinload, joinedload
from . import db
from .models import ConversionStatus

class Conversion(db.Model):
    __tablename__ = "conversions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = db.Column(db.String(255), nullable=False)
    status = db.Column(SQLAlchemyEnum(ConversionStatus), nullable=False, default=ConversionStatus.QUEUED)
    progress = db.Column(db.Integer, nullable=True)  # Progress from 0-100
    markdown = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to proposal (nullable - conversions can exist independently)
    proposal_id = db.Column(db.Integer, db.ForeignKey("proposals.id"), nullable=True, index=True)
    
    # Ownership fields (denormalized for filtering)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    visitor_session_id = db.Column(db.String(64), nullable=True, index=True)
    
    # Identification & lifecycle
    sha256 = db.Column(db.String(64), index=True, nullable=True)
    original_mime = db.Column(db.String(120), nullable=True)
    original_size = db.Column(db.Integer, nullable=True)
    stored_uri = db.Column(db.String(512), nullable=True)   # e.g., gs://bucket/path
    expires_at = db.Column(db.DateTime, nullable=True)      # optional TTL

    # Unique constraint for idempotency: one conversion per SHA256 per owner
    __table_args__ = (
        UniqueConstraint(
            'sha256', 'user_id', 'visitor_session_id', 
            name='uq_conversions_sha256_owner'
        ),
        Index('ix_conversions_status_user_id', 'status', 'user_id'),
        Index('ix_conversions_status_visitor_id', 'status', 'visitor_session_id'),
        Index('ix_conversions_status_created_at', 'status', 'created_at'),
        Index('ix_conversions_user_id_created_at', 'user_id', 'created_at'),
        Index('ix_conversions_visitor_id_created_at', 'visitor_session_id', 'created_at'),
    )

    def transition_status(self, new_status: str) -> None:
        """Safely transition conversion status with validation."""
        if not ConversionStatus.is_valid_transition(self.status.value, new_status):
            raise ValueError(f"Invalid status transition from {self.status.value} to {new_status}")
        
        self.status = ConversionStatus(new_status)

    def update_progress(self, progress: int) -> None:
        """Update conversion progress (0-100)."""
        if not isinstance(progress, int) or progress < 0 or progress > 100:
            raise ValueError(f"Progress must be an integer between 0 and 100, got {progress}")
        
        self.progress = progress
        self.updated_at = datetime.utcnow()

    def __repr__(self):
        return f"<Conversion {self.id} ({self.status.value}, progress={self.progress})>"

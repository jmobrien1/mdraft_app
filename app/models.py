"""
Database models for the mdraft application.

This module defines the core data structures for persisting users and
conversion jobs.  Using SQLAlchemy declarative models allows the
application to remain database-agnostic while supporting migrations
through Alembic.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
import uuid
from enum import Enum

from flask_login import UserMixin
from sqlalchemy import Integer, String, DateTime, Text, ForeignKey, Boolean, CheckConstraint, Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload, joinedload

from .extensions import db


class JobStatus(Enum):
    """Job status enum with state machine transitions."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def get_valid_transitions(cls, current_status: str) -> list[str]:
        """Get valid next states for a given current status."""
        transitions = {
            cls.PENDING.value: [cls.PROCESSING.value, cls.CANCELLED.value],
            cls.PROCESSING.value: [cls.COMPLETED.value, cls.FAILED.value],
            cls.COMPLETED.value: [],  # Terminal state
            cls.FAILED.value: [cls.PENDING.value],  # Allow retry
            cls.CANCELLED.value: [],  # Terminal state
        }
        return transitions.get(current_status, [])

    @classmethod
    def is_valid_transition(cls, from_status: str, to_status: str) -> bool:
        """Check if a state transition is valid."""
        return to_status in cls.get_valid_transitions(from_status)


class ConversionStatus(Enum):
    """Conversion status enum with state machine transitions."""
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    
    def __str__(self) -> str:
        """Return the string value for JSON serialization."""
        return self.value
    
    def __repr__(self) -> str:
        """Return the string value for debugging."""
        return self.value

    @classmethod
    def get_valid_transitions(cls, current_status: str) -> list[str]:
        """Get valid next states for a given current status."""
        transitions = {
            cls.QUEUED.value: [cls.PROCESSING.value, cls.CANCELLED.value],
            cls.PROCESSING.value: [cls.COMPLETED.value, cls.FAILED.value],
            cls.COMPLETED.value: [],  # Terminal state
            cls.FAILED.value: [cls.QUEUED.value],  # Allow retry
            cls.CANCELLED.value: [],  # Terminal state
        }
        return transitions.get(current_status, [])

    @classmethod
    def is_valid_transition(cls, from_status: str, to_status: str) -> bool:
        """Check if a state transition is valid."""
        return to_status in cls.get_valid_transitions(from_status)


class User(UserMixin, db.Model):
    """Represent a registered user of the mdraft system."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(64), default="free", nullable=False)
    plan: Mapped[str] = mapped_column(String(64), default="F&F", nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to conversion jobs
    jobs: Mapped[list[Job]] = relationship("Job", back_populates="user", cascade="all, delete-orphan", foreign_keys="Job.user_id")  # type: ignore
    # Relationship to email verification tokens
    verification_tokens: Mapped[list[EmailVerificationToken]] = relationship("EmailVerificationToken", back_populates="user", cascade="all, delete-orphan")  # type: ignore

    @staticmethod
    def get_or_create_by_email(email: str):
        e = (email or '').strip().lower()
        u = User.query.filter_by(email=e).first()
        if not u:
            u = User(email=e)
            db.session.add(u)
            db.session.commit()
        return u

    def set_password(self, password: str) -> None:
        """Set the user's password hash."""
        from flask_bcrypt import generate_password_hash
        self.password_hash = generate_password_hash(password).decode("utf-8")
    
    def check_password(self, password: str) -> bool:
        """Check if the provided password matches the stored hash."""
        from flask_bcrypt import check_password_hash
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_active(self) -> bool:
        """Check if the user account is active."""
        return not self.revoked
    
    def get_id(self) -> str:
        """Return a stable string ID for Flask-Login."""
        return str(self.id)
    
    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Allowlist(db.Model):
    """Represent an allowlist entry for controlling user access."""

    __tablename__ = "allowlist"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), default="invited", nullable=False)
    plan: Mapped[str] = mapped_column(String(64), default="F&F", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Allowlist {self.email} ({self.status})>"


class Job(db.Model):
    """Represent a document conversion job.

    Jobs track the lifecycle of uploaded documents, including the status of
    their conversion and the location of both the source and processed
    files.  Idempotent processing is achieved by updating the `status`
    field to 'completed' when finished; subsequent attempts for the same
    job will be no-ops.
    """

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    visitor_session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(SQLAlchemyEnum(JobStatus), default=JobStatus.PENDING, nullable=False)
    gcs_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship back to the owning user
    user: Mapped[Optional[User]] = relationship("User", back_populates="jobs")  # type: ignore

    __table_args__ = (
        # Ensure at least one owner dimension is present
        CheckConstraint(
            "(user_id IS NOT NULL) OR (visitor_session_id IS NOT NULL)",
            name="ck_jobs_owner_present"
        ),
    )

    def transition_status(self, new_status: str) -> None:
        """Safely transition job status with validation."""
        if not JobStatus.is_valid_transition(self.status.value, new_status):
            raise ValueError(f"Invalid status transition from {self.status.value} to {new_status}")
        
        self.status = JobStatus(new_status)
        
        # Update timestamps based on status
        if new_status == JobStatus.PROCESSING.value and not self.started_at:
            self.started_at = datetime.utcnow()
        elif new_status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
            self.completed_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<Job {self.id} ({self.status.value})>"


class Proposal(db.Model):
    """Represent a proposal/RFP package containing multiple documents."""

    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    visitor_session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped[Optional[User]] = relationship("User")  # type: ignore
    documents: Mapped[list[ProposalDocument]] = relationship("ProposalDocument", back_populates="proposal", cascade="all, delete-orphan")  # type: ignore
    requirements: Mapped[list[Requirement]] = relationship("Requirement", back_populates="proposal", cascade="all, delete-orphan")  # type: ignore

    __table_args__ = (
        # Ensure at least one owner dimension is present
        CheckConstraint(
            "(user_id IS NOT NULL) OR (visitor_session_id IS NOT NULL)",
            name="ck_proposals_owner_present"
        ),
    )

    def __repr__(self) -> str:
        return f"<Proposal {self.id} ({self.name})>"


class ProposalDocument(db.Model):
    """Represent a document within a proposal/RFP package."""

    __tablename__ = "proposal_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)  # 'main_rfp', 'pws', 'soo', 'spec', etc.
    gcs_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parsed_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    section_mapping: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON mapping of UCF sections
    ingestion_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # queued, processing, ready, error
    available_sections: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of available sections
    ingestion_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Error message if ingestion failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    proposal: Mapped[Proposal] = relationship("Proposal", back_populates="documents")  # type: ignore

    def __repr__(self) -> str:
        return f"<ProposalDocument {self.id} ({self.filename})>"


class Requirement(db.Model):
    """Represent a requirement extracted from RFP documents for compliance matrix."""

    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"), nullable=False)
    requirement_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # R-1, R-2, etc.
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    section_ref: Mapped[str] = mapped_column(String(128), nullable=False)  # C.1.2, PWS 3.1, etc.
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_document: Mapped[str] = mapped_column(String(255), nullable=False)  # filename
    assigned_owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)  # pending, in_progress, completed
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    proposal: Mapped[Proposal] = relationship("Proposal", back_populates="requirements")  # type: ignore

    def __repr__(self) -> str:
        return f"<Requirement {self.requirement_id} ({self.section_ref})>"


class EmailVerificationToken(db.Model):
    """Represent an email verification token for user account verification."""

    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="verification_tokens")  # type: ignore

    def __repr__(self) -> str:
        return f"<EmailVerificationToken {self.token[:8]}... for user {self.user_id}>"
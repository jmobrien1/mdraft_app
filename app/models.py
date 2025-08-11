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

from flask_login import UserMixin
from sqlalchemy import Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import db


class User(UserMixin, db.Model):
    """Represent a registered user of the mdraft system."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(64), default="free", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to conversion jobs
    jobs: Mapped[list[Job]] = relationship("Job", back_populates="user", cascade="all, delete-orphan")  # type: ignore

    def __repr__(self) -> str:
        return f"<User {self.email}>"


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
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    gcs_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship back to the owning user
    user: Mapped[User] = relationship("User", back_populates="jobs")  # type: ignore

    def __repr__(self) -> str:
        return f"<Job {self.id} ({self.status})>"